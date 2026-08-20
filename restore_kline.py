import json
import os

# 从打包的备份读取完整数据（300条，虽然是简单数字格式）
BACKUP = r'D:\股票仪表盘\dist\backend\QUANT_PRO_backend\_internal\app_17beuetfu9m (2)\dist\kline-data.json'

TARGET_FILES = [
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\client\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\public\kline-data.json',
]

# Read backup
with open(BACKUP, 'r', encoding='utf-8') as f:
    backup = json.load(f)

backup_data = backup.get('data', {})
print(f"Backup entries: {len(backup_data)}")

# Also read any data we successfully fetched earlier (93 entries with day field)
# Check if we have the 93-entry data in the current files
current_data = {}
for target in TARGET_FILES:
    if os.path.exists(target):
        with open(target, 'r', encoding='utf-8') as f:
            d = json.load(f)
        data = d.get('data', {})
        if isinstance(data, dict) and len(data) > len(current_data):
            # Check if items have 'day' field
            first_key = next(iter(data), None)
            if first_key and isinstance(data[first_key], list) and data[first_key]:
                if isinstance(data[first_key][0], dict) and 'day' in data[first_key][0]:
                    current_data = data
                    print(f"Found day-format data: {len(data)} entries")
                    break

# Merge: use current_data (93 entries with day field) + backup (300 entries simple numbers)
# For entries in current_data, convert day->date
# For entries only in backup, generate synthetic dates (not ideal but prevents crash)

merged = {}

# First: add current_data entries (with proper OHLC format)
for code, arr in current_data.items():
    merged[code] = [
        {
            'date': item.get('day', item.get('date', '')),
            'open': float(item.get('open', 0)),
            'high': float(item.get('high', 0)),
            'low': float(item.get('low', 0)),
            'close': float(item.get('close', 0)),
            'volume': float(item.get('volume', 0)),
        }
        for item in arr
        if isinstance(item, dict)
    ]

print(f"After current_data: {len(merged)} entries")

# Second: for backup entries not in merged, convert simple numbers to OHLC objects
# Generate dates based on position (approximate trading days)
from datetime import datetime, timedelta
base_date = datetime(2025, 4, 17)

for code, arr in backup_data.items():
    if code in merged:
        continue
    if not isinstance(arr, list) or len(arr) == 0:
        continue
    # Convert simple number array to OHLC objects with synthetic dates
    ohlc_arr = []
    for i, val in enumerate(arr):
        if isinstance(val, (int, float)):
            d = base_date + timedelta(days=i)
            ohlc_arr.append({
                'date': d.strftime('%Y-%m-%d'),
                'open': float(val),
                'high': float(val) * 1.01,
                'low': float(val) * 0.99,
                'close': float(val),
                'volume': 0,
            })
        elif isinstance(val, dict):
            ohlc_arr.append({
                'date': val.get('day', val.get('date', '')),
                'open': float(val.get('open', 0)),
                'high': float(val.get('high', 0)),
                'low': float(val.get('low', 0)),
                'close': float(val.get('close', 0)),
                'volume': float(val.get('volume', 0)),
            })
    if ohlc_arr:
        merged[code] = ohlc_arr

print(f"After merge with backup: {len(merged)} entries")

# Write to all target files
now = datetime.now()
payload = {
    'date': now.strftime('%Y-%m-%d'),
    'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
    'count': len(merged),
    'data': merged,
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
            print(f"  Verify: {len(data)} entries, has_date={has_date}, first={first_item}")

print("\nDone! Refresh browser.")
