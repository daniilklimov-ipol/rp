@echo off
REM Build YouTubeWatchPredictor.exe locally on Windows.
REM Requires Python 3.10+ on PATH.

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller==6.11.1
pyinstaller --noconfirm ytpredictor.spec

echo.
echo Done. The app is at: dist\YouTubeWatchPredictor.exe
pause
