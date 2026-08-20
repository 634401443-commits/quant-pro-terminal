# -*- coding: utf-8 -*-
c = open(r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\assets\index-B3WrOZ0j.js', encoding='utf-8').read()

# 找 Dxe 使用（渲染组件）
idxs = []
i = -1
while True:
    i = c.find('Dxe(', i + 1)
    if i < 0: break
    idxs.append(i)
print('Dxe( @', idxs)
for i in idxs:
    is_def = c[max(0, i-9):i] == 'function '
    tag = '[定义]' if is_def else '[使用]'
    print(f'{tag} @{i}:', c[max(0,i-60):i+120])
    print()

# Txe 调用处（1562890）所在组件 —— 找它属于哪个页面
i = 1562890
print('=== Txe 调用上下文 ===')
print(c[i-500:i+500])
