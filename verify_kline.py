import json

path = r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json'
with open(path, 'r', encoding='utf-8') as f:
    d = json.load(f)

data = d.get('data', {})
first_key = next(iter(data), None)
if first_key:
    arr = data[first_key]
    if arr and isinstance(arr[0], dict):
        has_date = 'date' in arr[0]
        print(f'Entries: {len(data)}')
        print(f'First key: {first_key}')
        print(f'First item keys: {list(arr[0].keys())}')
        print(f'Has date field: {has_date}')
        print(f'First item: {arr[0]}')
    else:
        print(f'Bad format: first item type={type(arr[0])}, value={arr[0]}')
else:
    print('No data')
