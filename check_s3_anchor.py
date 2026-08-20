# -*- coding: utf-8 -*-
base = open(r'C:\Users\86157\AppData\Local\Programs\QUANT PRO\resources\backend\QUANT_PRO_backend\_internal\app_17beuetfu9m (2)\dist\assets\index-B3WrOZ0j.js', encoding='utf-8').read()

# 分解 old3 逐段测试
parts = {
  'A': "children:[e.relatedStock,`（`,e.stockCode,`）· `,e.stockIndustry]",
  'B': "])]})]})},",
  'C': "(0,H.jsxs)(`div`,{className:`border border-border/20 rounded-lg overflow-hidden`",
}
for k, v in parts.items():
    print(f'{k} in base: {v in base}')

# 完整 old3
old3_full = "children:[e.relatedStock,`（`,e.stockCode,`）· `,e.stockIndustry]})]})]})},(0,H.jsxs)(`div`,{className:`border border-border/20 rounded-lg overflow-hidden`"
print('完整 old3 in base:', old3_full in base)

# 对比字符
i = base.find('e.stockIndustry')
seg = base[i:i+95]
print('文件:', repr(seg))
print('old3:', repr(old3_full[:95]))
