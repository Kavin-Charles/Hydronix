@echo off
REM Launch Streamlit web UI.
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
echo.
echo Opening Streamlit UI at http://localhost:8501 ...
streamlit run app.py %*
endlocal
