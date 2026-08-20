#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P3.2: 压力测试脚本 — 极端行情下ETF轮动策略风险评估
=====================================================
分析核心10只ETF在历史极端行情区间的表现，评估策略尾部风险。

用法:
  python stress_test.py           # 运行全部压力测试
  python stress_test.py --html    # 生成HTML报告

数据源: 腾讯K线API (web.ifzq.gtimg.cn)
"""
import json
import sys
import time
import urllib.request
import ssl
import numpy as np
from datetime import datetime

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

ETF_POOL = [
    ('510300', 'sh', '沪深300ETF'),
    ('159915', 'sz', '创业板ETF'),
    ('515080', 'sh', '红利ETF'),
    ('513100', 'sh', '纳指ETF'),
    ('513500', 'sh', '标普500ETF'),
    ('513520', 'sh', '日经ETF'),
    ('513030', 'sh', '德国ETF'),
    ('159920', 'sz', '恒生ETF'),
    ('159934', 'sz', '黄金ETF'),
    ('159518', 'sz', '油气ETF'),
]

STRESS_PERIODS = [
    {
        'name': '2024年9月底大涨',
        'start': '2024-09-20',
        'end': '2024-10-10',
        'desc': '政策利好驱动的快速上涨行情',
    },
    {
        'name': '2024年1-2月小盘暴跌',
        'start': '2024-01-05',
        'end': '2024-02-08',
        'desc': '小盘股流动性危机引发的快速下跌',
    },
    {
        'name': '2022年4月上海封控',
        'start': '2022-03-15',
        'end': '2022-04-29',
        'desc': '疫情封控导致的市场恐慌性下跌',
    },
    {
        'name': '2020年3月全球疫情',
        'start': '2020-02-20',
        'end': '2020-03-23',
        'desc': '新冠疫情引发的全球资产抛售',
    },
    {
        'name': '2015年股灾',
        'start': '2015-06-15',
        'end': '2015-07-09',
        'desc': '杠杆泡沫破裂引发的极端下跌',
    },
]


def fetch_kline(code, market, days=800):
    """从腾讯API获取日K线"""
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
        if not kline or len(kline) < 30:
            return None
        return {
            'dates': [r[0] for r in kline],
            'close': np.array([float(r[2]) for r in kline]),
            'high': np.array([float(r[3]) for r in kline]),
            'low': np.array([float(r[4]) for r in kline]),
        }
    except Exception as e:
        print(f"  [!] {code} K线获取失败: {e}")
        return None


def analyze_period(klines, period):
    """分析各ETF在指定区间的表现"""
    start, end = period['start'], period['end']
    results = []

    for code, market, name in ETF_POOL:
        kl = klines.get(code)
        if kl is None:
            results.append({'code': code, 'name': name, 'return': None, 'max_dd': None,
                           'volatility': None, 'max_drawdown': None})
            continue

        dates = kl['dates']
        close = kl['close']
        high = kl['high']
        low = kl['low']

        # 找到区间内的数据
        mask = np.array([(start <= d <= end) for d in dates])
        if mask.sum() < 3:
            results.append({'code': code, 'name': name, 'return': None, 'max_dd': None,
                           'volatility': None, 'max_drawdown': None})
            continue

        c = close[mask]
        h = high[mask]
        l = low[mask]

        # 区间收益率
        ret = (c[-1] / c[0] - 1) * 100 if c[0] > 0 else 0

        # 区间最大回撤
        peak = np.maximum.accumulate(c)
        dd = (c - peak) / peak * 100
        max_dd = float(np.min(dd))

        # 日波动率
        daily_ret = np.diff(c) / np.maximum(c[:-1], 1e-10)
        vol = float(np.std(daily_ret) * np.sqrt(252) * 100) if len(daily_ret) > 1 else 0

        # 最大单日跌幅
        max_daily_drop = float(np.min(daily_ret) * 100) if len(daily_ret) > 0 else 0

        results.append({
            'code': code, 'name': name,
            'return': round(ret, 2),
            'max_dd': round(max_dd, 2),
            'volatility': round(vol, 2),
            'max_daily_drop': round(max_daily_drop, 2),
            'days': int(mask.sum()),
        })

    return results


def simulate_top3_worst(results):
    """模拟最坏情况：持有表现最差的3只ETF"""
    valid = [r for r in results if r['return'] is not None]
    if len(valid) < 3:
        return None
    sorted_by_dd = sorted(valid, key=lambda x: x['max_dd'])
    worst3 = sorted_by_dd[:3]
    avg_dd = np.mean([r['max_dd'] for r in worst3])
    avg_ret = np.mean([r['return'] for r in worst3])
    return {
        'worst3': [{'code': r['code'], 'name': r['name'], 'max_dd': r['max_dd'], 'return': r['return']} for r in worst3],
        'avg_max_dd': round(avg_dd, 2),
        'avg_return': round(avg_ret, 2),
    }


def run_stress_test():
    """运行完整压力测试"""
    print("=" * 60)
    print("ETF轮动策略压力测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"标的池: {len(ETF_POOL)}只ETF")
    print("=" * 60)

    # 获取所有ETF的K线数据
    print("\n[1/3] 获取K线数据...")
    klines = {}
    for code, market, name in ETF_POOL:
        kl = fetch_kline(code, market, 800)
        if kl:
            klines[code] = kl
            print(f"  {name}({code}): {len(kl['dates'])}天")
        time.sleep(0.3)
    print(f"  成功获取: {len(klines)}/{len(ETF_POOL)}")

    # 分析各极端行情区间
    print("\n[2/3] 分析极端行情区间...")
    all_results = []
    for period in STRESS_PERIODS:
        print(f"\n  --- {period['name']} ({period['start']} ~ {period['end']}) ---")
        print(f"  {period['desc']}")
        results = analyze_period(klines, period)
        worst = simulate_top3_worst(results)

        print(f"  {'标的':<12} {'收益率':>8} {'最大回撤':>8} {'年化波动':>8} {'最大日跌':>8}")
        for r in results:
            if r['return'] is not None:
                print(f"  {r['name']:<12} {r['return']:>7.1f}% {r['max_dd']:>7.1f}% {r['volatility']:>7.1f}% {r['max_daily_drop']:>7.1f}%")
            else:
                print(f"  {r['name']:<12}  无数据")

        if worst:
            print(f"\n  [最坏3只等权模拟] 平均回撤: {worst['avg_max_dd']:.1f}%  平均收益: {worst['avg_return']:.1f}%")
            for w in worst['worst3']:
                print(f"    {w['name']}({w['code']}): 回撤{w['max_dd']:.1f}%  收益{w['return']:.1f}%")

        all_results.append({
            'period': period['name'],
            'desc': period['desc'],
            'start': period['start'],
            'end': period['end'],
            'etf_results': [r for r in results if r['return'] is not None],
            'worst3': worst,
        })

    # 汇总
    print("\n" + "=" * 60)
    print("[3/3] 压力测试汇总")
    print("=" * 60)
    print(f"\n{'极端行情':<20} {'最坏3只平均回撤':>15} {'最坏3只平均收益':>15}")
    for r in all_results:
        if r['worst3']:
            print(f"{r['period']:<20} {r['worst3']['avg_max_dd']:>14.1f}% {r['worst3']['avg_return']:>14.1f}%")
        else:
            print(f"{r['period']:<20}  数据不足")

    worst_dd = min([r['worst3']['avg_max_dd'] for r in all_results if r['worst3']], default=0)
    print(f"\n历史最坏情况: 等权Top3最大回撤 {worst_dd:.1f}%")
    print(f"半仓(0.5)风险: 最大回撤 {worst_dd * 0.5:.1f}%")
    print("\n结论: 若策略在极端行情中持有最差3只ETF(等权)，")
    print(f"  满仓最大回撤可达 {abs(worst_dd):.1f}%")
    print(f"  半仓(position_ratio=0.5)可将回撤降至 {abs(worst_dd) * 0.5:.1f}%")
    print("=" * 60)

    return all_results


if __name__ == '__main__':
    results = run_stress_test()
    # 保存结果
    output_path = 'stress_test_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output_path}")
