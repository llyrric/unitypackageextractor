# Unity Package Extractor

A small desktop tool that unpacks `.unitypackage` files into a normal folder tree. You don't need Unity installed.

It was made for bringing Unity Asset Store assets into **Godot 4**, but the output is plain files and folders, so you can use it with any engine or tool.

## Features

- Extract one or many packages in a single run. Each one goes into its own subfolder named after the package.
- Opens `.unitypackage`, `.unitypackage.gz` and `*_unitypackage.gz` files, including Asset Store downloads with headers that Python's normal tar streaming can't read.
- Rebuilds each asset's original project path from the GUID-named entries inside the package.
- Optionally removes the leading `Assets/` folder (on by default).
- Optionally keeps Unity `.meta` files (off by default, since Godot doesn't need them).
- Cleans file names that Windows doesn't allow (`<>:"|?*`, control characters, trailing dots and spaces) and blocks `..` path traversal.
- Shows a progress bar and a log, and you can cancel a run partway through.

## Requirements

| Requirement | Notes |
|---|---|
| **Python 3.6 or newer** | Python 3.10+ is recommended. Developed with Python 3.13. |
| **Tkinter** | Python's built-in GUI toolkit. Most Python installs include it (see below). |

There are **no third-party packages**: no `pip install`, no `requirements.txt`. Everything it uses (`tkinter`, `tarfile`, `gzip`, `shutil`, `threading`, `re`, `os`) is in the Python standard library.

## Installation

### 1. Get the code

```bash
git clone https://github.com/llyrric/unitypackageextractor.git
```

Or download the ZIP from the GitHub page (**Code → Download ZIP**) and unzip it.

### 2. Install Python (with Tkinter)

**Windows**

1. Download Python from <https://www.python.org/downloads/windows/>.
2. In the installer, tick **"Add python.exe to PATH"**.
3. Leave **"tcl/tk and IDLE"** ticked (it is by default). This is what installs Tkinter.

Or install it with winget:

```bash
winget install Python.Python.3.13
```

**macOS**

The python.org installer includes Tkinter. If you use Homebrew, install Tk support separately:

```bash
brew install python python-tk
```

**Linux**

Many distributions ship Tkinter as a separate package:

```bash
# Debian / Ubuntu
sudo apt install python3 python3-tk

# Fedora
sudo dnf install python3 python3-tkinter

# Arch
sudo pacman -S python tk
```

### 3. Check that Tkinter works

```bash
python -m tkinter
```

A small test window should appear. If you see `ModuleNotFoundError: No module named 'tkinter'`, go back to step 2 and install the Tk package for your platform. On macOS and Linux, use `python3` in place of `python` if needed.

## Usage

### Start the app

- **Windows:** double-click `start.bat`. It runs the app with `pythonw`, so no console window stays open. If `pythonw` isn't on your PATH, it falls back to `python` and keeps the console open so you can read any errors.
- **Any platform:**

  ```bash
  python unity_extractor.py
  ```

### Extract packages

1. Next to **Unity packages**, click **Browse...** and pick one or more packages. **Add...** adds more to the list, and **Remove** takes the selected ones off it.
2. Choose an **Output folder**. Browse fills it in with the folder of the first package you picked.
3. Set the options:
   - **Strip leading 'Assets/' folder**: on by default.
   - **Keep Unity .meta files (not needed for Godot)**: off by default.
4. Click **Extract**. The log lists each file as it's written, then a total for each package, e.g. `Done: 120 files extracted (3 skipped).` Click **Cancel** to stop.

### Output layout

```
<output folder>/
└── <package name>/
    ├── Models/
    │   └── Tree.fbx
    ├── Textures/
    │   └── Tree_Albedo.png
    └── ...
```

With **Strip leading 'Assets/'** turned off, the files sit under `<package name>/Assets/...` instead.

### Using the files in Godot 4

Copy the extracted package folder (or the parts you need) into your Godot project folder. Godot imports supported formats (`.fbx`, `.gltf`/`.glb`, `.obj`, `.png`, `.jpg`, `.wav`, `.ogg`, etc.) on its own. Unity-only files such as `.prefab`, `.mat`, `.unity`, `.asset` and `.cs` scripts are extracted as-is, but Godot can't use them directly.

## How it works

A `.unitypackage` is a gzipped tar archive. Inside it, every asset sits in a folder named after its GUID:

```
<guid>/asset       the file's contents
<guid>/pathname    the original path in the Unity project, e.g. Assets/Models/Tree.fbx
<guid>/asset.meta  Unity's import settings
```

The tool streams the archive into a temporary `.unitypkg_*` folder inside the output folder. It then reads each `pathname`, cleans it up, and moves the matching `asset` (and, if you asked for it, the `.meta`) into place. The temporary folder is always deleted afterward, even when a run fails or you cancel it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `start.bat` flashes and closes, or says Python isn't found | Python isn't on your PATH. Reinstall it with **"Add python.exe to PATH"** ticked, or run `python unity_extractor.py` from a terminal. |
| `No module named 'tkinter'` | Install the Tk package for your platform (see [Installation](#2-install-python-with-tkinter)). |
| The log says some entries were "skipped" | Those GUID entries have no usable `pathname` (none at all, or one that is empty after cleaning), so there's nowhere to put them. A few are normal. |
| A package fails with an error | The file may be damaged or not really a Unity package. Try downloading it again. Other packages in the same run still extract. |
