# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


project_root = Path.cwd()
if not (project_root / "operator_assist.py").exists():
    project_root = Path(__file__).resolve().parents[2]

datas = [
    (str(project_root / "assets" / "logo-enot.png"), "assets"),
    (str(project_root / "assets" / "logo-enot-72.png"), "assets"),
    (str(project_root / "assets" / "logo-enot-96.png"), "assets"),
    (str(project_root / "assets" / "logo-enot-128.png"), "assets"),
    (str(project_root / "assets" / "logo-enot-256.png"), "assets"),
    (str(project_root / "assets" / "operator_assist.ico"), "assets"),
]
datas += collect_data_files("vosk")
datas += collect_data_files("soundcard")

hiddenimports = [
    "operator_assist_chat_bridge_v5_base",
    "operator_assist_chat_bridge_v3_base",
    "operator_assist_runtime.base_runtime",
    "operator_assist_runtime.runtime_paths",
    "operator_assist_runtime.technical_terms",
    "operator_assist_runtime.text_utils",
]
hiddenimports += collect_submodules("soundcard")

hookspath = [
    str(project_root / "vendor" / "soundcard" / "__pyinstaller"),
    str(project_root / "vendor" / "numpy" / "_pyinstaller"),
]

excludes = [
    "pytest",
    "tkinter.test",
    "numpy.tests",
    "numpy._pyinstaller.tests",
]

a = Analysis(
    [str(project_root / "operator_assist.py")],
    pathex=[str(project_root), str(project_root / "vendor")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OPERATOR_ASSIST",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(project_root / "assets" / "operator_assist.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OPERATOR_ASSIST",
)
