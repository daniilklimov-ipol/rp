@echo off
REM Build PyBrowser.exe locally on Windows.
REM Requires Python 3.9+ on PATH.

python -m pip install --upgrade pip
pip install PyQt5==5.15.11 PyQtWebEngine==5.15.7 pyinstaller==6.11.1
pyinstaller --noconfirm pybrowser.spec

echo.
echo Done. Your browser is at: dist\PyBrowser.exe
pause
