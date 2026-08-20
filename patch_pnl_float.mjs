import fs from 'fs';

const p = 'D:\\股票仪表盘\\app_17beuetfu9m (2)\\dist\\assets\\index-B3WrOZ0j.js';
let c = fs.readFileSync(p, 'utf8');
fs.copyFileSync(p, 'C:\\Users\\86157\\AppData\\Roaming\\TRAE SOLO CN\\ModularData\\ai-agent\\work-mode-projects\\6a719e82aba1f4ba68420467\\index_pnl_backup.js');

// 1. tbody 开头：计算浮动盈亏 fp（买入记录基于当前持仓）
const old1 = 'M.map(e=>{let t=A(e)===`etf`,n=e.amount-(e.pnl||0),r=e.direction===`卖出`&&n>0?(e.pnl||0)/n*100:null;return(0,H.jsxs)(`tr`,{className:`border-b border-border/20 hover:bg-accent/30 transition-colors`,children:[';
const new1 = 'M.map(e=>{let t=A(e)===`etf`,n=e.amount-(e.pnl||0),fp=(()=>{try{let a=JSON.parse(localStorage.getItem(`quant-sim-account`)||`null`),q=(a&&a.positions||[]).find(z=>z.code===e.code);if(!q||!q.costPrice)return null;return{amt:(q.currentPrice-q.costPrice)*e.shares,pct:(q.currentPrice-q.costPrice)/q.costPrice*100}}catch(_x){return null}})(),r=e.direction===`卖出`&&n>0?(e.pnl||0)/n*100:fp?fp.pct:null;return(0,H.jsxs)(`tr`,{className:`border-b border-border/20 hover:bg-accent/30 transition-colors`,children:[';

if (c.includes(old1)) {
  c = c.replace(old1, new1);
  console.log('1. tbody 浮动盈亏计算已注入');
} else {
  console.log('1. old1 未找到!');
}

// 2. 盈亏列：买入记录显示浮动盈亏金额
const old2 = 'children:e.direction===`卖出`?(e.pnl>=0?`+`:``)+e.pnl.toLocaleString(void 0,{maximumFractionDigits:0}):`-`}';
const new2 = 'children:e.direction===`卖出`?(e.pnl>=0?`+`:``)+e.pnl.toLocaleString(void 0,{maximumFractionDigits:0}):fp?(fp.amt>=0?`+`:``)+fp.amt.toLocaleString(void 0,{maximumFractionDigits:0}):`-`}';

if (c.includes(old2)) {
  c = c.replace(old2, new2);
  console.log('2. 盈亏列已支持浮动盈亏金额');
} else {
  console.log('2. old2 未找到!');
}

fs.writeFileSync(p, c);
console.log('写入完成, 新大小:', c.length);
