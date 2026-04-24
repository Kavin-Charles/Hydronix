@echo off
REM Headless capsize-simulator demo on KCS (rogue wave strike).
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
python scripts\capsize_demo.py
endlocal
