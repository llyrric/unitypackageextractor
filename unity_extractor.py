"""Unity Package Extractor - extract .unitypackage contents into a normal folder tree
(handy for importing assets into Godot 4)."""
import gzip
import os
import re
import shutil
import tarfile
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

INVALID = re.compile(r'[<>:"|?*\x00-\x1f]')
PKG_TYPES = [("Unity package", "*.unitypackage *.unitypackage.gz *_unitypackage.gz"),
             ("All", "*.*")]


def safe_rel(path: str) -> str:
    parts = []
    for p in path.replace("\\", "/").split("/"):
        if p in ("", ".", ".."):
            continue
        parts.append(INVALID.sub("_", p).rstrip(" ."))
    return os.path.join(*parts) if parts else ""


def pkg_name(path: str) -> str:
    # .unitypackage.gz is the same gzipped tar, just renamed
    return re.sub(r"[._]unitypackage(\.gz)?$", "", os.path.basename(path), flags=re.I)


def extract_package(pkg, dest, keep_meta=False, strip_assets=True,
                    progress=None, log=None, cancel=None):
    """Extract pkg into dest. Returns (files_written, skipped)."""
    log = log or (lambda m: None)
    progress = progress or (lambda f: None)
    os.makedirs(dest, exist_ok=True)
    # Not tempfile.mkdtemp: on Windows it sets a restrictive ACL that breaks
    # creating subfolders on some drives (WinError 5).
    tmp = os.path.join(dest, ".unitypkg_" + os.urandom(4).hex())
    os.makedirs(tmp)
    total = os.path.getsize(pkg)
    try:
        log("Reading package...")
        with open(pkg, "rb") as raw:
            # tarfile's own streaming gzip reader mis-parses the gzip header's
            # extra field, where Asset Store packages keep their metadata
            # ("invalid compressed data"), so let the gzip module handle it.
            is_gz = raw.read(2) == b"\x1f\x8b"
            raw.seek(0)
            stream = gzip.GzipFile(fileobj=raw) if is_gz else raw
            with tarfile.open(fileobj=stream, mode="r|" if is_gz else "r|*") as tar:
                for m in tar:
                    if cancel and cancel.is_set():
                        raise InterruptedError
                    progress(raw.tell() / total * 0.7)
                    if not m.isfile():
                        continue
                    parts = m.name.replace("\\", "/").strip("./").split("/")
                    if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]+", parts[0]):
                        continue
                    if parts[1] not in ("asset", "pathname", "asset.meta"):
                        continue
                    d = os.path.join(tmp, parts[0])
                    os.makedirs(d, exist_ok=True)
                    src = tar.extractfile(m)
                    with open(os.path.join(d, parts[1]), "wb") as out:
                        shutil.copyfileobj(src, out, 1 << 20)

        guids = [g for g in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, g))]
        written = skipped = 0
        for i, g in enumerate(guids):
            if cancel and cancel.is_set():
                raise InterruptedError
            progress(0.7 + 0.3 * (i / max(1, len(guids))))
            gd = os.path.join(tmp, g)
            pn = os.path.join(gd, "pathname")
            if not os.path.exists(pn):
                skipped += 1
                continue
            with open(pn, "r", encoding="utf-8", errors="replace") as f:
                rel = safe_rel(f.readline().strip())
            if strip_assets and rel.lower().startswith("assets" + os.sep):
                rel = rel[len("assets") + 1:]
            if not rel:
                skipped += 1
                continue
            target = os.path.join(dest, rel)
            for name, tgt in (("asset", target), ("asset.meta", target + ".meta")):
                s = os.path.join(gd, name)
                if not os.path.exists(s):
                    continue
                if name == "asset.meta" and not keep_meta:
                    continue
                os.makedirs(os.path.dirname(tgt), exist_ok=True)
                shutil.move(s, tgt)
                if name == "asset":
                    written += 1
                    log(rel)
            # folder entries have only a meta/pathname -> nothing to write
        progress(1.0)
        return written, skipped
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Unity Package Extractor")
        self.geometry("760x600")
        self.dest = tk.StringVar()
        self.keep_meta = tk.BooleanVar(value=False)
        self.strip = tk.BooleanVar(value=True)
        self.cancel = threading.Event()

        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)
        f.columnconfigure(1, weight=1)
        f.rowconfigure(6, weight=1)

        ttk.Label(f, text="Unity packages:").grid(row=0, column=0, sticky="nw", pady=4)
        self.pkgbox = tk.Listbox(f, height=6, selectmode="extended", activestyle="none")
        self.pkgbox.grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        pf = ttk.Frame(f)
        pf.grid(row=0, column=2, sticky="n", pady=4)
        self.pkg_btns = [
            ttk.Button(pf, text="Browse...", command=self.pick_pkgs),
            ttk.Button(pf, text="Add...", command=lambda: self.pick_pkgs(add=True)),
            ttk.Button(pf, text="Remove", command=self.remove_pkgs),
        ]
        for b in self.pkg_btns:
            b.pack(fill="x", pady=(0, 2))

        ttk.Label(f, text="Output folder:").grid(row=1, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.dest).grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ttk.Button(f, text="Browse...", command=self.pick_dest).grid(row=1, column=2, sticky="ew")
        ttk.Label(f, text="Each package is extracted into its own subfolder named after the package.",
                  foreground="gray").grid(row=2, column=1, sticky="w", padx=6)

        ttk.Checkbutton(f, text="Strip leading 'Assets/' folder", variable=self.strip
                        ).grid(row=3, column=1, sticky="w")
        ttk.Checkbutton(f, text="Keep Unity .meta files (not needed for Godot)",
                        variable=self.keep_meta).grid(row=4, column=1, sticky="w")

        bf = ttk.Frame(f)
        bf.grid(row=5, column=0, columnspan=3, sticky="ew", pady=8)
        self.btn = ttk.Button(bf, text="Extract", command=self.start)
        self.btn.pack(side="left")
        self.cbtn = ttk.Button(bf, text="Cancel", command=self.cancel.set, state="disabled")
        self.cbtn.pack(side="left", padx=6)
        self.bar = ttk.Progressbar(bf, maximum=100)
        self.bar.pack(side="left", fill="x", expand=True, padx=6)

        self.logbox = tk.Text(f, height=10, state="disabled")
        self.logbox.grid(row=6, column=0, columnspan=3, sticky="nsew")
        sb = ttk.Scrollbar(f, command=self.logbox.yview)
        sb.grid(row=6, column=3, sticky="ns")
        self.logbox["yscrollcommand"] = sb.set

    def pick_pkgs(self, add=False):
        ps = filedialog.askopenfilenames(filetypes=PKG_TYPES)
        if not ps:
            return
        if not add:
            self.pkgbox.delete(0, "end")
        have = set(self.pkgbox.get(0, "end"))
        for p in ps:
            p = os.path.normpath(p)
            if p not in have:
                self.pkgbox.insert("end", p)
        # Browse always follows the new packages; Add keeps a folder already chosen
        if not add or not self.dest.get():
            self.dest.set(os.path.dirname(os.path.normpath(ps[0])))

    def remove_pkgs(self):
        for i in reversed(self.pkgbox.curselection()):
            self.pkgbox.delete(i)

    def pick_dest(self):
        p = filedialog.askdirectory()
        if p:
            self.dest.set(p)

    def log(self, msg):
        def w():
            self.logbox.configure(state="normal")
            self.logbox.insert("end", msg + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.after(0, w)

    def set_busy(self, busy):
        self.btn.configure(state="disabled" if busy else "normal")
        self.cbtn.configure(state="normal" if busy else "disabled")
        for b in self.pkg_btns:
            b.configure(state="disabled" if busy else "normal")

    def start(self):
        pkgs = list(self.pkgbox.get(0, "end"))
        missing = [p for p in pkgs if not os.path.isfile(p)]
        if not pkgs or not self.dest.get():
            messagebox.showerror("Error", "Select at least one package and an output folder.")
            return
        if missing:
            messagebox.showerror("Error", "Package not found:\n" + "\n".join(missing))
            return
        self.cancel.clear()
        self.set_busy(True)
        self.bar["value"] = 0
        threading.Thread(target=self.run, daemon=True,
                         args=(pkgs, os.path.normpath(self.dest.get()),self.keep_meta.get(), self.strip.get())
                         ).start()

    def run(self, pkgs, out, keep_meta, strip):
        n = len(pkgs)
        total = 0
        failed = []
        try:
            for i, p in enumerate(pkgs):
                dest = os.path.join(out, pkg_name(p))
                self.log(f"=== [{i + 1}/{n}] {os.path.basename(p)} -> {dest}")
                try:
                    w, s = extract_package(
                        p, dest, keep_meta, strip,
                        progress=lambda f, i=i: self.after(
                            0, lambda: self.bar.configure(value=(i + f) / n * 100)),
                        log=self.log, cancel=self.cancel)
                except InterruptedError:
                    raise
                except Exception as e:
                    failed.append(f"{os.path.basename(p)}: {e}")
                    self.log(f"Error: {e}")
                    try:
                        os.rmdir(dest)  # only if nothing got written
                    except OSError:
                        pass
                    continue
                total += w
                self.log(f"Done: {w} files extracted ({s} skipped).")
            if n == 1 and not failed:
                msg = f"Extracted {total} files to\n{dest}"
            else:
                msg = f"Extracted {n - len(failed)} of {n} packages ({total} files) to\n{out}"
            if failed:
                msg += "\n\nFailed:\n" + "\n".join(failed)
                self.after(0, lambda: messagebox.showwarning("Finished with errors", msg))
            else:
                self.after(0, lambda: messagebox.showinfo("Done", msg))
        except InterruptedError:
            self.log("Cancelled.")
        finally:
            self.after(0, lambda: self.set_busy(False))


if __name__ == "__main__":
    App().mainloop()
