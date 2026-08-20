import fs from 'fs';

const file = 'D:\\股票仪表盘\\app_17beuetfu9m (2)\\dist\\index.html';
let html = fs.readFileSync(file, 'utf8');

const replacements = {
  '{{appId}}': '',
  '{{userId}}': '',
  '{{tenantId}}': '',
  '{{userName}}': '',
  '{{csrfToken}}': '',
  '{{environment}}': 'production',
  '{{basename}}': '',
  '{{appName}}': 'QUANT PRO',
  '{{appAvatar}}': '/favicon.svg',
  '{{{appAvatar}}}': '',
  '{{appDescription}}': '',
};

let count = 0;
for (const [k, v] of Object.entries(replacements)) {
  if (html.includes(k)) {
    html = html.split(k).join(v);
    count++;
  }
}
html = html.replace(/<title>[^<]*<\/title>/, '<title>QUANT PRO - 量化策略终端</title>');
fs.writeFileSync(file, html, 'utf8');
console.log('placeholders replaced:', count);
console.log('Contains {{:', html.includes('{{'));
console.log('title ok:', html.includes('<title>QUANT PRO - 量化策略终端</title>'));
