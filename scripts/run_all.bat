@echo off
REM Full pipeline: setup -> tests -> CLI demo -> capsize demo.
setlocal
cd /d "%~dp0\.."
call scripts\setup.bat        || exit /b 1
call scripts\run_tests.bat    || exit /b 1
call scripts\run_demo.bat     || exit /b 1
call scripts\run_capsize.bat  || exit /b 1
echo.
echo  ===========================================================
echo   Full pipeline complete. Launch UI with:
echo       scripts\run_streamlit.bat
echo  ===========================================================
endlocal
