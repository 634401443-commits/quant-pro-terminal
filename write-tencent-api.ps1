$content = @'
/**
 * 腾讯行情 API 前端调用工具
 * 通过 Vite proxy /api/quote/ 代理到 https://qt.gtimg.cn/q=
 */

export interface TencentQuote {
  code: string;
  name: string;
  price: number;
  prevClose: number;
  open: number;
  volume: number;
  amount: number;
  changePoint: number;
  change: number;
  high: number;
  low: number;
  time: string;
}

function toMarketCode(code: string): string {
  if (code.startsWith('6') || code.startsWith('9') || code.startsWith('5')) return `sh${code}`;
  if (code.startsWith('0') || code.startsWith('3') || code.startsWith('2') || code.startsWith('1')) return `sz${code}`;
  if (code.startsWith('8') || code.startsWith('4')) return `bj${code}`;
  return `sh${code}`;
}

function parseQuote(raw: string): TencentQuote | null {
  const match = raw.match(/v_\w+="(.+?)"/);
  if (!match) return null;
  const fields = match[1].split('~');
  if (fields.length < 40) return null;
  return {
    name: fields[1],
    code: fields[2],
    price: parseFloat(fields[3]),
    prevClose: parseFloat(fields[4]),
    open: parseFloat(fields[5]),
    volume: parseFloat(fields[6]),
    amount: parseFloat(fields[37]),
    time: fields[30],
    changePoint: parseFloat(fields[31]),
    change: parseFloat(fields[32]),
    high: parseFloat(fields[33]),
    low: parseFloat(fields[34]),
  };
}

/**
 * 批量获取行情数据
 * @param codes 股票/指数/ETF代码数组，如 ['000001', '600000', '510300']
 * @returns 行情数据数组
 */
export async function fetchQuotes(codes: string[]): Promise<TencentQuote[]> {
  if (codes.length === 0) return [];
  const marketCodes = codes.map(toMarketCode).join(',');
  const url = `/api/quote/${marketCodes}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Tencent API error: ${resp.status}`);
  const text = await resp.text();
  const lines = text.split(';').filter(l => l.trim());
  const results: TencentQuote[] = [];
  for (const line of lines) {
    const q = parseQuote(line);
    if (q) results.push(q);
  }
  return results;
}

/**
 * 获取单个行情
 */
export async function fetchQuote(code: string): Promise<TencentQuote | null> {
  const arr = await fetchQuotes([code]);
  return arr[0] || null;
}

/**
 * 获取北向资金净流入（通过东方财富 API）
 * @returns 净流入金额（亿元），正数=流入，负数=流出
 */
export async function fetchNorthboundFlow(): Promise<number | null> {
  try {
    const resp = await fetch('/api/eastmoney/api/qt/kamt.rtmin/get?fields1=f1,f2,f3,f4&fields2=f51,f52,f53,f54,f55,f56');
    if (!resp.ok) return null;
    const data = await resp.json();
    if (data.data?.f2 != null) {
      return Number(data.data.f2.toFixed(2));
    }
    if (data.data?.f51) {
      const parts = String(data.data.f51).split(',');
      if (parts.length >= 2) return Number((parseFloat(parts[1]) / 100).toFixed(2));
    }
    return null;
  } catch {
    return null;
  }
}
'@

$f = 'D:\股票仪表盘\app_17beuetfu9m (2)\src\lib\tencent-api.ts'
[System.IO.File]::WriteAllText($f, $content, [System.Text.Encoding]::UTF8)
Write-Host "Created: $f"