# -*- mode: python ; coding: utf-8 -*-
"""
eDonish Auto CLI — PyInstaller spec file
Builds: CLI executable (headless, no GUI dependencies)

Includes all necessary DLLs for Windows compatibility.

Usage:
  python -m PyInstaller edonish-auto-cli.spec --clean --noconfirm
"""
import sys
from pathlib import Path

block_cipher = None

# ── Collect Windows DLLs ────────────────────────────────────────
binaries_list = []
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
                'vcruntime', 'msvcp',
                'python3', 'libcrypto', 'libssl',
                'libffi', 'sqlite3', 'select',
                'unicodedata', '_ctypes', '_decimal',
                '_hashlib', '_socket', '_bz2',
                '_lzma', '_zlib',
            ]):
                binaries_list.append((str(dll_file), '.'))

# ── Analysis ────────────────────────────────────────────────────
a = Analysis(
    ['main_cli.py'],
    pathex=[str(Path(sys.base_exec_prefix) / 'Lib' / 'site-packages')],
    binaries=binaries_list,
    datas=[],
    hiddenimports=[
        'requests',
        'urllib3',
        'urllib3.util',
        'certifi',
        'charset_normalizer',
        'idna',
        'json',
        'threading',
        'logging',
        'concurrent.futures',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'customtkinter', 'tkinter', '_tkinter',
        'matplotlib', 'numpy', 'PIL', 'scipy', 'pandas',
        'IPython', 'notebook', 'jupyter', 'selenium',
        'darkdetect', 'packaging', 'pytz',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ── EXE ─────────────────────────────────────────────────────────
if sys.platform == 'win32':
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
        strip=False,         # Don't strip on Windows
        upx=False,           # UPX can break DLLs
        upx_exclude=[],
        runtime_tmpdir=None,
        console=True,        # CLI mode — show console
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
else:
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
        console=True,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
