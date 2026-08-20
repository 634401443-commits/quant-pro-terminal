# -*- coding: utf-8 -*-
import re

src = open(r'C:\Users\86157\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a719e82aba1f4ba68420467\patch_news2.py', encoding='utf-8').read()
m = re.search(r'new3 = \((.*?)\)\nassert old3', src, re.S)
s = m.group(1)
print('new3 长度:', len(s))

# 括号平衡
bal = 0
for ch in s:
    if ch == '(': bal += 1
    elif ch == ')': bal -= 1
print('括号平衡:', bal)

# 反引号配对（近似，忽略嵌套）
print('反引号数:', s.count('`'))
print('${ 数:', s.count('${'))
# 关键片段
for kw in ['推理逻辑', 'text-right', '相关快讯', '（另有']:
    i = s.find(kw)
    if i >= 0:
        print(f'\n[{kw}] @{i}:', repr(s[max(0,i-60):i+120]))
