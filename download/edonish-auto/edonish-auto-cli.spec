# -*- mode: python ; coding: utf-8 -*-
"""
eDonish Auto CLI — PyInstaller spec file
Builds: CLI executable (headless, no GUI dependencies)

Usage:
  python -m PyInstaller edonish-auto-cli.spec --clean --noconfirm
"""
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main_cli.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'customtkinter', 'tkinter', 'matplotlib', 'numpy', 'PIL',
        'scipy', 'pandas', 'IPython', 'notebook', 'jupyter', 'selenium',
        'darkdetect', 'packaging',
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
    name='edonish-auto-cli',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,        # CLI mode — show console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
