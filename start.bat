@echo off
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw unity_extractor.py) || (python unity_extractor.py & pause)
