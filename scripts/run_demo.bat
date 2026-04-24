@echo off
REM Full CLI demo: box barge + KCS with PDF + JSON artefacts in output/.
setlocal
cd /d "%~dp0\.."
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist output mkdir output

echo.
echo === Box Barge - quick IMO sweep ===
python main.py samples\box_barge.json --imo --angles "0:60:10" --no-plot ^
    --save output\box_barge.json

echo.
echo === Wigley Hull - with trim solver ===
python main.py samples\wigley.json --imo --angles "0:60:5" --no-plot ^
    --trim 2300,50 --save output\wigley.json

echo.
echo === KCS Containership - full PDF report ===
python main.py samples\kcs_real.json --draft 10.8 --KG 13.5 --rho 1.025 ^
    --angles "0:60:5" --imo --weather --no-plot ^
    --save output\kcs_results.json ^
    --report output\kcs_report.pdf

echo.
echo  ======================================================
echo   Artefacts written to output\ :
dir /b output
echo  ======================================================
endlocal
