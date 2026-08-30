@echo off
chcp 65001 > nul
title FinPlay ToDo

rem Prejdi do priecinka, v ktorom lezi tento subor
cd /d "%~dp0"

set "PYDIR=C:\venvs\finplay\Scripts"

if not exist "%PYDIR%\streamlit.exe" (
    echo.
    echo   [CHYBA] Nenasiel som Streamlit v: %PYDIR%
    echo.
    echo   Vytvor virtualne prostredie a nainstaluj balicky:
    echo.
    echo     python -m venv C:\venvs\finplay
    echo     C:\venvs\finplay\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

if not exist "app.py" (
    echo.
    echo   [CHYBA] Nenasiel som app.py v: %CD%
    echo   Tento .bat subor musi lezat v priecinku projektu.
    echo.
    pause
    exit /b 1
)

echo.
echo   FinPlay ToDo sa spusta...
echo.
echo   Prehliadac sa otvori sam na adrese http://localhost:8501
echo   Toto okno nechaj otvorene - kym bezi, bezi aj aplikacia.
echo   Ukoncis ho stlacenim Ctrl+C alebo zatvorenim tohto okna.
echo.

"%PYDIR%\streamlit.exe" run app.py

echo.
echo   Aplikacia sa ukoncila.
pause
