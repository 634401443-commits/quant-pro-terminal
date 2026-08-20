import { spawn } from 'child_process';

const edge = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const userData = 'C:\\Users\\86157\\AppData\\Local\\Temp\\edge_cdp_wscreen';
const proc = spawn(edge, [
  '--headless', '--disable-gpu',
  '--remote-debugging-port=9270',
  `--user-data-dir=${userData}`,
  '--no-first-run', '--no-default-browser-check', '--disable-sync',
  '--disable-extensions', '--disable-background-networking',
  'about:blank'
], { stdio: 'ignore' });

async function getPage() {
  for (let i = 0; i < 20; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9270/json');
      const tabs = await res.json();
      const page = tabs.find(t => t.type === 'page');
      if (page) return page;
    } catch (e) {}
    await new Promise(r => setTimeout(r, 500));
  }
  return null;
}

setTimeout(async () => {
  try {
    const page = await getPage();
    if (!page) { console.log('NO PAGE'); process.exit(1); }
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise(r => ws.onopen = r);
    let msgId = 0;
    const pending = new Map();
    const errors = [];
    const logs = [];
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
      if (m.method === 'Runtime.exceptionThrown') {
        const d = m.params.exceptionDetails;
        errors.push((d.exception?.description || d.text || '').substring(0, 400));
      }
      if (m.method === 'Runtime.consoleAPICalled') {
        const txt = (m.params.args || []).map(a => a.value || a.description || '').join(' ');
        if (m.params.type === 'error') logs.push('CONSOLE-ERR: ' + txt.substring(0, 300));
      }
    };
    const send = (method, params = {}) => new Promise(r => {
      const id = ++msgId;
      pending.set(id, r);
      ws.send(JSON.stringify({ id, method, params }));
    });
    await send('Runtime.enable');
    await send('Page.enable');
    const failed = [];
    const origFetch = globalThis.fetch;
    // 监听请求失败
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result); pending.delete(m.id); }
      if (m.method === 'Runtime.exceptionThrown') {
        const d = m.params.exceptionDetails;
        errors.push((d.exception?.description || d.text || '').substring(0, 400));
      }
      if (m.method === 'Network.loadingFailed') {
        failed.push(m.params.errorText + ' @' + (m.params.requestId || ''));
      }
    };
    await send('Network.enable');
    await send('Page.navigate', { url: 'http://localhost:8000/simulation' });
    await new Promise(r => setTimeout(r, 15000));
    const r = await send('Runtime.evaluate', {
      expression: `JSON.stringify({
        rootChildren: document.getElementById('root') ? document.getElementById('root').children.length : -1,
        bodyText: (document.body.innerText || '').substring(0, 120),
        url: location.href
      })`,
      returnByValue: true,
    });
    console.log('页面状态:', r.result.value);
    console.log('JS 异常:', errors.length ? errors.slice(0, 5) : '无');
    console.log('加载失败:', failed.length ? failed.slice(0, 10) : '无');
    process.exit(0);
  } catch (e) {
    console.log('PROBE ERR:', e.message);
    process.exit(1);
  }
}, 3000);
