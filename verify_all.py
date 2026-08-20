import urllib.request, json

# Test 1: API status
resp = urllib.request.urlopen('http://localhost:8000/api/stocks', timeout=10)
data = json.loads(resp.read().decode('utf-8'))
if isinstance(data, list):
    print(f'API /api/stocks: {len(data)} stocks')
else:
    print(f'API /api/stocks: {data}')

# Test 2: factor config
resp2 = urllib.request.urlopen('http://localhost:8000/api/factor-config', timeout=5)
cfg = json.loads(resp2.read().decode('utf-8'))
print(f'API /api/factor-config: blend={cfg.get("blend_ratio", {})}')

# Test 3: kline-data.json via HTTP
resp3 = urllib.request.urlopen('http://localhost:8000/kline-data.json', timeout=5)
kl = json.loads(resp3.read().decode('utf-8'))
kd = kl.get('data', {})
first_key = next(iter(kd), None)
if first_key and isinstance(kd[first_key], list) and kd[first_key]:
    item = kd[first_key][0]
    has_date = isinstance(item, dict) and 'date' in item
    print(f'kline-data.json: {len(kd)} entries, has_date={has_date}')
    if has_date:
        print(f'  First item: {item}')
else:
    print('kline-data.json: empty or bad format')

# Test 4: Check backend is serving frontend
resp4 = urllib.request.urlopen('http://localhost:8000/', timeout=5)
html = resp4.read().decode('utf-8', errors='ignore')
print(f'Frontend: {"OK" if "<html" in html.lower() else "Not HTML"}')
