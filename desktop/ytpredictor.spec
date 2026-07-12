# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for YouTubeWatchPredictor.exe (Windows single-file).

Bundles the FastAPI/uvicorn local server, scikit-learn model, SQLite/SQLAlchemy
storage, and the VADER sentiment lexicon data into one executable.

Build with:  pyinstaller ytpredictor.spec
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

for pkg in ("sklearn", "scipy", "numpy", "uvicorn", "vaderSentiment", "fastapi", "pydantic"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    "sqlalchemy.dialects.sqlite",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    # scipy ships a handful of Cython "shared utility" extension modules that
    # are only ever loaded implicitly (via cimport, not a Python-level
    # `import`), so PyInstaller's static source scan misses them even with
    # collect_all("scipy") above. Without these, a frozen exe crashes on
    # startup with "ModuleNotFoundError: No module named 'scipy...cyutility'".
    "scipy._lib.cyutility",
    "scipy._lib._cyutility",
    "scipy._cyutility",
    "scipy._lib._ccallback_c",
    "scipy._lib._ccallback",
    "scipy.special.cython_special",
    "scipy.special._cdflib",
]

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
    excludes=["tkinter.test", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="YouTubeWatchPredictor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,          # GUI app, no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
