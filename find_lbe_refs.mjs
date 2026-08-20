import fs from 'fs';

const p = 'C:\\Users\\86157\\AppData\\Local\\Programs\\QUANT PRO\\resources\\backend\\QUANT_PRO_backend\\_internal\\app_17beuetfu9m (2)\\dist\\assets\\index-B3WrOZ0j.js';
const c = fs.readFileSync(p, 'utf8');

// Lbe 所有引用
const idxs = [];
let i = -1;
while ((i = c.indexOf('Lbe', i + 1)) !== -1 && idxs.length < 20) idxs.push(i);
console.log('Lbe 引用:', idxs.join(', '));
for (const pos of idxs) {
  console.log(`\n@${pos}: ${c.substring(pos - 80, pos + 80)}`);
}

// $Y 所有引用
const idxs2 = [];
i = -1;
while ((i = c.indexOf('$Y', i + 1)) !== -1 && idxs2.length < 20) idxs2.push(i);
console.log('\n$Y 引用:', idxs2.join(', '));
for (const pos of idxs2) {
  console.log(`\n@${pos}: ${c.substring(pos - 60, pos + 60)}`);
}
