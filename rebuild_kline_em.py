import json
import os
import time
import urllib.request
import ssl
from datetime import datetime

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

TARGET_FILES = [
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\client\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\public\kline-data.json',
]

# Read stock list from one of the existing files
stock_list = []
for target in TARGET_FILES:
    if os.path.exists(target):
        with open(target, 'r', encoding='utf-8') as f:
            d = json.load(f)
        data = d.get('data', {})
        if isinstance(data, dict) and len(data) > len(stock_list):
            stock_list = list(data.keys())
        break

if not stock_list:
    # Read from the backup
    backup = r'D:\股票仪表盘\dist\backend\QUANT_PRO_backend\_internal\app_17beuetfu9m (2)\dist\kline-data.json'
    if os.path.exists(backup):
        with open(backup, 'r', encoding='utf-8') as f:
            d = json.load(f)
        stock_list = list(d.get('data', {}).keys())

print(f"Stock list: {len(stock_list)} items")


def fetch_kline_sina(code):
    """从新浪API获取K线"""
    market = 'sh' if code.startswith('6') else 'sz'
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={market}{code}&scale=240&ma=no&datalen=80"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn/",
        })
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            text = resp.read().decode('utf-8', errors='ignore')
        data = json.loads(text)
        if not data or not isinstance(data, list):
            return None
        # Convert: day->date, string values->float
        return [
            {
                'date': item.get('day', ''),
                'open': float(item.get('open', 0)),
                'high': float(item.get('high', 0)),
                'low': float(item.get('low', 0)),
                'close': float(item.get('close', 0)),
                'volume': float(item.get('volume', 0)),
            }
            for item in data
        ]
    except Exception as e:
        return None


def fetch_kline_tencent(code):
    """从腾讯API获取K线"""
    market = 'sh' if code.startswith('6') else 'sz'
    param = f"{market}{code},day,,,80,qfq"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={param}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://finance.sina.com.cn/",
        })
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as resp:
            d = json.loads(resp.read().decode('utf-8', errors='ignore'))
        key = f"{market}{code}"
        data = d.get('data', {})
        if not isinstance(data, dict):
            return None
        inner = data.get(key, {})
        if not isinstance(inner, dict):
            return None
        kline = inner.get('qfqday') or inner.get('day')
        if not kline or len(kline) < 10:
            return None
        # Convert to [{date, open, close, high, low, volume}, ...]
        return [
            {
                'date': r[0],
                'open': float(r[1]),
                'close': float(r[2]),
                'high': float(r[3]),
                'low': float(r[4]),
                'volume': float(r[5]) if len(r) > 5 else 0,
            }
            for r in kline
        ]
    except Exception as e:
        return None


# Try both APIs
print("\nFetching kline data...")
kline_data = {}
api_errors = {'sina': 0, 'tencent': 0}

for i, code in enumerate(stock_list):
    # Try Sina first, then Tencent
    kl = fetch_kline_sina(code)
    if kl:
        kline_data[code] = kl
        api_errors['sina'] = 0
    else:
        api_errors['sina'] += 1
        # Fall back to Tencent
        kl = fetch_kline_tencent(code)
        if kl:
            kline_data[code] = kl
            api_errors['tencent'] = 0
        else:
            api_errors['tencent'] += 1

    if (i + 1) % 50 == 0:
        print(f"  Progress: {i+1}/{len(stock_list)} ({len(kline_data)} success)")
    
    # If too many consecutive Sina errors, switch to Tencent only
    if api_errors['sina'] >= 10:
        time.sleep(1)
        api_errors['sina'] = 0
    
    time.sleep(0.15)

print(f"\nSuccess: {len(kline_data)}/{len(stock_list)}")

if len(kline_data) == 0:
    print("\n[!] All APIs failed. Trying Sina with longer delay...")
    for i, code in enumerate(stock_list[:10]):
        kl = fetch_kline_sina(code)
        if kl:
            kline_data[code] = kl
            print(f"  Sina OK: {code}")
        else:
            print(f"  Sina FAIL: {code}")
        time.sleep(2)

if len(kline_data) == 0:
    print("\n[ERROR] Cannot fetch any kline data. All APIs blocked.")
    print("Please try again later or use a different network.")
    exit(1)

# Write to all target files
now = datetime.now()
payload = {
    'date': now.strftime('%Y-%m-%d'),
    'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    'count': len(kline_data),
    'data': kline_data,
}

for target in TARGET_FILES:
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, default=str)
        print(f"  [OK] {target}")
    except Exception as e:
        print(f"  [FAIL] {target}: {e}")

# Verify
for target in TARGET_FILES:
    if os.path.exists(target):
        with open(target, 'r', encoding='utf-8') as f:
            d = json.load(f)
        data = d.get('data', {})
        first_key = next(iter(data), None)
        if first_key and isinstance(data[first_key], list) and data[first_key]:
            first_item = data[first_key][0]
            has_date = isinstance(first_item, dict) and 'date' in first_item
            print(f"  Verify {os.path.basename(os.path.dirname(target))}: {len(data)} entries, has_date={has_date}")

print("\nDone! Refresh browser.")
