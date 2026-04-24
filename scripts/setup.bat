@echo off
REM =====================================================================
REM HydroHackathon - one-shot setup (Windows cmd)
REM Creates .venv, installs all deps, regenerates sample hulls.
REM =====================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0\.."

echo.
echo [1/4] Python version check
python --version || (echo Python not on PATH. Install 3.11 or 3.12. & exit /b 1)

echo.
echo [2/4] Create virtual environment at .venv
if not exist .venv (
    python -m venv .venv
) else (
    echo    .venv already exists - skipping
)

echo.
echo [3/4] Install dependencies
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo [4/4] Generate sample offset files
python samples\generate_samples.py
python samples\build_kcs.py

echo.
echo  ======================================================
echo   Setup complete. Activate with:
echo       .venv\Scripts\activate.bat
echo   Then run:
echo       scripts\run_tests.bat      (validation suite)
echo       scripts\run_demo.bat       (CLI demo)
echo       scripts\run_streamlit.bat  (web UI)
echo  ======================================================
endlocal
