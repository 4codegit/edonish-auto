# -*- mode: python ; coding: utf-8 -*-
"""
eDonish Auto — PyInstaller spec file
Builds: GUI executable with CustomTkinter

Usage:
  python -m PyInstaller edonish-auto.spec --clean --noconfirm
"""
import sys
import os
import importlib
from pathlib import Path

# Dynamically find CustomTkinter path
try:
    import customtkinter as ctk
    ctk_path = Path(ctk.__path__[0])
except ImportError:
    ctk_path = None
    print("WARNING: customtkinter not found, GUI build may fail!")

block_cipher = None

# Build datas list
datas_list = []
if ctk_path and ctk_path.exists():
    datas_list.append((str(ctk_path / 'assets'), 'customtkinter/assets'))
    if (ctk_path / 'windows').exists():
        datas_list.append((str(ctk_path / 'windows'), 'customtkinter/windows'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'customtkinter',
        'tkinter',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'darkdetect',
        'packaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'numpy', 'PIL', 'scipy', 'pandas',
        'IPython', 'notebook', 'jupyter', 'selenium',
        'pytest', 'unittest', 'pydoc',
    ],
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
    name='edonish-auto',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # GUI mode — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # Add .ico path here for Windows icon
)

# For macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='eDonish Auto.app',
        icon=None,       # Add .icns path here for macOS icon
        bundle_identifier='tj.edonish.auto',
        info_plist={
            'CFBundleName': 'eDonish Auto',
            'CFBundleDisplayName': 'eDonish Auto',
            'CFBundleVersion': '2.0.0',
            'CFBundleShortVersionString': '2.0.0',
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '10.13',
        },
    )
