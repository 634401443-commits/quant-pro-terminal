import subprocess, sys, os

py = r'C:\Users\86157\AppData\Local\Programs\Python\Python311\python.exe'
exe = r'C:\Users\86157\AppData\Local\Programs\QUANT PRO\resources\backend\QUANT_PRO_backend\QUANT_PRO_backend.exe'

# 列出归档内容（PYZ 里的模块需要通过 -r 递归）
out = subprocess.run([py, '-m', 'PyInstaller.utils.cliutils.archive_viewer', '-l', exe],
                     capture_output=True, text=True, encoding='utf-8', errors='replace')
print('=== 顶层条目 ===')
print(out.stdout)

# 递归查看 PYZ
out2 = subprocess.run([py, '-m', 'PyInstaller.utils.cliutils.archive_viewer', '-r', '-l', exe],
                      capture_output=True, text=True, encoding='utf-8', errors='replace')
print('=== 递归（PYZ 内模块）筛选 ===')
for line in out2.stdout.splitlines():
    l = line.strip()
    if any(k in l.lower() for k in ['chat', 'dev', 'proxy', 'share', 'app', 'tencent', 'kline', 'simulation', 'factor', 'fetch']):
        print(l[:150])
