#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重建 kline-data.json — 修正格式为前端所需的 OHLC 对象数组
===========================================================
前端 cX() 要求: {code: [{close, high, low, open, volume}, ...]}
旧格式(数字数组)会被全部跳过 → ETF轮动页无K线数据
"""
import json
import os
import time
import urllib.request
import ssl
import concurrent.futures

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

DIST_DIR = r'C:\Users\86157\AppData\Local\Programs\QUANT PRO\resources\backend\QUANT_PRO_backend\_internal\app_17beuetfu9m (2)\dist'
KLINE_PATH = os.path.join(DIST_DIR, 'kline-data.json')
BACKUP_DIR = os.path.join(DIST_DIR, 'backups')
os.makedirs(BACKUP_DIR, exist_ok=True)

# 80 ETF pool (from frontend hardcoded EX array)
ETF_LIST = [
    # 宽基
    ('510300','sh'), ('510500','sh'), ('510180','sh'), ('159915','sz'),
    ('588000','sh'), ('159901','sz'), ('512100','sh'), ('588030','sh'),
    # 行业
    ('512480','sh'), ('159995','sz'), ('515030','sh'), ('515790','sh'),
    ('512690','sh'), ('512010','sh'), ('159929','sz'), ('512880','sh'),
    ('512800','sh'), ('512200','sh'), ('515880','sh'), ('512660','sh'),
    ('159870','sz'), ('516650','sh'), ('159992','sz'), ('515050','sh'),
    ('512760','sh'), ('516950','sh'), ('159869','sz'), ('515250','sh'),
    ('562500','sh'), ('159766','sz'), ('515220','sh'), ('515210','sh'),
    ('159611','sz'), ('512580','sh'), ('159825','sz'), ('515170','sh'),
    ('512980','sh'), ('159745','sz'),
    # 主题
    ('515000','sh'), ('159994','sz'), ('516160','sh'), ('515980','sh'),
    ('159806','sz'), ('515700','sh'), ('159998','sz'), ('512970','sh'),
    ('560980','sh'), ('159839','sz'), ('516070','sh'), ('159949','sz'),
    # 跨境
    ('513050','sh'), ('513130','sh'), ('159941','sz'), ('513100','sh'),
    ('513500','sh'), ('513550','sh'), ('159920','sz'), ('510900','sh'),
    ('513060','sh'), ('159747','sz'), ('513080','sh'), ('513520','sh'),
    ('159509','sz'), ('513030','sh'), ('513880','sh'), ('159329','sz'),
    ('159740','sz'), ('159309','sz'),
    # 债券
    ('511010','sh'), ('511260','sh'), ('511220','sh'), ('511030','sh'),
    ('511380','sh'),
    # 商品
    ('518880','sh'), ('159934','sz'), ('518800','sh'), ('159981','sz'),
    ('159980','sz'), ('161226','sz'),
    # 红利(标记为跨境但实际是)
    ('510880','sh'),
]

SINA_KLINE_URL = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'

def fetch_sina_kline(symbol, datalen=125):
    """从新浪API获取日K线(OHLC格式)"""
    url = f'{SINA_KLINE_URL}?symbol={symbol}&scale=240&datalen={datalen}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://finance.sina.com.cn/',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        text = resp.read().decode('utf-8', errors='ignore')
        raw = json.loads(text)
        if not isinstance(raw, list):
            return None
        kline = []
        for item in raw:
            kline.append({
                'day': item.get('day', ''),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('volume', 0)),
            })
        return kline
    except Exception as e:
        print(f'  ERROR {symbol}: {e}')
        return None

def fetch_one(args):
    code, prefix = args
    symbol = f'{prefix}{code}'
    kline = fetch_sina_kline(symbol)
    if kline:
        print(f'  OK {code}: {len(kline)} pts')
    else:
        print(f'  FAIL {code}')
    return code, kline

def main():
    print('=== 重建 kline-data.json (OHLC对象格式) ===')
    print(f'ETF count: {len(ETF_LIST)}')

    # Backup existing file
    if os.path.exists(KLINE_PATH):
        ts = time.strftime('%Y%m%d_%H%M%S')
        backup = os.path.join(BACKUP_DIR, f'kline-data_{ts}.json')
        os.rename(KLINE_PATH, backup)
        print(f'Backed up to: {backup}')

    # Fetch ETF kline data (parallel)
    print('\nFetching ETF klines from Sina API...')
    etf_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(fetch_one, ETF_LIST))

    for code, kline in results:
        if kline:
            etf_data[code] = kline

    print(f'\nETF success: {len(etf_data)}/{len(ETF_LIST)}')

    # Fetch stock klines from Sina API (with dates, same as ETFs)
    print('\nFetching stock klines from Sina API...')
    try:
        req = urllib.request.Request('http://localhost:8000/api/stocks',
            headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=30)
        d = json.loads(resp.read().decode('utf-8'))
        stocks = d.get('stocks', [])
        stock_list = []
        for s in stocks:
            code = s['code']
            prefix = 'sh' if code.startswith(('6', '9', '5')) else 'sz'
            stock_list.append((code, prefix))
    except Exception as e:
        print(f'Stock list fetch error: {e}')
        stock_list = []

    stock_data = {}
    if stock_list:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(fetch_one, stock_list))
        for code, kline in results:
            if kline:
                stock_data[code] = kline
    print(f'Stocks: {len(stock_data)}/{len(stock_list)}')

    # Merge: ETF data takes priority
    all_data = {}
    all_data.update(stock_data)
    all_data.update(etf_data)

    payload = {
        'date': time.strftime('%Y-%m-%d'),
        'updatedAt': time.strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(all_data),
        'data': all_data,
    }

    with open(KLINE_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    print(f'\n=== Done ===')
    print(f'Total: {len(all_data)} ({len(etf_data)} ETFs + {len(stock_data)} stocks)')
    print(f'File: {KLINE_PATH}')
    print(f'Size: {os.path.getsize(KLINE_PATH)} bytes')

    # Verify format
    with open(KLINE_PATH, 'r', encoding='utf-8') as f:
        verify = json.load(f)
    sample = verify['data']['510300'][0]
    print(f'\nVerify 510300 first entry: {sample}')
    assert 'close' in sample and 'high' in sample and 'low' in sample, 'Format check FAILED'
    print('Format check: PASS')

if __name__ == '__main__':
    main()
