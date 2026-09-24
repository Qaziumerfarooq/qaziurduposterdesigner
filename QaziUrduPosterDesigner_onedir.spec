# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

rembg_datas, rembg_binaries, rembg_hidden = collect_all('rembg')
ort_datas, ort_binaries, ort_hidden = collect_all('onnxruntime')
sp_datas, sp_binaries, sp_hidden = collect_all('setuptools')
pkg_datas, pkg_binaries, pkg_hidden = collect_all('pkg_resources')
hb_datas, hb_binaries, hb_hidden = collect_all('uharfbuzz')
ft_datas, ft_binaries, ft_hidden = collect_all('freetype')

import os

a = Analysis(
    ['qazi_poster_app.py'],
    pathex=[],
    binaries=rembg_binaries + ort_binaries + sp_binaries + pkg_binaries + hb_binaries + ft_binaries,
    datas=[('fonts', 'fonts'),
           ('icon.png', '.'),
           ('urdu_render.py', '.'),
           (r'C:\Users\Qaziumerfarooq\.rembg\models\u2netp\u2netp.onnx', 'models/u2netp')] + rembg_datas + ort_datas + sp_datas + pkg_datas + hb_datas + ft_datas,
    hiddenimports=(rembg_hidden + ort_hidden + sp_hidden + pkg_hidden + hb_hidden + ft_hidden +
                   ['rembg', 'rembg.bg', 'rembg.sessions', 'rembg.session_factory',
                    'rembg.sessions.load_models', 'onnxruntime',
                    'setuptools', 'pkg_resources',
                    'urdu_render', 'uharfbuzz', 'freetype']),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='QaziUrduPosterDesigner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='QaziUrduPosterDesigner_Folder',
)