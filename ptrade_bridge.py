#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUANT PRO → 国金 PTrade 信号桥接服务
======================================
链路: QUANT PRO ETF轮动排名 → 信号文件 trade_signal.json → 手动上传 PTrade 研究目录 → PTrade 策略自动下单

背景: QUANT PRO 后端 app.py 已由 PyInstaller 打包为 exe（无源码可改），本服务为功能等价的独立桥接层，
复算 ETF 轮动排名（与前端 momentum 策略同口径：实时价 + K线快照 → 20日涨幅排序 + MA20 买入信号判定）。

用法:
  1) 服务模式    python ptrade_bridge.py
       GET /api/etf-ranking/latest      → 最新轮动排名(JSON)
       GET /api/export-ptrade-signal    → 生成 Top3 买入信号并写 trade_signal.json
  2) 命令行生成  python ptrade_bridge.py --generate
       （供定时任务/schtasks 使用，每 5 分钟一次）
  3) 日志: D:\股票仪表盘\logs\ptrade_bridge.log

数据源:
  - ETF 静态表    D:\股票仪表盘\etf_list.json（80 只，提取自前端打包产物）
  - K线快照       D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json
  - 实时行情      http://localhost:8000/api/quote/shXXXXXX（QUANT PRO 后端 exe 代理腾讯行情）
"""
import json
import os
import re
import sys
import time
import urllib.request
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = r'D:\股票仪表盘'
KLINE_PATH = os.path.join(BASE_DIR, r'app_17beuetfu9m (2)\dist\kline-data.json')
ETF_LIST_PATH = os.path.join(BASE_DIR, 'etf_list.json')
SIGNAL_PATH = os.path.join(BASE_DIR, 'trade_signal.json')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
QUOTE_API = 'http://localhost:8000/api/quote/'
PORT = 8766
TOP_N = 3          # 输出 Top3 买入信号
BATCH = 30         # 行情请求分批
VOLUME = 10000     # 建议数量(股)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
_log = logging.getLogger('ptrade-bridge')
try:
    os.makedirs(LOG_DIR, exist_ok=True)
    fh = logging.FileHandler(os.path.join(LOG_DIR, 'ptrade_bridge.log'), encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    _log.addHandler(fh)
except Exception as e:
    _log.warning('日志文件初始化失败: %s', e)


def load_etf_list():
    """读取 80 只 ETF 静态表"""
    try:
        with open(ETF_LIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log.error('读取 etf_list.json 失败: %s', e)
        return []


def load_kline():
    """读取 K线快照 → {code: [kline对象,...]}"""
    try:
        with open(KLINE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('data') or {}
    except Exception as e:
        _log.error('读取 kline-data.json 失败: %s', e)
        return {}


def fetch_quotes(codes):
    """分批请求实时行情（腾讯格式）→ {code: {price, high, change_pct, name}}"""
    result = {}
    for i in range(0, len(codes), BATCH):
        batch = codes[i:i + BATCH]
        prefixed = []
        for c in batch:
            c = c.strip()
            if c.startswith(('5', '6', '9')):
                prefixed.append('sh' + c)
            else:
                prefixed.append('sz' + c)
        url = QUOTE_API + ','.join(prefixed)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            text = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')
            for m in re.finditer(r'v_(\w+)="([^"]*)"', text):
                code = m.group(1)[2:]           # 去掉 sh/sz 前缀
                f = m.group(2).split('~')
                if len(f) < 35:
                    continue
                try:
                    result[code] = {
                        'price': float(f[3]),
                        'high': float(f[33]),
                        'low': float(f[34]),
                        'change_pct': float(f[32]),
                        'name': f[1],
                    }
                except (ValueError, IndexError):
                    continue
        except Exception as e:
            _log.error('行情请求失败(%s): %s', batch, e)
        time.sleep(0.15)
    return result


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compute_ranking():
    """复算 ETF 轮动排名（momentum 口径：20日涨幅降序 + 买入信号）"""
    etfs = load_etf_list()
    klines = load_kline()
    if not etfs:
        _log.error('ETF 列表为空，无法计算')
        return None
    codes = [e['code'] for e in etfs]
    quotes = fetch_quotes(codes)
    if not quotes:
        _log.error('实时行情全部获取失败，放弃计算（不覆盖旧信号文件）')
        return None

    rows = []
    for etf in etfs:
        code = etf['code']
        q = quotes.get(code)
        if not q:
            _log.warning('%s 无行情，跳过', code)
            continue
        karr = klines.get(code)
        if not karr or not isinstance(karr, list) or len(karr) < 21:
            _log.warning('%s K线不足(21根)，跳过', code)
            continue

        closes = []
        highs = []
        for k in karr:
            if isinstance(k, dict):
                c = _to_float(k.get('close'))
                h = _to_float(k.get('high'))
                if c is not None:
                    closes.append(c)
                if h is not None:
                    highs.append(h)
        if len(closes) < 21:
            continue
        # 与前端 useRealTimeETF 一致：末位替换为实时价
        price = q['price']
        closes[-1] = price
        if highs:
            highs[-1] = q['high']

        price_20ago = closes[-21]
        chg20 = (price - price_20ago) / price_20ago * 100 if price_20ago > 0 else 0.0
        ma20 = sum(closes[-20:]) / 20.0
        above_ma20 = price > ma20
        high20 = max(highs[-20:]) if highs else price
        dist_high20 = (high20 - price) / high20 * 100 if high20 > 0 else 0.0

        if chg20 > 2 and above_ma20:
            signal = '买入'
        elif above_ma20:
            signal = '持有'
        else:
            signal = '观望'

        rows.append({
            'code': code,
            'name': etf['name'],
            'price': round(price, 4),
            'change_20d': round(chg20, 2),
            'dist_high20': round(dist_high20, 2),
            'signal': signal,
            'reason': '20日涨幅%.2f%%，距20日高点%.1f%%，%s' % (chg20, dist_high20, signal),
        })

    rows.sort(key=lambda r: r['change_20d'], reverse=True)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    rankings = []
    for i, r in enumerate(rows, 1):
        rankings.append({
            'rank': i,
            'symbol': _ptrade_symbol(r['code']),
            'code': r['code'],
            'name': r['name'],
            'price': r['price'],
            'change_20d': r['change_20d'],
            'signal': r['signal'],
            'reason': '排名第%d，%s' % (i, r['reason']),
            'suggested_volume': VOLUME,
        })
    return {'timestamp': now, 'total': len(rankings), 'rankings': rankings}


def _ptrade_symbol(code):
    """代码 → PTrade 符号（沪市 .SH / 深市 .SZ，用户示例格式）"""
    if code.startswith(('5', '6', '9')):
        return code + '.SH'
    return code + '.SZ'


def _load_factor_config():
    """P1.2: 加载统一因子配置，嵌入信号文件供PTrade读取"""
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'factor_config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        _log.warning('factor_config.json 加载失败(使用默认): %s', e)
        return {
            "blend_ratio": {"v31a": 0.50, "qp": 0.50},
            "factor_groups": {
                "qp": {"factors": [
                    {"name": "xsmom", "weight": 0.25},
                    {"name": "lowvol", "weight": 0.20},
                    {"name": "vpcorr", "weight": 0.20},
                    {"name": "trend", "weight": 0.20},
                    {"name": "bias", "weight": 0.15},
                ]}
            }
        }


def build_signal_file(rankings):
    """从排名中取 Top3 买入信号 → trade_signal.json"""
    if not rankings:
        _log.error('排名为空，无法生成信号')
        return None
    buys = [r for r in rankings['rankings'] if r['signal'] == '买入']
    top = buys[:TOP_N]
    # P1.2: 嵌入统一因子配置，PTrade策略从信号文件读取（消除双体系分裂）
    factor_cfg = _load_factor_config()
    payload = {
        'timestamp': rankings['timestamp'],
        'source': 'QUANT PRO ETF轮动',
        'strategy': 'momentum(20日涨幅) Top%d买入' % TOP_N,
        'note': '信号为轮动策略参考，下单前请人工复核价格与风控；手动上传至 PTrade 研究目录 /home/fly/notebook/trade_signal.json',
        'factor_config': factor_cfg,
        'signals': [
            {
                'action': 'buy',
                'symbol': r['symbol'],
                'name': r['name'],
                'price': r['price'],
                'volume': r['suggested_volume'],
                'reason': r['reason'],
            }
            for r in top
        ],
    }
    try:
        with open(SIGNAL_PATH, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        _log.info('信号文件已写入 %s（%d 条买入）', SIGNAL_PATH, len(top))
        for s in payload['signals']:
            _log.info('  [buy] %s %s %d股 @%.3f 原因:%s',
                      s['symbol'], s['name'], s['volume'], s['price'], s['reason'])
        return payload
    except Exception as e:
        _log.error('写入信号文件失败: %s', e)
        return None


def generate_signal():
    rankings = compute_ranking()
    if rankings is None:
        return None
    return build_signal_file(rankings)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path.startswith('/api/etf-ranking/latest'):
                data = compute_ranking()
                if data is None:
                    self._json({'code': 0, 'msg': '数据获取失败，请检查 QUANT PRO 后端(:8000) 与 K线文件'}, 502)
                else:
                    self._json({'code': 1, 'timestamp': data['timestamp'], 'rankings': data['rankings']})
            elif self.path.startswith('/api/export-ptrade-signal'):
                payload = generate_signal()
                if payload is None:
                    self._json({'code': 0, 'msg': '信号生成失败'}, 500)
                else:
                    self._json({'code': 1, 'msg': '信号已生成', 'file': SIGNAL_PATH, 'signals': payload['signals']})
            elif self.path.startswith('/api/signal/latest'):
                # P2.1: PTrade策略通过HTTP拉取最新信号（消除手动上传）
                try:
                    with open(SIGNAL_PATH, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    self._json({'code': 1, 'data': payload})
                except FileNotFoundError:
                    payload = generate_signal()
                    if payload:
                        self._json({'code': 1, 'data': payload})
                    else:
                        self._json({'code': 0, 'msg': '暂无信号文件'}, 404)
                except Exception as e:
                    self._json({'code': 0, 'msg': str(e)}, 500)
            elif self.path.startswith('/api/positions/latest'):
                # P3.1: 获取最新持仓快照
                try:
                    snapshot_path = os.path.join(BASE_DIR, 'position_snapshot.json')
                    with open(snapshot_path, 'r', encoding='utf-8') as f:
                        payload = json.load(f)
                    self._json({'code': 1, 'data': payload})
                except FileNotFoundError:
                    self._json({'code': 0, 'msg': '暂无持仓快照'}, 404)
                except Exception as e:
                    self._json({'code': 0, 'msg': str(e)}, 500)
            elif self.path == '/':
                self._json({'code': 1, 'service': 'QUANT PRO → PTrade 信号桥', 'endpoints': [
                    '/api/etf-ranking/latest', '/api/export-ptrade-signal',
                    '/api/signal/latest', '/api/positions/latest', '/api/positions/report(POST)']})
            else:
                self._json({'code': 0, 'msg': 'not found'}, 404)
        except Exception as e:
            _log.error('请求处理异常 %s: %s', self.path, e)
            self._json({'code': 0, 'msg': str(e)}, 500)

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """P3.1: 接收PTrade持仓快照"""
        try:
            if self.path.startswith('/api/positions/report'):
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                payload = json.loads(body.decode('utf-8'))
                # 保存持仓快照
                snapshot_path = os.path.join(BASE_DIR, 'position_snapshot.json')
                with open(snapshot_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                _log.info('P3.1: 持仓快照已接收(%d只, 总值%.2f)',
                          len(payload.get('positions', [])),
                          payload.get('total_value', 0))
                self._json({'code': 1, 'msg': '持仓快照已保存'})
            else:
                self._json({'code': 0, 'msg': 'not found'}, 404)
        except Exception as e:
            _log.error('POST请求异常 %s: %s', self.path, e)
            self._json({'code': 0, 'msg': str(e)}, 500)

    def log_message(self, fmt, *args):
        _log.info('[http] %s', fmt % args)


if __name__ == '__main__':
    if '--generate' in sys.argv:
        _log.info('命令行模式：生成信号文件')
        p = generate_signal()
        sys.exit(0 if p else 1)

    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    _log.info('QUANT PRO → PTrade 信号桥已启动: http://127.0.0.1:%d', PORT)
    _log.info('  GET /api/etf-ranking/latest')
    _log.info('  GET /api/export-ptrade-signal')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        _log.info('服务已停止')
