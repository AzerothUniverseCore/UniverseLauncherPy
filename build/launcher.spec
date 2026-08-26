# -*- mode: python ; coding: utf-8 -*-
"""
launcher.spec
-------------
Spec PyInstaller pour compiler AzerothUniverseLauncher.exe sous Windows.

Utilisation (depuis la racine du projet, PAS depuis build/) :
    pyinstaller build/launcher.spec

Voir build/BUILD_INSTRUCTIONS.md pour la procedure complete (creation de
l'environnement virtuel, placement de tools/UnRAR.exe, etc).
"""

import os

block_cipher = None
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(SPEC), ".."))

datas = [
    (os.path.join(PROJECT_ROOT, "manifest.json"), "."),
    (os.path.join(PROJECT_ROOT, "assets"), "assets"),
    (os.path.join(PROJECT_ROOT, "tools"), "tools"),
]

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AzerothUniverseLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(PROJECT_ROOT, "assets", "icon.ico"),
)
