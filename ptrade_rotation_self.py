# -*- coding: utf-8 -*-
"""
PTrade ETF 轮动 Top3 策略 — 对齐 v3.1-A 日志约束
======================================================
环境约束（依据 LogEngine 实测）：
  - log 仅有 info / error 两个方法（无 warn）
  - log.info / log.error 只接受单个字符串（先 % 格式化）
其余 API 调用方式与 v3.1-A 一致（已跑通回测）：
  - 日期: context.current_dt + str(today.date())
  - K线: get_history(count, '1d', fields, code)
  - 当前价: get_history(5, '1d', 'close', code) 末位
  - 下单: order(code, vol, limit_price=...)
逻辑：20日涨幅>2% 且 现价>MA20 → 买入，按20日涨幅取 Top3
"""
import numpy as np


def initialize(context):
    g.etf_pool = ['512010.SS', '159992.SZ', '512690.SS', '159929.SZ', '512480.SS',
                  '515880.SS', '512760.SS', '588000.SS', '515030.SS',
                  '515790.SS', '159934.SZ', '518880.SS', '159980.SZ', '159915.SZ',
                  '510300.SS', '510500.SS', '513050.SS', '159941.SZ', '513100.SS']
    g.top_n = 3
    g.vol_per = 10000          # 建议股数
    g.max_amount = 50000       # 单笔金额上限
    g.last_date = None
    g.bought_codes = []        # 当日已买入代码（防重复）

    log.info("=" * 56)
    log.info("ETF轮动Top3 (20日涨幅动量) 标的数:%d Top%d 每只%d股" % (
        len(g.etf_pool), g.top_n, g.vol_per))
    log.info("=" * 56)


def get_ohlc(code, count=25):
    df = get_history(count, '1d', ['open', 'high', 'low', 'close', 'volume'], code)
    if df is None or len(df) < 21:
        return None
    return df


def handle_data(context, data):
    try:
        today = context.current_dt
        today_str = str(today.date())
        if g.last_date == today_str:
            return
        g.last_date = today_str
        g.bought_codes = []

        # 1) 逐只计算 20日涨幅 + MA20
        ranked = []
        for code in g.etf_pool:
            try:
                df = get_ohlc(code, 25)
                if df is None:
                    continue
                closes = df['close'].values.flatten().astype(float)
                highs = df['high'].values.flatten().astype(float)
                if len(closes) < 21:
                    continue
                price = float(closes[-1])
                chg20 = (price - closes[-21]) / closes[-21] * 100
                ma20 = float(np.mean(closes[-20:]))
                high20 = float(np.max(highs[-20:]))
                dist = (high20 - price) / high20 * 100 if high20 > 0 else 0
                if chg20 > 2 and price > ma20:
                    ranked.append([code, chg20, price, dist])
            except Exception as e:
                log.info("【轮动】%s 计算异常: %s" % (code, e))

        if not ranked:
            log.info("【轮动】%s 无买入信号" % today_str)
            return

        # 2) 20日涨幅降序 → Top3
        ranked.sort(key=lambda x: x[1], reverse=True)
        top = ranked[:g.top_n]
        log.info("【轮动】%s Top%d: %s" % (
            today_str, g.top_n,
            " ".join("%s %.2f%%" % (c, v) for c, v, _, _ in top)))

        # 3) 下单
        for code, chg20, price, dist in top:
            _buy(context, code, price, chg20, dist)
    except Exception as e:
        log.error("handle_data异常: %s" % str(e))


def _pos_amount(pos):
    """兼容 PTrade Position（dict 风格 pos['amount'] / 属性 pos.amount）"""
    if pos is None:
        return 0
    try:
        return int(pos['amount'])
    except Exception:
        pass
    try:
        return int(getattr(pos, 'amount', 0))
    except Exception:
        return 0


def _buy(context, code, price, chg20, dist):
    if code in g.bought_codes:
        return
    # 已持仓跳过（amount 下标/属性兼容）
    try:
        pos = context.portfolio.positions.get(code)
        if _pos_amount(pos) > 0:
            log.info("【轮动】%s 已持仓，跳过" % code)
            g.bought_codes.append(code)
            return
    except Exception:
        pass
    # 数量与风控
    vol = g.vol_per
    if price * vol > g.max_amount:
        vol = int(g.max_amount / price / 100) * 100
    cash = getattr(context.portfolio, 'cash', 0) or 0
    if price * vol > cash:
        vol = int(cash / price / 100) * 100
        if vol <= 0:
            log.info("【轮动】%s 余额不足，放弃" % code)
            g.bought_codes.append(code)
            return
    order(code, vol, limit_price=round(price * 1.01, 3))
    g.bought_codes.append(code)
    log.info("【买入】%s %d股 @%.3f 金额%.0f | 20日涨幅%.2f%% 距高点%.1f%%" % (
        code, vol, price, price * vol, chg20, dist))
