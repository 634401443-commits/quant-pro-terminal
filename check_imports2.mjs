import fs from 'fs';

const newIndex = 'D:\\股票仪表盘\\app_17beuetfu9m (2)\\dist\\assets\\index-D8PIyhaO.js';
const oldIndex = 'C:\\Users\\86157\\AppData\\Local\\Programs\\QUANT PRO\\resources\\backend\\QUANT_PRO_backend\\_internal\\app_17beuetfu9m (2)\\dist\\assets\\index-B3WrOZ0j.js';

const n = fs.readFileSync(newIndex, 'utf8');
const o = fs.readFileSync(oldIndex, 'utf8');

console.log('=== 新 index import 语句 ===');
const nImp = n.match(/import\{[^}]*\}from"[^"]+"/g) || [];
console.log(nImp.slice(0, 15).join('\n'));

console.log('\n=== 打包版 index import 语句 ===');
const oImp = o.match(/import\{[^}]*\}from"[^"]+"/g) || [];
console.log(oImp.slice(0, 15).join('\n'));

console.log('\n=== 新 index 开头 500 ===');
console.log(n.substring(0, 500));
