# -*- coding: utf-8 -*-
# 提取 bisect_news.py 中 step3 的 new3，检查括号平衡
import re

src = open(r'C:\Users\86157\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6a719e82aba1f4ba68420467\bisect_news.py', encoding='utf-8').read()

# 提取 new3 字符串（step3 函数内 new = (...)
m = re.search(r'def step3.*?new = \((.*?)\)\n    assert old', src, re.S)
if not m:
    print('new3 未提取到')
else:
    s = m.group(1)
    # 括号平衡（忽略字符串内）
    bal = 0
    for ch in s:
        if ch == '(': bal += 1
        elif ch == ')': bal -= 1
    print('new3 括号平衡:', bal, '长度:', len(s))
    # 检查关键片段
    print('尾部:', repr(s[-150:]))
