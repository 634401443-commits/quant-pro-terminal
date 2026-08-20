"""
选股小工具 v4.0 — FastAPI 全栈版
================================
借鉴 DSA 架构: 单进程 FastAPI + React前端 + SQLite 持久化

启动: python app.py
访问: http://localhost:8000

API endpoints:
  GET  /api/stocks           — 股票排名 (实时计算)
  GET  /api/stocks/{code}    — 单只详情
  GET  /api/indices          — 大盘指数
  GET  /api/config           — 因子配置
  POST /api/config           — 更新配置
  GET  /api/history          — 历史评分
"""

import json, os, time, asyncio, sqlite3, re
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

import numpy as np
import urllib.request
import ssl as ssl_mod
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ======================== 配置 ========================

PORT = int(os.environ.get("PORT", 8000))
# 桌面应用（Electron+PyInstaller）部署：路径可由环境变量覆盖
# REACT_DIR: 前端构建产物目录；QUANT_PRO_DB: SQLite 数据库文件；QUANT_PRO_MARKET_TS: market.ts 目标
_env_react = os.environ.get("REACT_DIR")
REACT_DIR = Path(_env_react) if _env_react else (Path(__file__).parent / "app_17beuetfu9m (2)" / "dist")
_env_db = os.environ.get("QUANT_PRO_DB")
DB_PATH = Path(_env_db) if _env_db else (Path(__file__).parent / "data" / "fts.db")
CACHE_TTL = 300  # 因子缓存5分钟

# ======================== SQLite ========================

def init_db():
    print(f"[init_db] DB_PATH={DB_PATH} parent_exists={DB_PATH.parent.exists()} parent_writable={os.access(str(DB_PATH.parent), os.W_OK)}", flush=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"[init_db] after mkdir parent_exists={DB_PATH.parent.exists()}", flush=True)
    conn = sqlite3.connect(str(DB_PATH))
    print(f"[init_db] connect OK", flush=True)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stock_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            price REAL,
            score REAL,
            rank INTEGER,
            factors TEXT,  -- JSON
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS share_reports (
            id TEXT PRIMARY KEY,
            report_type TEXT NOT NULL,
            report_data TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            expire_at TEXT DEFAULT (datetime('now', 'localtime', '+7 days')),
            view_count INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS index_data (
            date TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT,
            price REAL,
            change_pct REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (date, code)
        )
    """)
    # 默认配置
    defaults = {
        "factor_weights": json.dumps({
            "价值因子": 20, "成长因子": 18, "质量因子": 22,
            "动量因子": 15, "波动率因子": 10, "技术因子": 15,
        }),
        "stock_pool_size": "300",
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    return conn

# ======================== 腾讯API数据拉取 (urllib版) ========================

_SSL_CTX = ssl_mod.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl_mod.CERT_NONE

def _sync_fetch(url, encoding='gbk'):
    """同步HTTP GET请求，使用urllib"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://finance.sina.com.cn/",
    })
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        raw = resp.read()
        return raw.decode(encoding, errors='ignore')

def _sync_fetch_em(url):
    """东财专用GET（需 quote.eastmoney.com Referer 避免 rc:102）"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://quote.eastmoney.com/",
    })
    with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# ======================== P1.1: 真实基本面数据 ========================

_VALUATION_CACHE = {}
_VALUATION_TS = 0

def fetch_valuation_batch():
    """从东财批量获取A股真实估值+财务数据(PE/PB/PCF/股息率/ROE/毛利率/行业/市值)"""
    global _VALUATION_CACHE, _VALUATION_TS
    try:
        url = ('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=6000&po=1&np=1'
               '&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81'
               '&fields=f12,f2,f9,f23,f100,f115,f186,f20,f21,f37,f49,f167,f173')
        text = _sync_fetch_em(url)
        d = json.loads(text)
        items = d.get('data', {}).get('diff', {})
        cache = {}
        for v in (items.values() if isinstance(items, dict) else items):
            code = str(v.get('f12', ''))
            if not code or code == '-':
                continue
            def _f(key):
                val = v.get(key, '-')
                return float(val) if val != '-' else 0
            cache[code] = {
                'pe': _f('f9'),
                'pb': _f('f23'),
                'pcf': _f('f115'),
                'dividendYield': _f('f186'),
                'industry': str(v.get('f100', '-')) if v.get('f100', '-') != '-' else '其他',
                'totalMv': _f('f20'),
                'roe': _f('f37'),
                'grossMargin': _f('f49'),
                'netMargin': _f('f167'),
                'revenueGrowth': _f('f173'),
            }
        _VALUATION_CACHE = cache
        _VALUATION_TS = time.time()
        print(f'[valuation] 获取真实估值+财务数据: {len(cache)} 只', flush=True)
        return cache
    except Exception as e:
        print(f'[valuation] 获取失败: {e}', flush=True)
        return _VALUATION_CACHE

# ======================== P1.2: 统一因子配置 ========================

_FACTOR_CFG = None

def load_factor_config():
    """加载统一因子配置(factor_config.json)，消除后端与PTrade双体系分裂"""
    global _FACTOR_CFG
    if _FACTOR_CFG is not None:
        return _FACTOR_CFG
    _FACTOR_CFG = {
        "blend_ratio": {"v31a": 0.50, "qp": 0.50},
        "qp_weights": {"xsmom": 0.25, "lowvol": 0.20, "vpcorr": 0.20, "trend": 0.20, "bias": 0.15},
    }
    try:
        cfg_path = Path(__file__).parent / "factor_config.json"
        with open(cfg_path, encoding='utf-8') as f:
            data = json.load(f)
        _FACTOR_CFG["blend_ratio"] = data.get("blend_ratio", _FACTOR_CFG["blend_ratio"])
        qp_group = data.get("factor_groups", {}).get("qp", {})
        for fac in qp_group.get("factors", []):
            _FACTOR_CFG["qp_weights"][fac["name"]] = fac["weight"]
        print(f"[factor_config] 已加载统一因子配置 v{data.get('version', '?')}", flush=True)
    except Exception as e:
        print(f"[factor_config] 加载失败(使用默认值): {e}", flush=True)
    return _FACTOR_CFG

def _sync_fetch_json(url):
    """同步HTTP GET请求，返回JSON解析结果"""
    raw = _sync_fetch(url, encoding='utf-8')
    return json.loads(raw)

async def fetch_url(url, encoding='gbk'):
    """异步HTTP GET请求，内部使用urllib同步执行"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch, url, encoding)

async def fetch_url_json(url):
    """异步HTTP GET请求，返回JSON"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_fetch_json, url)

async def get_kline(code, market, days=200):
    param = f"{market}{code},day,,,{days+5},qfq"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
    try:
        d = await fetch_url_json(url)
    except:
        return None
    if not d: return None
    key = f"{market}{code}"
    kline = d.get('data', {}).get(key, {}).get('qfqday') or d.get('data', {}).get(key, {}).get('day')
    if not kline or len(kline) < 30: return None
    return {
        'code': code,
        'close': np.array([float(r[2]) for r in kline]),
        'open':  np.array([float(r[1]) for r in kline]),
        'high':  np.array([float(r[3]) for r in kline]),
        'low':   np.array([float(r[4]) for r in kline]),
        'volume':np.array([float(r[5]) for r in kline]),
        'dates': [r[0] for r in kline],
    }

async def get_indices():
    url = "http://qt.gtimg.cn/q=s_sh000001,s_sz399001,s_sz399006,s_sh000688"
    try:
        text = await fetch_url(url)
    except:
        return []
    if not text: return []
    indices = []
    for line in text.strip().split('\n'):
        if '="' not in line: continue
        f = line.split('="', 1)[1].strip('";\n\r').split('~')
        # 腾讯 s_ 指数格式 ~11 字段: 1~上证指数~000001~3982.65~55.47~1.41~...
        if len(f) < 6: continue
        try:
            indices.append({
                'code': f[2], 'name': f[1],
                'price': float(f[3]) if f[3] else 0,
                'change_pct': float(f[5]) if len(f) > 5 and f[5] else 0,
                'change_pt': float(f[4]) if len(f) > 4 and f[4] else 0,
                'amount': float(f[6]) if len(f) > 6 and f[6] else 0,
            })
        except: pass
    return indices

async def fetch_quotes(codes_batch):
    """批量获取行情数据"""
    url = f"http://qt.gtimg.cn/q={','.join(codes_batch)}"
    text = await fetch_url(url)
    quote_map = {}
    if text:
        for line in text.strip().split('\n'):
            if '="' not in line: continue
            try:
                flds = line.split('="', 1)[1].strip('";\n\r').split('~')
                if len(flds) < 40: continue
                code = flds[2]
                quote_map[code] = {
                    'name': flds[1],
                    'price': float(flds[3]) if flds[3] else 0,
                    'change': float(flds[32]) if flds[32] else 0,
                    'pe': float(flds[39]) if flds[39] else 0,
                    'pb': float(flds[46]) if flds[46] else 0,
                    'market_cap': float(flds[44]) if flds[44] else 0,
                }
            except: pass
    return quote_map

# ======================== 成分股列表 ========================

async def get_stock_pool(max_n=300):
    """获取沪深300+中证500成分股"""
    pool = []
    try:
        import akshare as ak
        for idx_code in ["000300", "000905"]:
            df = ak.index_stock_cons_weight_csindex(idx_code)
            for _, r in df.iterrows():
                c = str(r["成分券代码"])
                pool.append((c, str(r["成分券名称"]), 'sh' if c.startswith('6') else 'sz'))
    except: pass
    
    seen = set(); unique = []
    for c, n, m in pool:
        if c not in seen: seen.add(c); unique.append((c, n, m))
    return unique[:max_n]

# ======================== 因子计算 ========================

def sma(arr, w):
    n = len(arr); cs = np.cumsum(np.insert(arr.astype(float), 0, 0.0))
    r = np.zeros(n)
    for i in range(n):
        s = max(0, i - w + 1); r[i] = (cs[i + 1] - cs[s]) / (i - s + 1)
    return r

def rolling_std(arr, w):
    n = len(arr); r = np.zeros(n); m = sma(arr, w)
    cs2 = np.cumsum(np.insert(arr.astype(float) ** 2, 0, 0.0))
    for i in range(n):
        s = max(0, i - w + 1); c = i - s + 1
        r[i] = np.sqrt(max(cs2[i + 1] - cs2[s] - c * m[i] ** 2, 0)) / np.sqrt(c)
    return r

_TDX_FIN = None  # 缓存 TDX 财务数据 {code: {roe, grossMargin, ...}}

def load_tdx_financial():
    """加载 tdx-financial-data.json 建立 code -> 财务指标 映射（进程内缓存）"""
    global _TDX_FIN
    if _TDX_FIN is not None:
        return _TDX_FIN
    _TDX_FIN = {}
    try:
        path = os.path.join(os.path.dirname(__file__), 'app_17beuetfu9m (2)', 'public', 'tdx-financial-data.json')
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        for s in data.get('stocks', []):
            _TDX_FIN[str(s.get('code'))] = s
    except Exception as e:
        print(f"[app] 加载 tdx-financial-data.json 失败: {e}")
    return _TDX_FIN

def compute_factors(hist):
    c, v = hist['close'], hist['volume']; n = len(c)
    if n < 60: return None, None
    ret = np.zeros(n); ret[1:] = (c[1:] - c[:-1]) / np.maximum(c[:-1], 1e-10)
    
    f = {}
    f["change1m"] = float((c[-1] / c[-min(21, n)] - 1) * 100) if n > 21 else 0
    f["change3m"] = float((c[-1] / c[-min(63, n)] - 1) * 100) if n > 63 else 0
    f["change6m"] = float((c[-1] / c[-min(126, n)] - 1) * 100) if n > 126 else 0
    g = np.where(ret > 0, ret, 0); l = np.where(ret < 0, -ret, 0)
    ag = sma(g, 14)[-1]; al = sma(l, 14)[-1]
    f["rsi"] = float(100 - 100 / (1 + ag / max(al, 1e-10)))
    v20 = rolling_std(ret, 20) * np.sqrt(252)
    f["vol20"] = float(v20[-1] * 100)
    f["vol60"] = float(rolling_std(ret, 60)[-1] * np.sqrt(252) * 100)
    f["maxDrawdown"] = float(np.min(c[-60:] / np.maximum.accumulate(c[-60:]) - 1) * 100)
    f["beta"] = float(np.clip(v20[-1] / 0.25, 0.3, 3.0))
    
    # MACD
    def ema(arr, p):
        a = 2.0 / (p + 1); r = np.zeros_like(arr); r[0] = arr[0]
        for i in range(1, len(arr)): r[i] = a * arr[i] + (1 - a) * r[i - 1]
        return r
    e12 = ema(c, 12); e26 = ema(c, 26)
    macd_h = 2 * (e12 - e26 - ema(e12 - e26, 9))
    f["macd"] = float(np.clip(macd_h[-1] / max(c[-1], 1e-10) * 100, -10, 10))
    
    if n >= 9: f["kdj"] = float((c[-1] - np.min(c[-9:])) / max(np.max(c[-9:]) - np.min(c[-9:]), 1e-10) * 100)
    else: f["kdj"] = 50
    
    m20 = sma(c, 20)[-1]; s20 = rolling_std(c, 20)[-1]
    f["bollPosition"] = float(np.clip((c[-1] - (m20 - 2 * s20)) / max(4 * s20, 1e-10) * 100, 0, 100))
    f["maBullish"] = bool(float(np.mean(c[-5:])) > float(np.mean(c[-10:])) > float(np.mean(c[-20:])) > float(np.mean(c[-60:])))
    
    # 估值/成长/质量 — P1.1: 优先使用真实基本面数据(东财API)
    _code = str(hist.get('code', '')).split('.')[0]
    _val = _VALUATION_CACHE.get(_code, {})
    _has_em = _code in _VALUATION_CACHE

    # 估值因子（东财API真实值）
    f["pe"] = float(_val.get('pe', 0))
    f["pb"] = float(_val.get('pb', 0))
    f["ps"] = 0  # 东财免费接口无PS
    f["pcf"] = float(_val.get('pcf', 0))
    f["dividendYield"] = float(_val.get('dividendYield', 0))
    f["evEbitda"] = 0  # 需付费数据源

    # 成长/质量因子：东财真实值 > TDX本地 > 技术面代理
    if _has_em and _val.get('roe', 0) != 0:
        f["roe"] = float(np.clip(_val.get('roe', 0), -50, 100))
    else:
        f["roe"] = float(np.clip(15 + f["change1m"] * 0.3, 0, 50))

    if _has_em and _val.get('grossMargin', 0) != 0:
        f["grossMargin"] = float(np.clip(_val.get('grossMargin', 0), 0, 100))
    else:
        f["grossMargin"] = float(np.clip(30, 10, 80))

    if _has_em and _val.get('netMargin', 0) != 0:
        f["netMargin"] = float(np.clip(_val.get('netMargin', 0), -50, 100))
    else:
        f["netMargin"] = float(np.clip(12, 5, 50))

    if _has_em and _val.get('revenueGrowth', 0) != 0:
        f["revenueGrowth"] = float(np.clip(_val.get('revenueGrowth', 0), -100, 200))
    else:
        f["revenueGrowth"] = float(np.clip(f["change1m"] * 12, -50, 100))

    f["roa"] = float(np.clip(f["roe"] * 0.6, 0, 30))
    f["profitGrowth"] = float(np.clip(f["revenueGrowth"] * 1.2, -50, 100))
    f["roeChange"] = float(np.clip(f["revenueGrowth"] * 0.5, -20, 30))
    f["debtRatio"] = float(np.clip(50, 10, 90))
    f["cashFlowQuality"] = float(np.clip(50 + f["change3m"] * 2, 0, 100))

    # PEG（需在revenueGrowth确定后计算）
    f["peg"] = float(f["pe"] / max(f["revenueGrowth"], 1)) if f["pe"] > 0 and f["revenueGrowth"] > 0 else 0

    # TDX 财务数据补充（仅在东财未命中时回退）
    _fin = load_tdx_financial()
    if not _has_em and _code in _fin:
        _fd = _fin[_code]
        for _k in ['roe', 'grossMargin', 'netMargin', 'revenueGrowth', 'profitGrowth']:
            if _fd.get(_k) is not None:
                f[_k] = float(np.clip(float(_fd[_k]), 0, 100))
        f["roa"] = float(np.clip(f["roe"] * 0.6, 0, 30))

    # P1.1: 标记数据来源
    f["finSource"] = ("real_fundamentals" if _has_em and f["pe"] > 0 and _val.get('roe', 0) != 0
                      else "real_pe_pb" if _has_em and f["pe"] > 0
                      else "tdx_override" if _code in _fin
                      else "proxy")
    
    # FTS 5因子
    ft = {}
    r20 = (c[-1] / c[-min(21, n)] - 1) if n > 21 else 0
    r60 = (c[-1] / c[-min(61, n)] - 1) if n > 61 else 0
    sx = 0.6 * np.tanh(r20 * 15) + 0.4 * np.tanh(r60 * 8)
    ft["fts_xsmom"] = float(np.clip((sx + 1) * 50, 0, 100))
    ft["fts_lowvol"] = float(np.clip(100 - rolling_std(ret, 20)[-1] * 100 * 5, 0, 100))
    
    w = 10; vi = v[-w:]; ci = c[-w:]
    vr = np.argsort(np.argsort(vi)).astype(float) / w
    cr = np.argsort(np.argsort(ci)).astype(float) / w
    cv = np.sum((vr - np.mean(vr)) * (cr - np.mean(cr))) / max(np.sqrt(np.sum((vr - np.mean(vr)) ** 2) * np.sum((cr - np.mean(cr)) ** 2)), 1e-10)
    ft["fts_vpcorr"] = float(np.clip((cv + 1) * 50, 0, 100))
    
    x = np.arange(20).astype(float); yi = c[-20:]
    xm, ym = np.mean(x), np.mean(yi)
    slope = np.sum((x - xm) * (yi - ym)) / max(np.sum((x - xm) ** 2), 1e-10)
    rsq = 1 - np.sum((yi - (ym + slope * (x - xm))) ** 2) / max(np.sum((yi - ym) ** 2), 1e-10)
    st = np.tanh(slope / max(c[-21], 1e-10) * 100) * 0.6 + rsq * 0.4
    ft["fts_trend"] = float(np.clip((st + 1) * 50, 0, 100))
    
    m20v = sma(c, 20)[-1]; bias = -(c[-1] - m20v) / max(m20v, 1e-10)
    ft["fts_bias"] = float(np.clip((np.tanh(bias * 15) + 1) * 50, 0, 100))
    # P1.2: 统一因子权重从 factor_config.json 读取（消除双体系分裂）
    _cfg = load_factor_config()
    _w = _cfg["qp_weights"]
    ft["fts_composite"] = float(np.clip(
        ft["fts_xsmom"] * _w["xsmom"] + ft["fts_lowvol"] * _w["lowvol"] +
        ft["fts_vpcorr"] * _w["vpcorr"] + ft["fts_trend"] * _w["trend"] +
        ft["fts_bias"] * _w["bias"], 0, 100))
    
    return f, ft

# ======================== 缓存管理 ========================

class StockCache:
    def __init__(self):
        self.data = []
        self.indices = []
        self.last_update = None
        self.updating = False
    
    def is_stale(self):
        return (self.last_update is None or 
                (datetime.now() - self.last_update).total_seconds() > CACHE_TTL)
    
    async def refresh(self):
        if self.updating: return
        self.updating = True
        try:
            # P1.1: 刷新真实基本面数据缓存(PE/PB/ROE/毛利率等)
            fetch_valuation_batch()

            # 获取成分股
            pool = await get_stock_pool(300)

            # P1.1 fallback: 东财API失败时用腾讯行情补充PE/PB
            if not _VALUATION_CACHE:
                print('[valuation] 东财API不可用，使用腾讯行情补充PE/PB', flush=True)
                for i in range(0, len(pool), 50):
                    batch = pool[i:i+50]
                    codes_batch = [f"{m}{c}" for c, n, m in batch]
                    quotes = await fetch_quotes(codes_batch)
                    for code, name, market in batch:
                        q = quotes.get(code, {})
                        if q and q.get('pe', 0) > 0:
                            _VALUATION_CACHE[code] = {
                                'pe': q.get('pe', 0),
                                'pb': q.get('pb', 0),
                                'pcf': 0,
                                'dividendYield': 0,
                                'industry': '其他',
                                'totalMv': q.get('market_cap', 0),
                                'roe': 0,
                                'grossMargin': 0,
                                'netMargin': 0,
                                'revenueGrowth': 0,
                            }

            results = []
            for code, name, market in pool:
                hist = await get_kline(code, market, 200)
                if not hist: continue
                f, ft = compute_factors(hist)
                if not f: continue

                results.append({
                    'code': code, 'name': name,
                    'industry': _VALUATION_CACHE.get(code, {}).get('industry', '其他'),
                    'price': float(hist['close'][-1]),
                    'score': float(ft['fts_composite']),
                    'factors': {k: round(float(v), 2) if isinstance(v, (int, float, np.floating)) else v for k, v in f.items()},
                    'ftsFactors': {k: round(float(v), 2) for k, v in ft.items()},
                    'kline': hist['close'][-60:].tolist(),
                    'high': hist['high'][-60:].tolist(),
                    'low': hist['low'][-60:].tolist(),
                    'open': hist['open'][-60:].tolist(),
                    'dates': hist['dates'][-60:],
                })
            
            results.sort(key=lambda x: x['score'], reverse=True)
            for i, r in enumerate(results): r['rank'] = i + 1
            self.data = results
            
            # 指数
            self.indices = await get_indices()
            self.last_update = datetime.now()
            
            # 存SQLite
            self._save_to_db()
            # 导出静态文件（factor_scores.json / kline-data.json），消除前端48h陈旧告警
            self._export_static()
        finally:
            self.updating = False
    
    def _save_to_db(self):
        try:
            conn = sqlite3.connect(str(DB_PATH))
            today = datetime.now().strftime("%Y-%m-%d")
            for r in self.data:
                conn.execute(
                    "INSERT OR REPLACE INTO stock_scores (date, code, name, price, score, rank, factors) VALUES (?,?,?,?,?,?,?)",
                    (today, r['code'], r['name'], r['price'], r['score'], r['rank'], json.dumps(r['factors']))
                )
            for idx in self.indices:
                conn.execute(
                    "INSERT OR REPLACE INTO index_data (date, code, name, price, change_pct) VALUES (?,?,?,?,?)",
                    (today, idx['code'], idx['name'], idx['price'], idx['change_pct'])
                )
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB save error: {e}")
    
    def _export_static(self):
        """导出 factor_scores.json / kline-data.json 到前端静态目录（消除48h陈旧告警）"""
        if not self.data:
            print("[static] 数据为空，跳过导出（避免覆盖已有kline-data.json）")
            return
        try:
            from datetime import datetime as _dt
            now = _dt.now()
            payload = {
                'date': now.strftime('%Y-%m-%d'),
                'updateTime': now.strftime('%Y-%m-%d %H:%M:%S'),
                'stockCount': len(self.data),
                'stocks': self.data,
                'ftsTop5': [{'code': r['code'], 'name': r.get('name', ''), 'score': r['score'], 'rank': r['rank']} for r in self.data[:5]],
            }
            kline_payload = {
                'date': now.strftime('%Y-%m-%d'),
                'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
                'count': len(self.data),
                'data': {
                    r['code']: [
                        {
                            'date': r['dates'][i] if i < len(r.get('dates', [])) else '',
                            'open': float(r['open'][i]) if i < len(r.get('open', [])) else 0,
                            'high': float(r['high'][i]) if i < len(r.get('high', [])) else 0,
                            'low': float(r['low'][i]) if i < len(r.get('low', [])) else 0,
                            'close': float(r['kline'][i]) if i < len(r.get('kline', [])) else 0,
                            'volume': 0,
                        }
                        for i in range(len(r.get('kline', [])))
                    ]
                    for r in self.data
                },
            }
            dirs = [
                REACT_DIR,
                Path(__file__).parent / "app_17beuetfu9m (2)" / "public",
            ]
            for d in dirs:
                try:
                    d.mkdir(parents=True, exist_ok=True)
                    (d / "factor_scores.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding='utf-8')
                    (d / "kline-data.json").write_text(json.dumps(kline_payload, ensure_ascii=False, default=str), encoding='utf-8')
                except Exception as e:
                    print(f"[static] {d.name} export error: {e}")
            print(f"[static] 静态文件已导出 ({now.strftime('%Y-%m-%d %H:%M')}, {len(self.data)}只)")
        except Exception as e:
            print(f"[static] export error: {e}")

    def get_history(self, code=None, days=7):
        try:
            conn = sqlite3.connect(str(DB_PATH))
            if code:
                rows = conn.execute(
                    "SELECT date, score, rank FROM stock_scores WHERE code=? ORDER BY date DESC LIMIT ?",
                    (code, days)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT date, code, name, score FROM stock_scores WHERE date=(SELECT MAX(date) FROM stock_scores) ORDER BY score DESC"
                ).fetchall()
            conn.close()
            return rows
        except:
            return []

cache = StockCache()

# ======================== FastAPI App ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"  DB: {DB_PATH}")
    # 后台刷新缓存 + 指数数据
    asyncio.create_task(cache.refresh())
    asyncio.create_task(refresh_market_ts())
    yield

async def refresh_market_ts():
    """拉取真实指数数据写入 market.ts (触发Vite HMR)"""
    _env_market = os.environ.get("QUANT_PRO_MARKET_TS")
    market_path = Path(_env_market) if _env_market else (Path(__file__).parent / "app_17beuetfu9m (2)" / "src" / "data" / "market.ts")
    try:
        indices = await get_indices()
        if not indices:
            print("  [market.ts] 指数数据为空，跳过")
            return
        
        lines = [
            f"// AUTO-GENERATED from Tencent — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "export interface IMarketIndex {",
            "  name:string;code:string;value:number;change:number;changePoint:number;",
            "  amount:number;kline:number[];",
            "}",
            "export const MARKET_INDICES: IMarketIndex[] = [",
        ]
        for idx in indices:
            lines.append(f"  {{name:'{idx['name']}',code:'{idx['code']}',")
            lines.append(f"   value:{idx['price']:.2f},change:{idx['change_pct']:.2f},")
            lines.append(f"   changePoint:{idx.get('change_pt',0):.2f},amount:{idx.get('amount',0):.0f},kline:[]}},")
        lines.append("];")
        lines.extend([
            "",
            "export interface IIndustryData { name:string;change:number;change5d:number;change20d:number;change60d:number;amount:number;leadingStock:string;leadingChange:number; }",
            "export const INDUSTRY_DATA: IIndustryData[] = [{name:'电子',change:1.2,change5d:3.5,change20d:8.2,change60d:15.3,amount:520,leadingStock:'龙头',leadingChange:5.2}];",
            "export interface IMarketSentiment { upCount:number;downCount:number;flatCount:number;limitUp:number;limitDown:number;profitEffect:number;northFlow:number;totalAmount:number;marginBalance:number;newHigh52:number;newLow52:number; }",
            "export const MARKET_SENTIMENT: IMarketSentiment = { upCount:1500,downCount:2000,flatCount:500,limitUp:45,limitDown:12,profitEffect:45,northFlow:15,totalAmount:8500,marginBalance:15000,newHigh52:120,newLow52:35 };",
            "export interface IStrategyPerformance { name:string;returns:number[];finalReturn:number;maxDrawdown:number;sharpe:number; }",
            "export const STRATEGY_PERFORMANCE: IStrategyPerformance[] = [",
            "  {name:'沪深300基准',returns:[0,1,2,3,4,5],finalReturn:5,maxDrawdown:-15,sharpe:0.3},",
            "  {name:'多因子选股',returns:[0,3,8,12,18,25],finalReturn:25,maxDrawdown:-10,sharpe:1.5},",
            "];",
        ])
        with open(market_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"  [market.ts] 已更新 — {len(indices)}个指数 {indices[0]['name']}:{indices[0]['price']:.0f}")
    except Exception as e:
        print(f"  [market.ts] 更新失败: {e}")

app = FastAPI(title="FTS 选股工具 v4.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ======================== 自定义股票池 ========================

class CustomPoolRequest(BaseModel):
    codes: list[str]
    top_n: int = 20

def _parse_stock_code(raw: str):
    """解析股票代码 -> (code, market, display)"""
    raw = raw.strip().upper()
    if not raw:
        return None
    m = re.match(r"^(\d{6})\.([SZ]{2})$", raw)
    if m:
        c, mk = m.group(1), m.group(2).lower()
        return c, mk, f"{c}.{mk.upper()}"
    m = re.match(r"^([SZ]{2})(\d{6})$", raw)
    if m:
        c, mk = m.group(2), m.group(1).lower()
        return c, mk, f"{c}.{mk.upper()}"
    m = re.match(r"^(\d{6})$", raw)
    if m:
        c = m.group(1)
        first = c[0]
        if first in ("0","1","2","3"): mk = "sz"
        elif first in ("5","6","9"): mk = "sh"
        elif first in ("4","8"): mk = "bj"
        else: mk = "sz"
        return c, mk, f"{c}.{mk.upper()}"
    return None

@app.post("/api/custom_pool")
async def custom_pool(req: CustomPoolRequest):
    start = time.time()
    parsed = {}
    for raw in req.codes:
        p = _parse_stock_code(raw)
        if p:
            parsed[p[0]] = p
    if not parsed:
        raise HTTPException(400, "没有有效的股票代码")
    errors = []
    results = []
    
    market_codes = [f"{p[1]}{p[0]}" for p in parsed.values()]
    quote_map = {}
    for i in range(0, len(market_codes), 30):
        batch = market_codes[i:i + 30]
        qm = await fetch_quotes(batch)
        quote_map.update(qm)
        if i + 30 < len(market_codes):
            await asyncio.sleep(0.15)
    
    for code, (c, mk, display) in parsed.items():
        try:
            q = quote_map.get(c, {})
            if not q.get('price') or q['price'] <= 0:
                errors.append(f"{display}: 无法获取行情(代码无效)")
                continue
            hist = await get_kline(c, mk, 200)
            if not hist:
                errors.append(f"{display}: K线数据不足")
                continue
            f, ft = compute_factors(hist)
            if not f:
                errors.append(f"{display}: 因子计算失败")
                continue
            results.append({
                'code': display,
                'name': q.get('name',''),
                'price': round(q['price'], 2),
                'change': round(q.get('change',0), 2),
                'score': round(float(ft['fts_composite']), 2),
                'factors': {k: round(float(v),2) if isinstance(v,(int,float,np.floating)) else v for k,v in f.items()},
                'ftsFactors': {k: round(float(v),2) for k,v in ft.items()},
                'kline': hist['close'][-60:].tolist(),
                    'high': hist['high'][-60:].tolist(),
                    'low': hist['low'][-60:].tolist(),
                    'open': hist['open'][-60:].tolist(),
            })
        except Exception as e:
            errors.append(f"{display}: {str(e)}")
    results.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(results):
        r['rank'] = i + 1
    return {
        'success': len(results) > 0,
        'total': len(parsed),
        'processed': len(results),
        'skipped': len(errors),
        'elapsed_ms': round((time.time() - start) * 1000, 1),
        'results': results[:req.top_n],
        'errors': errors,
    }

# ======================== 报告分享 ========================

_share_rate: dict = {}  # ip -> list of timestamps（限流：每小时最多10个）

class ShareReportRequest(BaseModel):
    report_type: str = "stock"  # stock | etf
    report_data: dict

def _gen_share_id():
    import random, string
    return "rpt_" + "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

@app.post("/api/reports/share")
async def share_report(req: ShareReportRequest):
    client_ip = req.client.host if hasattr(req, 'client') else None
    # 简化限流：基于请求头 X-Forwarded-For 不可靠，用固定 key + 时间窗口
    now_ts = time.time()
    key = "local"
    _share_rate.setdefault(key, [])
    _share_rate[key] = [t for t in _share_rate[key] if now_ts - t < 3600]
    if len(_share_rate[key]) >= 10:
        raise HTTPException(429, "每小时最多生成10个分享链接，请稍后再试")
    _share_rate[key].append(now_ts)

    share_id = _gen_share_id()
    report_type = req.report_type if req.report_type in ("stock", "etf") else "stock"
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute(
            "INSERT INTO share_reports (id, report_type, report_data) VALUES (?,?,?)",
            (share_id, report_type, json.dumps(req.report_data, ensure_ascii=False)),
        )
        conn.commit()
        row = conn.execute(
            "SELECT created_at, expire_at FROM share_reports WHERE id=?",
            (share_id,)
        ).fetchone()
        conn.close()
    except Exception as e:
        raise HTTPException(500, f"分享保存失败: {e}")

    expire_at = row[1] if row else ""
    return {
        "ok": True,
        "shareId": share_id,
        "shareUrl": f"/share/{share_id}",
        "expireAt": expire_at,
        "validDays": 7,
    }

@app.get("/api/reports/share/{share_id}")
async def get_share_report(share_id: str):
    if not re.match(r"^rpt_[a-z0-9]{6}$", share_id):
        raise HTTPException(400, "分享编号格式错误")
    try:
        conn = sqlite3.connect(str(DB_PATH))
        row = conn.execute(
            "SELECT report_type, report_data, created_at, expire_at, view_count FROM share_reports WHERE id=?",
            (share_id,)
        ).fetchone()
        if row:
            conn.execute("UPDATE share_reports SET view_count=view_count+1 WHERE id=?", (share_id,))
            conn.commit()
        conn.close()
    except Exception as e:
        raise HTTPException(500, str(e))
    if not row:
        raise HTTPException(404, "分享不存在或已删除")
    report_type, report_data, created_at, expire_at, view_count = row
    from datetime import datetime as _dt
    try:
        expired = _dt.strptime(expire_at, "%Y-%m-%d %H:%M:%S") < _dt.now()
    except Exception:
        expired = False
    return {
        "ok": True,
        "shareId": share_id,
        "reportType": report_type,
        "reportData": json.loads(report_data),
        "createdAt": created_at,
        "expireAt": expire_at,
        "viewCount": view_count,
        "expired": expired,
    }

# ======================== API Routes ========================

@app.get("/api/stocks")
async def get_stocks(
    sort: str = Query("score", description="排序字段: score|rank|change1m|vol20"),
    limit: int = Query(300, ge=5, le=500),
    offset: int = Query(0, ge=0),
):
    """获取股票排名列表"""
    if cache.is_stale():
        asyncio.create_task(cache.refresh())
    data = cache.data
    return {
        "total": len(data),
        "updateTime": cache.last_update.isoformat() if cache.last_update else None,
        "stocks": data[offset:offset + limit],
    }

@app.get("/api/stocks/{code}")
async def get_stock_detail(code: str):
    """获取单只股票详情"""
    for s in cache.data:
        if s['code'] == code:
            return s
    raise HTTPException(404, f"Stock {code} not found")

@app.get("/api/indices")
async def get_indices_api():
    """获取大盘指数"""
    if not cache.indices:
        cache.indices = await get_indices()
    return {"indices": cache.indices, "updateTime": cache.last_update.isoformat() if cache.last_update else None}

@app.get("/api/config")
async def get_config():
    """获取配置"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT key, value FROM config").fetchall()
        conn.close()
        return {k: json.loads(v) for k, v in rows}
    except:
        return {}

@app.get("/api/factor-config")
async def get_factor_config():
    """P1.2: 获取统一因子配置"""
    return load_factor_config()

class ConfigUpdate(BaseModel):
    key: str
    value: dict

@app.post("/api/config")
async def update_config(cfg: ConfigUpdate):
    """更新配置"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?,?,CURRENT_TIMESTAMP)", 
                     (cfg.key, json.dumps(cfg.value)))
        conn.commit(); conn.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/history")
async def get_history(code: str = Query(None), days: int = Query(7, ge=1, le=90)):
    """获取历史评分"""
    rows = cache.get_history(code, days)
    if code:
        return {"code": code, "history": [{"date": r[0], "score": r[1], "rank": r[2]} for r in rows]}
    return {"stocks": [{"code": r[1], "name": r[2], "score": r[3]} for r in rows]}

@app.get("/api/refresh")
async def refresh_cache():
    """手动刷新缓存"""
    asyncio.create_task(cache.refresh())
    return {"ok": True, "message": "刷新中，请稍后查询"}

@app.get("/api/health")
async def health():
    return {"status": "ok", "stocks": len(cache.data), "updated": cache.last_update.isoformat() if cache.last_update else None}

# ======================== 外部行情代理（桌面生产模式，替代 vite proxy） ========================

@app.get("/api/quote/{rest:path}")
async def proxy_quote(rest: str):
    """代理腾讯行情 qt.gtimg.cn/q=xxx（原 vite /api/quote 代理）"""
    url = f"https://qt.gtimg.cn/q={rest}"
    try:
        text = await fetch_url(url)
    except Exception:
        return JSONResponse(content={"error": "quote proxy failed"}, status_code=502)
    return Response(content=text, media_type="text/plain; charset=gbk")

@app.get("/api/t-kline/{rest:path}")
async def proxy_tkline(rest: str):
    """代理腾讯K线 web.ifzq.gtimg.cn（原 vite /api/t-kline 代理）"""
    url = f"https://web.ifzq.gtimg.cn/{rest}"
    try:
        text = await fetch_url_json(url)
    except Exception:
        return JSONResponse(content={"error": "t-kline proxy failed"}, status_code=502)
    return JSONResponse(content=text)

@app.get("/api/em-stock/{rest:path}")
async def proxy_emstock(rest: str):
    """代理东财 push2.eastmoney.com（原 vite /api/em-stock 代理）"""
    url = f"https://push2.eastmoney.com/{rest}"
    try:
        text = await fetch_url_json(url)
    except Exception:
        return JSONResponse(content={"error": "em-stock proxy failed"}, status_code=502)
    return JSONResponse(content=text)

@app.get("/api/eastmoney/{rest:path}")
async def proxy_eastmoney(rest: str):
    """代理东财 push2.eastmoney.com（原 vite /api/eastmoney 代理）"""
    url = f"https://push2.eastmoney.com/{rest}"
    try:
        text = await fetch_url_json(url)
    except Exception:
        return JSONResponse(content={"error": "eastmoney proxy failed"}, status_code=502)
    return JSONResponse(content=text)

@app.get("/api/sina-kline/{rest:path}")
async def proxy_sina(rest: str):
    """代理新浪行情 money.finance.sina.com.cn（原 vite /api/sina-kline 代理）"""
    url = f"https://money.finance.sina.com.cn/{rest}"
    try:
        text = await fetch_url(url)
    except Exception:
        return JSONResponse(content={"error": "sina-kline proxy failed"}, status_code=502)
    return Response(content=text, media_type="text/plain; charset=gbk")

# ======================== 静态文件 ========================

REACT_DIR.mkdir(parents=True, exist_ok=True)

# SPA fallback：分享页等前端路由（需在 mount 之前注册，否则被静态捕获返回404）
@app.get("/share/{share_id}")
async def share_spa(share_id: str):
    return FileResponse(str(REACT_DIR / "index.html"))

# SPA catch-all：前端路由（/rotation, /backtest 等）回退到 index.html
@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str):
    # 排除 API 路由和静态文件
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    # 如果请求的是具体文件（有扩展名且文件存在），让 StaticFiles 处理
    if "." in full_path.split("/")[-1]:
        fp = REACT_DIR / full_path
        if fp.is_file():
            return FileResponse(str(fp))
    return FileResponse(str(REACT_DIR / "index.html"))

app.mount("/", StaticFiles(directory=str(REACT_DIR), html=True), name="static")

# ======================== 启动 ========================

if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*50}")
    print(f"  选股小工具 v4.0 — FastAPI 全栈版")
    print(f"  借鉴 DSA 架构 | 单进程 | SQLite 持久化")
    print(f"{'='*50}")
    print(f"  API:  http://localhost:{PORT}/api/stocks")
    print(f"  Web:  http://localhost:{PORT}/")
    print(f"  Docs: http://localhost:{PORT}/docs")
    print(f"{'='*50}\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")