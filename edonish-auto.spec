# -*- mode: python ; coding: utf-8 -*-
"""
eDonish Auto — PyInstaller spec file
Builds: GUI executable with CustomTkinter + ALL DLLs

Fixes:
  - Includes Tkinter/Tcl/Tk DLLs for Windows
  - Includes Visual C++ Runtime DLLs
  - Collects ALL customtkinter data files
  - Works on clean Windows without Python installed

Usage:
  python -m PyInstaller edonish-auto.spec --clean --noconfirm
"""
import sys
import os
from pathlib import Path

# ── Dynamically resolve customtkinter ──────────────────────────
ctk_path = None
try:
    import customtkinter as ctk
    ctk_path = Path(ctk.__path__[0])
except ImportError:
    print("WARNING: customtkinter not found, GUI build may fail!")

block_cipher = None

# ── Collect all data files ──────────────────────────────────────
datas_list = []

# CustomTkinter — collect ENTIRE package
if ctk_path and ctk_path.exists():
    datas_list.append((str(ctk_path), 'customtkinter'))
    print(f"  Adding CTk: {ctk_path}")

# ── Collect binaries (Windows DLLs) ────────────────────────────
binaries_list = []

# Windows: collect ALL necessary DLLs from Python installation
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
            if any(name_lower.startswith(p) for p in [
                'tcl', 'tk', 'vcruntime', 'msvcp',
                'python3', 'libcrypto', 'libssl',
                'libffi', 'sqlite3', 'select',
                'unicodedata', '_ctypes', '_decimal',
                '_hashlib', '_socket', '_bz2',
                '_lzma', '_zlib',
            ]):
                binaries_list.append((str(dll_file), '.'))
                print(f"  Adding DLL: {dll_file.name}")

# ── Hidden imports (platform-safe) ─────────────────────────────
hidden_imports = [
    'customtkinter',
    'tkinter',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.font',
    'tkinter.ttk',
    '_tkinter',
    'requests',
    'urllib3',
    'urllib3.util',
    'certifi',
    'charset_normalizer',
    'idna',
    'darkdetect',
    'packaging',
    'json',
    'threading',
    'logging',
    'concurrent.futures',
]

# Windows-only CTk modules
if sys.platform == 'win32':
    hidden_imports.extend([
        'customtkinter.windows',
        'customtkinter.windows.widgets',
        'customtkinter.windows.widgets.core',
        'customtkinter.windows.widgets.core_widget_classes',
        'customtkinter.windows.ctk_input_dialog',
        'customtkinter.windows.ctk_tk',
    ])

# ── Analysis ────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries_list,
    datas=datas_list,
    hiddenimports=hidden_imports,
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

# ── EXE ─────────────────────────────────────────────────────────
is_windows = sys.platform == 'win32'

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
    strip=not is_windows,
    upx=not is_windows,
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
