@echo off
REM Validation suite: analytical benchmarks + KCS regression.
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
echo.
echo === pytest ===
python -m pytest tests/ -v
echo.
echo === benchmark script (verbose numbers) ===
python tests\test_benchmarks.py
endlocal
