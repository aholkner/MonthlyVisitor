# -*- mode: python -*-
a = Analysis(['MonthlyVisitor.py'],
             pathex=['MonthlyVisitor'],
             hiddenimports=[],
             hookspath=None,
             runtime_hooks=None)
pyz = PYZ(a.pure)
res_tree = Tree('res', prefix='res')
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          res_tree,
          name='MonthlyVisitor.exe',
          debug=False,
          strip=None,
          upx=True,
          console=False)
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               #res_tree,
               strip=None,
               upx=True,
               name='dist/MonthlyVisitor')
app = BUNDLE(coll,
             name='MonthlyVisitor.app',
             icon=None)