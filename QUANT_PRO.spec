# -*- mode: python ; coding: utf-8 -*-
"""QUANT PRO 后端打包配置 (PyInstaller)
用法: pyinstaller QUANT_PRO.spec
输出: dist/backend/QUANT_PRO_backend/QUANT_PRO_backend.exe (onedir 模式)
"""
import os

FRONTEND_DIST = r"D:\股票仪表盘\app_17beuetfu9m (2)\dist"
DATAS_DIR = r"D:\股票仪表盘\data"

a = Analysis(
    ["D:\\股票仪表盘\\app.py"],
    pathex=["D:\\股票仪表盘"],
    binaries=[],
    datas=[
        (FRONTEND_DIST, "app_17beuetfu9m (2)/dist"),
        (DATAS_DIR, "data"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "anyio",
        "anyio._backends._asyncio",
        "anyio._backends._trio",
        "anyio._core._asyncio_stream",
        "fastapi",
        "pydantic",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除 app.py 不需要的大依赖（matplotlib 等会拖慢启动并可能触发 rthook 异常）
    excludes=[
        # akshare 依赖 pandas，已被排除；桌面版 get_stock_pool 走新浪 HTTP 兜底
        "akshare",
        "matplotlib",
        "matplotlib.pyplot",
        "pandas",
        "scipy",
        "PIL",
        "tkinter",
        "PySide6",
        "PyQt5",
        "IPython",
        "jupyter",
        "notebook",
        "pytest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QUANT_PRO_backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="QUANT_PRO_backend",
)
