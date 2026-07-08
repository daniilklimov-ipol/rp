# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for PyBrowser (Windows single-file .exe).

Bundles the full PyQt5 + QtWebEngine (Chromium) stack, including the
QtWebEngineProcess executable and its resources, into one PyBrowser.exe.
Build with:  pyinstaller pybrowser.spec
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# Pull in everything PyQt5 needs — QtWebEngine is picky, so collect it all.
for pkg in ("PyQt5",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PyQt6", "PySide2", "PySide6"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# One-file executable (everything unpacked to a temp dir at launch).
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="PyBrowser",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # no console window — it's a GUI app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
