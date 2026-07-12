@echo off
REM Build YouTubeWatchPredictor.exe locally on Windows.
REM Requires Python 3.10+ on PATH.

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install --upgrade pyinstaller==6.11.1 "pyinstaller-hooks-contrib>=2024.10"
pyinstaller --noconfirm ytpredictor.spec

echo.
echo Smoke-testing the exe...
dist\YouTubeWatchPredictor.exe --selfcheck
if errorlevel 1 (
    echo.
    echo BUILD PRODUCED A BROKEN EXE - see selfcheck_error.log
    pause
    exit /b 1
)

echo.
echo Done. The app is at: dist\YouTubeWatchPredictor.exe
pause
