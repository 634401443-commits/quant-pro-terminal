#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 kline-data.json 格式 — 将简单数字数组转为带day字段的OHLC对象数组
直接修复 D:\股票仪表盘 下的所有 kline-data.json 副本

用法: python fix_kline_format.py
"""
import json
import os
import time
import urllib.request
import ssl
import numpy as np
from datetime import datetime

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 需要修复的文件列表
TARGET_FILES = [
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\dist\client\kline-data.json',
    r'D:\股票仪表盘\app_17beuetfu9m (2)\public\kline-data.json',
]

def fetch_kline(code, market, days=80):
    """从腾讯API获取日K线（带日期）"""
    param = f"{market}{code},day,,,{days},qfq"
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
        return kline  # 原始格式: [date, open, close, high, low, volume, ...]
    except Exception as e:
        print(f"  [!] {code} 获取失败: {e}")
        return None


def main():
    print("=" * 60)
    print("kline-data.json 格式修复工具")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 读取现有的 kline-data.json 获取股票列表
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
        print("[!] 未找到现有 kline-data.json 或数据为空")
        return

    print(f"\n找到 {len(stock_list)} 只股票/ETF")

    # 逐个获取K线数据（带日期）
    print("\n[1/3] 获取K线数据（带日期）...")
    kline_data = {}
    for i, code in enumerate(stock_list):
        market = 'sh' if code.startswith('6') else 'sz'
        kl = fetch_kline(code, market, 80)
        if kl:
            kline_data[code] = kl
            if (i + 1) % 50 == 0:
                print(f"  进度: {i+1}/{len(stock_list)} ({len(kline_data)} 成功)")
        time.sleep(0.15)  # 避免限频

    print(f"\n  成功获取: {len(kline_data)}/{len(stock_list)}")

    # 转换为OHLC对象格式
    print("\n[2/3] 转换为OHLC对象格式...")
    ohlc_data = {}
    for code, kl in kline_data.items():
        ohlc_data[code] = [
            {
                'date': r[0],
                'open': float(r[1]),
                'close': float(r[2]),
                'high': float(r[3]),
                'low': float(r[4]),
                'volume': float(r[5]) if len(r) > 5 else 0,
            }
            for r in kl
        ]

    # 写入所有目标文件
    print(f"\n[3/3] 写入 {len(TARGET_FILES)} 个目标文件...")
    now = datetime.now()
    payload = {
        'date': now.strftime('%Y-%m-%d'),
        'updatedAt': now.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        'count': len(ohlc_data),
        'data': ohlc_data,
    }

    for target in TARGET_FILES:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
            print(f"  [OK] {target}")
        except Exception as e:
            print(f"  [FAIL] {target}: {e}")

    # 验证
    print("\n验证...")
    for target in TARGET_FILES:
        if os.path.exists(target):
            with open(target, 'r', encoding='utf-8') as f:
                d = json.load(f)
            data = d.get('data', {})
            if isinstance(data, dict):
                first_key = next(iter(data), None)
                if first_key and isinstance(data[first_key], list) and data[first_key]:
                    first_item = data[first_key][0]
                    has_day = 'day' in first_item if isinstance(first_item, dict) else False
                    print(f"  {os.path.basename(os.path.dirname(target))}: {len(data)}条, day字段={'有' if has_day else '无'}")
                else:
                    print(f"  {os.path.basename(os.path.dirname(target))}: 数据格式异常")
            else:
                print(f"  {os.path.basename(os.path.dirname(target))}: data不是dict")

    print("\n" + "=" * 60)
    print("修复完成！请刷新浏览器页面。")
    print("=" * 60)


if __name__ == '__main__':
    main()
