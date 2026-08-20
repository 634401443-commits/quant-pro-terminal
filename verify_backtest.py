import urllib.request, json

# Simulate what the frontend does: fetch kline-data.json and check format
resp = urllib.request.urlopen('http://localhost:8000/kline-data.json', timeout=10)
kl = json.loads(resp.read().decode('utf-8'))
kd = kl.get('data', {})

print(f"kline-data.json: {len(kd)} entries")

# Check first 3 entries have proper format
ok_count = 0
bad_count = 0
sample_codes = list(kd.keys())[:5]

for code in sample_codes:
    arr = kd[code]
    if arr and isinstance(arr[0], dict) and 'date' in arr[0] and 'close' in arr[0]:
        ok_count += 1
        print(f"  {code}: {len(arr)} bars, date={arr[0]['date']}, close={arr[0]['close']}")
    else:
        bad_count += 1
        print(f"  {code}: BAD FORMAT, first={arr[0] if arr else 'empty'}")

# Count total valid entries (with date + close fields)
valid = 0
for code, arr in kd.items():
    if arr and isinstance(arr[0], dict) and 'date' in arr[0] and 'close' in arr[0]:
        valid += 1

print(f"\nValid entries (with date+close): {valid}/{len(kd)}")

# Simulate backtest: check if 000001 (benchmark) has enough data
benchmark = kd.get('000001', [])
if benchmark:
    print(f"\nBenchmark 000001: {len(benchmark)} bars")
    if len(benchmark) >= 30:
        print("  >= 30 bars: OK for backtest")
    else:
        print("  < 30 bars: NOT enough for backtest")
else:
    print("\nBenchmark 000001: MISSING")

# Check ETF pool entries
etf_codes = ['510300', '159915', '513100', '513500', '159934']
print("\nETF pool check:")
for code in etf_codes:
    arr = kd.get(code, [])
    if arr and isinstance(arr[0], dict) and 'date' in arr[0]:
        print(f"  {code}: {len(arr)} bars, OK")
    elif arr:
        print(f"  {code}: {len(arr)} bars, BAD FORMAT")
    else:
        print(f"  {code}: MISSING")
