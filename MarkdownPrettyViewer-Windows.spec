# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path.cwd()
icon_path = project_dir / "assets" / "icon.ico"

added_files = [
    ("assets/styles.css", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/icon.ico", "assets"),
    ("templates/document.html", "templates"),
]

a = Analysis(
    ["app.py"],
    pathex=[str(project_dir)],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "markdown.extensions.extra",
        "markdown.extensions.sane_lists",
        "markdown.extensions.toc",
        "pymdownx.tasklist",
        "pymdownx.superfences",
        "pymdownx.highlight",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Markdown Pretty Viewer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Markdown Pretty Viewer",
)
