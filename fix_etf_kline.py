#!/usr/bin/env python3
"""Fetch ETF kline data from Sina API and merge with existing stock data."""
import json, os, time, urllib.request, ssl
from datetime import datetime

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ETF_LIST = [
    ('510300', 'sh'), ('510500', 'sh'), ('159915', 'sz'), ('512880', 'sh'),
    ('513100', 'sh'), ('513500', 'sh'), ('159934', 'sz'), ('513050', 'sh'),
    ('513260', 'sh'), ('518880', 'sh'), ('159980', 'sz'), ('510050', 'sh'),
    ('512000', 'sh'), ('512100', 'sh'), ('588000', 'sh'), ('159901', 'sz'),
    ('510310', 'sh'), ('510330', 'sh'), ('159920', 'sz'), ('513030', 'sh'),
    ('513100', 'sh'), ('513400', 'sh'), ('159509', 'sz'), ('518880', 'sh'),
    ('162411', 'sz'), ('159937', 'sz'), ('512690', 'sh'), ('512660', 'sh'),
    ('512760', 'sh'), ('515790', 'sh'), ('515050', 'sh'), ('515030', 'sh'),
    ('515170', 'sh'), ('516160', 'sh'), ('516510', 'sh'), ('515880', 'sh'),
    ('513330', 'sh'), ('159699', 'sz'), ('159605', 'sz'), ('159601', 'sz'),
    ('159792', 'sz'), ('561360', 'sh'), ('588100', 'sh'), ('159715', 'sz'),
    ('510310', 'sh'), ('511260', 'sh'), ('511010', 'sh'), ('511020', 'sh'),
    ('511220', 'sh'), ('511260', 'sh'), ('511990', 'sh'), ('159972', 'sz'),
    ('511020', 'sh'), ('513010', 'sh'), ('159941', 'sz'), ('513030', 'sh'),
    ('513080', 'sh'), ('513330', 'sh'), ('513600', 'sh'), ('513680', 'sh'),
    ('159939', 'sz'), ('159938', 'sz'), ('513100', 'sh'), ('159949', 'sz'),
    ('159995', 'sz'), ('512480', 'sh'), ('512660', 'sh'), ('512800', 'sh'),
    ('512980', 'sh'), ('513050', 'sh'), ('513260', 'sh'), ('513360', 'sh'),
    ('513520', 'sh'), ('513550', 'sh'), ('513660', 'sh'), ('513900', 'sh'),
    ('159920', 'sz'), ('159941', 'sz'), ('159942', 'sz'), ('159943', 'sz'),
]

def fetch_sina_kline(code, market, datalen=80):
    url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen={datalen}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn/",
        })
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            data = json.loads(resp.read().decode('utf-8', errors='ignore'))
        if not data or len(data) < 10:
            return None
        return [
            {
                'date': r['day'],
                'open': float(r['open']),
                'high': float(r['high']),
                'low': float(r['low']),
                'close': float(r['close']),
                'volume': float(r.get('volume', 0)),
            }
            for r in data
        ]
    except Exception as e:
        print(f"  [!] {code} failed: {e}")
        return None

def main():
    print("=" * 60)
    print("ETF K-line data fetcher")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Load existing backup data
    backup_path = r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\client\kline-data.json'
    with open(backup_path, 'r', encoding='utf-8') as f:
        backup = json.load(f)
    existing_data = backup.get('data', {})
    print(f"\nExisting data: {len(existing_data)} entries")

    # Fetch ETF data
    print(f"\nFetching {len(ETF_LIST)} ETFs...")
    etf_data = {}
    seen = set()
    for i, (code, market) in enumerate(ETF_LIST):
        if code in seen:
            continue
        seen.add(code)
        kl = fetch_sina_kline(code, market, 80)
        if kl:
            etf_data[code] = kl
            print(f"  [{len(etf_data):3d}] {code}: {len(kl)} bars OK")
        time.sleep(0.2)

    print(f"\nFetched {len(etf_data)} ETFs successfully")

    # Merge
    merged = {}
    merged.update(existing_data)
    merged.update(etf_data)
    print(f"Merged total: {len(merged)} entries ({len(existing_data)} stocks + {len(etf_data)} ETFs)")

    # Write to all target files
    now = datetime.now()
    payload = {
        'date': now.strftime('%Y-%m-%d'),
        'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'count': len(merged),
        'data': merged,
    }

    targets = [
        r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json',
        r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\client\kline-data.json',
        r'D:\股票仪表盘\app_17beuetfu9m (2)\public\kline-data.json',
    ]

    for t in targets:
        try:
            os.makedirs(os.path.dirname(t), exist_ok=True)
            with open(t, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
            print(f"  Written: {t} ({os.path.getsize(t)} bytes)")
        except Exception as e:
            print(f"  [!] Write error {t}: {e}")

    print("\nDone!")

if __name__ == '__main__':
    main()
