# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

project_dir = Path.cwd()
icon_path = project_dir / "assets" / "icon.icns"

added_files = [
    ("assets/styles.css", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/icon.icns", "assets"),
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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

app = BUNDLE(
    coll,
    name="Markdown Pretty Viewer.app",
    icon=str(icon_path),
    bundle_identifier="local.markdown-pretty-viewer",
    info_plist={
        "CFBundleName": "Markdown Pretty Viewer",
        "CFBundleDisplayName": "Markdown Pretty Viewer",
        "CFBundleShortVersionString": "1.1.0",
        "CFBundleVersion": "1.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
    },
)
