import fs from 'fs';

const file = 'D:\\股票仪表盘\\app_17beuetfu9m (2)\\src\\components\\Header.tsx';
let h = fs.readFileSync(file, 'utf8');
const original = h;

// ---- 1. 确保 lucide-react 导入包含 Bot ----
// 归一化：把 lucide-react 的导入块提取出来，补上 Bot
const importRe = /import \{\s*([\s\S]*?)\s*\} from 'lucide-react';/;
const m = h.match(importRe);
if (!m) {
  console.log('ERROR: lucide import not found');
  process.exit(1);
}
const names = m[1].split(',').map(s => s.trim()).filter(Boolean);
if (!names.includes('Bot')) {
  names.push('Bot');
}
// 保持原有换行风格：每行多个，简单按 6 个一行排版
let line = 'import {';
let lines = [];
let count = 0;
for (const n of names) {
  if (count === 0) {
    line = 'import {\n  ' + n;
    count = 1;
  } else if (count < 5) {
    line += ', ' + n;
    count++;
  } else {
    line += ',\n  ' + n;
    count = 1;
  }
}
line += '\n} from \'lucide-react\';';
const newImport = line;

// 用新导入替换原导入块（保留原缩进上下文：行首可能有空格）
const indentMatch = h.match(/^(\s*)import \{/m);
const indent = indentMatch ? indentMatch[1] : '';
const newImportIndented = newImport.split('\n').map(l => (l === "} from 'lucide-react';" ? l : l)).join('\n');

h = h.replace(importRe, newImportIndented);

// ---- 2. 确保 NAV_ITEMS 含 /chat ----
if (!h.includes("path: '/chat'")) {
  // 在 watchlist 项后插入
  const watchlistRe = /(\{\s*path: '\/watchlist',\s*label: '自选股',\s*icon: Star\s*\},?)/;
  if (watchlistRe.test(h)) {
    h = h.replace(watchlistRe, "$1\n  { path: '/chat', label: 'Hermes 助手', icon: Bot },");
    console.log('nav item added');
  } else {
    console.log('ERROR: watchlist anchor not found');
    process.exit(1);
  }
} else {
  console.log('nav item already present');
}

fs.writeFileSync(file, h, 'utf8');
console.log('Header.tsx written');

// ---- 验证 ----
const check = fs.readFileSync(file, 'utf8');
console.log('has Bot import:', check.includes('Bot'));
console.log('has /chat nav:', check.includes("path: '/chat'"));
console.log('--- lines 3-18 ---');
check.split('\n').slice(2, 18).forEach(l => console.log(l));
