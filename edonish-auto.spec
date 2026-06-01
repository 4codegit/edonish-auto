# -*- mode: python ; coding: utf-8 -*-
"""
eDonish Auto — PyInstaller spec file
Builds: GUI executable with CustomTkinter + ALL DLLs

Fixes:
  - Includes Tkinter/Tcl/Tk DLLs (tcl86t.dll, tk86t.dll, _tkinter.pyd)
  - Includes Visual C++ Runtime DLLs (vcruntime140.dll, etc.)
  - Collects ALL customtkinter data files
  - Works on clean Windows without Python installed

Usage:
  python -m PyInstaller edonish-auto.spec --clean --noconfirm
"""
import sys
import os
import struct
from pathlib import Path

# ── Dynamically resolve customtkinter ──────────────────────────
ctk_path = None
try:
    import customtkinter as ctk
    ctk_path = Path(ctk.__path__[0])
except ImportError:
    print("WARNING: customtkinter not found, GUI build may fail!")

# ── Dynamically resolve tkinter / Tcl-Tk ───────────────────────
tkinter_path = None
tcl_path = None
tk_path = None
try:
    import tkinter
    tkinter_path = Path(tkinter.__file__).parent
    # Find Tcl/Tk library directory
    tcl_dir = tkinter_path / "tcl"
    if tcl_dir.exists():
        tcl_path = tcl_dir
    # Find DLLs directory (Windows)
    dll_dir = tkinter_path.parent / "DLLs"
    if not dll_dir.exists():
        # Try Python root / DLLs
        dll_dir = Path(sys.base_exec_prefix) / "DLLs"
except Exception:
    pass

block_cipher = None

# ── Collect all data files ──────────────────────────────────────
datas_list = []

# CustomTkinter assets (icons, themes, etc.)
if ctk_path and ctk_path.exists():
    # Collect ENTIRE customtkinter package
    datas_list.append((str(ctk_path), 'customtkinter'))

# Tcl/Tk library files (needed for tkinter on all platforms)
if tcl_path and tcl_path.exists():
    # Find tcl8.x and tk8.x directories
    for item in tcl_path.iterdir():
        if item.is_dir() and (item.name.startswith('tcl') or item.name.startswith('tk')):
            datas_list.append((str(item), f'tcl/{item.name}'))
            print(f"  Adding Tcl/Tk lib: {item.name}")

# ── Collect all binaries (DLLs, .pyd) ──────────────────────────
binaries_list = []

# Tkinter .pyd extension module
try:
    import _tkinter
    _tkinter_file = Path(_tkinter.__file__)
    binaries_list.append((str(_tkinter_file), '.'))
    print(f"  Adding _tkinter: {_tkinter_file.name}")
except (ImportError, AttributeError):
    pass

# On Windows: collect ALL DLLs from Python DLLs directory
if sys.platform == 'win32':
    dll_search_dirs = [
        Path(sys.base_exec_prefix) / "DLLs",
        Path(sys.base_exec_prefix),
    ]
    for dll_dir in dll_search_dirs:
        if not dll_dir.exists():
            continue
        for dll_file in dll_dir.iterdir():
            name_lower = dll_file.name.lower()
            # Include critical DLLs
            if any(name_lower.startswith(p) for p in [
                'tcl', 'tk',           # Tcl/Tk DLLs
                'vcruntime',            # Visual C++ Runtime
                'msvcp',                # MSVC Runtime
                'python3',              # Python library
                'python3xx',            # Python3xx.dll
                'libcrypto',            # OpenSSL
                'libssl',               # OpenSSL
                'libffi',               # FFI
                'sqlite3',              # SQLite
                'select',               # Select module
                'unicodedata',          # Unicode data
                '_ctypes',              # ctypes
                '_decimal',             # decimal
                '_hashlib',             # hashlib
                '_socket',              # socket
                '_bz2',                 # bz2
                '_lzma',                # lzma
                '_zlib',                # zlib
            ]):
                binaries_list.append((str(dll_file), '.'))
                print(f"  Adding DLL: {dll_file.name}")

# On Linux/macOS: find shared libraries
if sys.platform in ('linux', 'darwin'):
    import ctypes.util
    for lib_name in ['tcl', 'tk']:
        lib_path = ctypes.util.find_library(lib_name)
        if lib_path:
            binaries_list.append((lib_path, '.'))
            print(f"  Adding lib: {lib_path}")

# ── Analysis ────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[str(Path(sys.base_exec_prefix) / 'Lib' / 'site-packages')],
    binaries=binaries_list,
    datas=datas_list,
    hiddenimports=[
        # CustomTkinter
        'customtkinter',
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.core',
        'customtkinter.windows.widgets.core_widget_classes',
        'customtkinter.windows.ctk_input_dialog',
        'customtkinter.windows.ctk_tk',
        # Tkinter
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.colorchooser',
        'tkinter.font',
        'tkinter.ttk',
        '_tkinter',
        # Network
        'requests',
        'urllib3',
        'urllib3.util',
        'urllib3.util.retry',
        'certifi',
        'charset_normalizer',
        'idna',
        # System
        'darkdetect',
        'packaging',
        'json',
        'threading',
        'logging',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'PIL', 'scipy', 'pandas',
        'IPython', 'notebook', 'jupyter', 'selenium',
        'pytest', 'unittest', 'pydoc', 'pytz',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── Windows/Linux: single EXE with all DLLs embedded ────────────
if sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='edonish-auto',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,           # Don't strip on Windows — can break DLLs
        upx=False,             # UPX can corrupt DLLs on Windows
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,         # GUI mode — no console window
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )
else:
    # Linux: single binary
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='edonish-auto',
        debug=False,
        bootloader_ignore_signals=False,
        strip=True,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=None,
    )

# ── macOS: .app bundle ──────────────────────────────────────────
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='eDonish Auto.app',
        icon=None,
        bundle_identifier='tj.edonish.auto',
        info_plist={
            'CFBundleName': 'eDonish Auto',
            'CFBundleDisplayName': 'eDonish Auto',
            'CFBundleVersion': '2.1.0',
            'CFBundleShortVersionString': '2.1.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.13',
        },
    )
