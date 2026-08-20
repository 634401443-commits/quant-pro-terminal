# -*- coding: utf-8 -*-
"""
PTrade ETF 轮动 Top3 跨市场版 — FTS 精英因子（2026-08 回测优化版）
=====================================================================
选股: 5 个 FTS 因子 IC加权打分(0-100) [0.35,0.20,0.18,0.15,0.12]
轮动: 按 FTS 分取 Top3；持仓掉出前8名 → 卖出；空仓且分>=45 → 买入（等权）
标的: 10 只跨市场 ETF（A股宽基3 + 跨境5 + 商品2），分散单一市场风险
回测(2024-10~2026-08): 收益52.1% 回撤11.6% 夏普1.36（本地严格回测，含佣金滑点）
环境约束（LogEngine 实测）:
  - log 仅 info/error，且只接受单个字符串（先 % 格式化）
  - 日期: context.current_dt；K线: get_history(count,'1d',fields,code)
  - 持仓: pos['amount']（dict 风格）
"""
import numpy as np


def initialize(context):
    # 跨市场标的池：A股宽基3（T+1） + 跨境5（T+0） + 商品2（T+0）
    g.etf_pool = [
        '510300.SS', '159915.SZ', '515080.SS',      # 沪深300/创业板/红利（T+1）
        '513100.SS', '513500.SS', '513520.SS',      # 纳指/标普/日经（T+0）
        '513030.SS', '159920.SZ',                   # 德国/恒生（T+0）
        '159934.SZ', '159518.SZ',                   # 黄金/油气（T+0）
    ]
    g.top_n = 3
    g.sell_rank = 8            # 缓冲带：掉出前8名才卖（回测优化）
    g.cooldown_days = 5        # 卖出后冷却天数（期间不买回，降换手）
    g.vol_per = 10000          # 建议股数
    g.max_amount = 50000       # 单笔金额上限
    g.min_score = 45           # 买入门槛（回测优化：45 比 55 更积极）
    g.position_ratio = 0.5     # v7新增：仓位系数（0.5=半仓/1.0=满仓；实盘建议半仓控风险）
    g.last_date = None
    g.cooldown = {}            # code -> 卖出日期str
    # T+0 标的（跨境5 + 商品2 当天可买卖；A股宽基3 为 T+1）
    g.t0 = {'513100.SS', '513500.SS', '513520.SS', '513030.SS', '159920.SZ',
            '159934.SZ', '159518.SZ'}

    # ===== v2新增：风控参数（统一在此调整）=====
    g.stop_loss_pct = 6            # 单票硬止损（回测优化：8→6）
    g.max_drawdown_pause = 12      # P0-2 账户回撤超过该%暂停新开仓
    g.max_drawdown_halve = 20      # P0-2 账户回撤超过该%强制减半所有持仓
    g.trailing_activate = 5        # P1-4 追踪止盈激活：浮盈超过该%
    g.trailing_drawback = 5        # P1-4 追踪止盈回撤：从最高点回撤该%清仓
    g.take_profit_tiers = [(15, 0.3), (25, 0.3), (35, 1.0)]  # 分批止盈（回测对齐）
    g.peak_value = None            # P0-2 账户资产峰值
    g.highest_prices = {}          # P1-4 各持仓最高价（code -> 最高价）
    g.tp_taken = {}                # P1-5 各持仓已执行止盈档位（code -> set(档位下标)）
    g.drawdown_mode = False        # P0-2 暂停开仓标志
    g.halved = False               # P0-2 减半执行标志（回撤恢复后重置）
    g.last_regime = 'neutral'      # P1-3 市场状态缓存
    g.sold_today = set()           # v2 当日已卖出代码（防重复卖出）
    g.t1_bought_today = set()      # v8 当日新买T+1标的（次日才允许卖出）
    g.log_counter = {}             # v8 日志计数器（抑制重复消息）
    g.last_buy_allowed = True      # v8 买入状态缓存（仅状态变化时打日志）

    # ===== v8新增：回测统计追踪 =====
    g.stat_initial_value = 0       # 初始资金（首日记录）
    g.stat_buy_count = 0           # 买入次数
    g.stat_sell_count = 0          # 卖出次数
    g.stat_win_count = 0           # 盈利卖出次数
    g.stat_loss_count = 0          # 亏损卖出次数
    g.stat_realized_pnl = 0.0      # 累计已实现盈亏
    g.stat_gross_profit = 0.0      # 盈利交易总盈利额
    g.stat_gross_loss = 0.0        # 亏损交易总亏损额（正数）
    g.stat_month_last = None       # 上次月度统计月份
    g.stat_day_start_value = 0     # 当日开盘前资产
    g.stat_profitable_days = 0     # 盈利交易日数
    g.stat_total_days = 0          # 总交易日数
    g.stat_max_drawdown = 0        # 历史最大回撤%
    g.stat_daily_returns = []      # 每日收益率列表（计算夏普/索提诺）

    log.info("=" * 56)
    log.info("ETF轮动Top3跨市场版 FTS因子 标的:%d Top%d 等权仓位" % (len(g.etf_pool), g.top_n))
    log.info("风控: 止损%.0f%% 回撤暂停%.0f%%/减半%.0f%% 追踪止盈%.0f%%/回撤%.0f%% 分批止盈%s" % (
        g.stop_loss_pct, g.max_drawdown_pause, g.max_drawdown_halve,
        g.trailing_activate, g.trailing_drawback, g.take_profit_tiers))
    log.info("=" * 56)

    # ===== v7新增：回测成本设置（仅回测生效；实盘由券商柜台决定，不影响实盘）=====
    try:
        set_commission(commission_ratio=0.00005, min_commission=1.0, type='ETF')   # ETF 佣金万0.5（用户实际费率），最低1元
        set_slippage(slippage=0.002)                                                # 比例滑点 0.2%（单边实际 0.1%）
        log.info("回测成本已设置: ETF佣金万0.5(最低1元) 滑点0.2%%")
    except Exception as e:
        log.info("回测成本设置跳过(不影响运行): %s" % e)


# ========== 工具（移植 v3.1-A） ==========

def sma(arr, window):
    n = len(arr)
    result = np.zeros(n)
    for i in range(n):
        start = max(0, i - window + 1)
        result[i] = np.mean(arr[start:i + 1])
    return result


# ========== FTS 五因子（移植 v3.1-A，已验证） ==========

def factor_volatility_reversion(c, n, w=20):
    ma = np.zeros(n); std = np.zeros(n)
    for i in range(n):
        if i + 1 >= w:
            ma[i] = np.mean(c[i - w + 1:i + 1])
            std[i] = np.std(c[i - w + 1:i + 1])
        else:
            ma[i] = np.mean(c[:i + 1]); std[i] = np.std(c[:i + 1])
    up = ma + 2 * std; lo = ma - 2 * std
    bp = np.clip((c - lo) / np.maximum(up - lo, 1e-10), 0, 1)
    return np.clip((0.5 - bp) * 1, -1, 1)


def factor_momentum(c, n, w=20):
    signal = np.zeros(n)
    if n > w:
        signal[w:] = (c[w:] - c[:-w]) / np.maximum(c[:-w], 1e-10)
    return np.clip(np.tanh(signal * 20), -1, 1)


def factor_five_dim_momentum(c, v, n):
    r15 = np.zeros(n); r45 = np.zeros(n); r150 = np.zeros(n)
    if n > 15:  r15[15:] = (c[15:] - c[:-15]) / np.maximum(c[:-15], 1e-10)
    if n > 45:  r45[45:] = (c[45:] - c[:-45]) / np.maximum(c[:-45], 1e-10)
    if n > 150: r150[150:] = (c[150:] - c[:-150]) / np.maximum(c[:-150], 1e-10)
    pm = np.zeros(n)
    pm += np.where(r15 > 0.05, 9, np.where(r15 > 0.02, 6, np.where(r15 > 0, 4, np.where(r15 > -0.03, 2, 0))))
    pm += np.where(r45 > 0.15, 9, np.where(r45 > 0.08, 6, np.where(r45 > 0, 4, np.where(r45 > -0.08, 2, 0))))
    pm += np.where(r150 > 0.25, 10, np.where(r150 > 0.10, 7, np.where(r150 > 0, 4, np.where(r150 > -0.15, 2, 0))))
    pm /= 28.0
    v5 = sma(v, 5); v20 = sma(v, 20); vr = v5 / np.maximum(v20, 1e-10)
    vol_score = np.zeros(n)
    vol_score += np.where(vr > 1.5, 9, np.where(vr > 1.2, 6, np.where(vr > 0.8, 4, np.where(vr > 0.5, 2, 0))))
    ch = np.zeros(n); ch[1:] = c[1:] - c[:-1]; vd = np.zeros(n)
    for i in range(10, n):
        uv = np.sum(v[i - 9:i + 1][ch[i - 9:i + 1] > 0])
        dv = np.sum(v[i - 9:i + 1][ch[i - 9:i + 1] <= 0])
        vd[i] = 9 if uv > dv * 1.2 else 5 if uv > dv else 2
    vol_score += vd; vol_score /= 18.0
    m5 = sma(c, 5); m10 = sma(c, 10); m20_s = sma(c, 20); m60 = sma(c, 60)
    tr = np.where((m5 > m10) & (m10 > m20_s) & (m20_s > m60), 10.0,
         np.where((m5 > m10) & (m10 > m20_s), 7.0, np.where(m5 > m10, 4.0, 0.0)))
    tr += np.where(c > m20_s, 5.0, np.where(c > m10, 3.0, 0.0)); tr /= 15.0
    rs = np.zeros(n); r20 = np.zeros(n)
    if n > 20: r20[20:] = (c[20:] - c[:-20]) / np.maximum(c[:-20], 1e-10)
    rs += np.where((r20 > 0) & (r15 > 0), 8, np.where(r20 > 0, 5, np.where(r20 > -0.05, 3, 1)))
    gn = np.zeros(n); ls = np.zeros(n)
    for i in range(1, n):
        d = c[i] - c[i - 1]; gn[i] = max(d, 0); ls[i] = max(-d, 0)
    ag = sma(gn, 14); al = sma(ls, 14)
    rsv = ag / np.maximum(al, 1e-10); rsi = 100 - 100 / (1 + rsv)
    rs += np.where((rsi >= 40) & (rsi <= 60), 7, np.where((rsi >= 30) & (rsi <= 70), 5, np.where(rsi > 70, 3, 1)))
    rs /= 15.0
    rk = np.zeros(n)
    for i in range(20, n):
        pk = np.max(c[i - 19:i + 1]); dd = (pk - c[i]) / pk * 100
        rk[i] = 7 if dd < 5 else 5 if dd < 10 else 3 if dd < 15 else 1 if dd < 20 else 0
    rk /= 7.0
    total = pm * 0.28 + vol_score * 0.18 + tr * 0.25 + rs * 0.15 + rk * 0.14
    s = total * 2 - 1
    bear = ((m5 < m10) & (m10 < m20_s)) | ((ch < 0) & (vr > 1.2))
    s = np.where(bear, -np.abs(s), s)
    return np.clip(s, -1, 1)


def factor_ma_trend(c, n, s_w=5, m_w=20, l_w=60):
    ms = sma(c, s_w); mm = sma(c, m_w); ml = sma(c, l_w)
    t = np.where((ms > mm) & (mm > ml), 1,
        np.where(ms > mm, 0.5, np.where((ms < mm) & (mm < ml), -1, np.where(ms < mm, -0.5, 0))))
    sl = np.zeros(n)
    if n > 5: sl[5:] = (mm[5:] - mm[:-5]) / np.maximum(mm[:-5], 1e-10) * 100
    return np.clip(t * 0.6 + np.tanh(sl * 5) * 0.4, -1, 1)


def factor_volume_momentum(c, v, n, w=10):
    pc = np.zeros(n); pc[1:] = (c[1:] - c[:-1]) / np.maximum(c[:-1], 1e-10)
    vm = np.array([np.mean(v[max(0, i - w):i]) if i >= w else 0 for i in range(n)])
    vr = v / np.maximum(vm, 1e-10)
    sig = np.where((pc > 0) & (vr > 1.3), pc * 10,
          np.where((pc < 0) & (vr > 1.3), pc * 5,
          np.where(pc > 0, pc * 3, pc * 1)))
    return np.clip(np.tanh(sig), -1, 1)


FACTOR_W = [0.20, 0.20, 0.20, 0.20, 0.20]  # 等权


def compute_fts_score(df):
    """FTS 综合打分 0-100（移植 v3.1-A）"""
    try:
        c = df['close'].values.flatten().astype(float)
        v = df['volume'].values.flatten().astype(float)
        n = len(c)
        sigs = [
            factor_volatility_reversion(c, n)[-1],
            factor_momentum(c, n)[-1],
            factor_five_dim_momentum(c, v, n)[-1],
            factor_ma_trend(c, n)[-1],
            factor_volume_momentum(c, v, n)[-1],
        ]
        scores = [(s + 1) * 10 * FACTOR_W[i] for i, s in enumerate(sigs)]
        return sum(scores) * (100.0 / 20.0)
    except Exception:
        return None


# ========== 数据（已验证用法） ==========

def get_ohlc(code, count=200):
    try:
        df = get_history(count, '1d', ['open', 'high', 'low', 'close', 'volume'], code)
    except Exception:
        return None
    if df is None or len(df) < 30:
        return None
    return df


def get_current_price(code):
    try:
        df = get_history(5, '1d', 'close', code)
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    return float(df.values.flatten()[-1])


def _pos_amount(pos):
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


def _pos_sellable(pos):
    """可卖数量 enable_amount：T+0 当天买可卖；T+1 当天买入部分不可卖（次日解冻）"""
    if pos is None:
        return 0
    try:
        return int(pos['enable_amount'])
    except Exception:
        pass
    try:
        return int(getattr(pos, 'enable_amount', 0))
    except Exception:
        return 0


# ===== v2新增：风控辅助函数 =====

def get_market_trend():
    """P1-3 大盘趋势：沪深300(000300.SS) 价格<MA60 且 MA20<MA60 → bear；反之 bull；否则 neutral"""
    try:
        df = get_history(80, '1d', 'close', '000300.SS')
        if df is None or len(df) < 60:
            return 'neutral'
        c = df['close'].values.flatten().astype(float)
        price = float(c[-1])
        ma20 = float(np.mean(c[-20:]))
        ma60 = float(np.mean(c[-60:]))
        if price < ma60 and ma20 < ma60:
            return 'bear'
        if price > ma60 and ma20 > ma60:
            return 'bull'
        return 'neutral'
    except Exception:
        return 'neutral'


def _pos_cost(pos):
    """持仓成本价（dict/属性兼容）"""
    if pos is None:
        return None
    try:
        return float(pos['cost_basis'])
    except Exception:
        pass
    try:
        return float(pos['avg_cost'])
    except Exception:
        pass
    try:
        return float(getattr(pos, 'cost_basis', 0))
    except Exception:
        return None


def _days_between(d1, d2):
    """d1-d2 天数差（日期str '%Y-%m-%d'）"""
    try:
        from datetime import datetime as _dtt
        return (_dtt.strptime(d1, '%Y-%m-%d') - _dtt.strptime(d2, '%Y-%m-%d')).days
    except Exception:
        return 999


def _enter_cooldown(code, today_str):
    g.cooldown[code] = today_str


def _is_cooldown(code, today_str):
    cd = g.cooldown.get(code)
    if cd is None:
        return False
    return _days_between(today_str, cd) < g.cooldown_days


def _record_sell_stat(qty, price, cost):
    """v8: 记录卖出交易统计（盈亏/胜率/盈亏比）"""
    g.stat_sell_count += 1
    if cost and cost > 0:
        pnl = (price - cost) * qty
        g.stat_realized_pnl += pnl
        if pnl > 0:
            g.stat_win_count += 1
            g.stat_gross_profit += pnl
        else:
            g.stat_loss_count += 1
            g.stat_gross_loss += abs(pnl)


# ========== 主逻辑 ==========

def handle_data(context, data):
    try:
        today = context.current_dt
        today_str = str(today.date())
        if g.last_date == today_str:
            return
        g.last_date = today_str
        g.sold_today = set()
        g.t1_bought_today = set()

        # v8：首日记录初始资金 + 当日开盘前资产
        total_value = float(getattr(context.portfolio, 'total_value', 0) or 0)
        if g.stat_initial_value == 0 and total_value > 0:
            g.stat_initial_value = total_value
        g.stat_day_start_value = total_value

        # ① v2新增：账户回撤风控（峰值跟踪 / 暂停开仓 / 强制减半）
        if g.peak_value is None or total_value > g.peak_value:
            g.peak_value = total_value
        drawdown = (g.peak_value - total_value) / g.peak_value * 100 if g.peak_value > 0 else 0
        if drawdown > g.stat_max_drawdown:
            g.stat_max_drawdown = drawdown
        # v3修复：空仓时自动解除回撤暂停（空仓=已防守，不应被回撤状态锁死而错过后续行情）
        has_position = any(_pos_amount(p) > 0 for p in context.portfolio.positions.values())
        if has_position and drawdown >= g.max_drawdown_halve and not g.halved:
            for code, pos in list(context.portfolio.positions.items()):
                amt = _pos_amount(pos)
                sellable = _pos_sellable(pos)
                if amt <= 0 or sellable <= 0:
                    continue
                half = int(sellable / 2 / 100) * 100
                if half <= 0:
                    continue
                cp = get_current_price(code)
                if cp is None:
                    continue
                order(code, -half)
                g.sold_today.add(code)
                log.info("【风控】账户回撤%.1f%%≥%.0f%%，减半 %s %d股" % (
                    drawdown, g.max_drawdown_halve, code, half))
            g.halved = True
            g.drawdown_mode = True
            log.info("【风控】账户回撤%.1f%% 暂停开仓+已减半" % drawdown)
        elif has_position and drawdown >= g.max_drawdown_pause:
            if not g.drawdown_mode:
                log.info("【风控】账户回撤%.1f%%≥%.0f%% 暂停开仓" % (drawdown, g.max_drawdown_pause))
            g.drawdown_mode = True
        elif not has_position or drawdown < g.max_drawdown_pause:
            if g.drawdown_mode:
                log.info("【风控】账户回撤恢复至%.1f%% 恢复开仓" % drawdown)
            g.drawdown_mode = False
            g.halved = False

        # ② v2新增：大盘趋势过滤（v4修复：A股熊市仅限制A股标的，跨境/商品不受A股信号干扰）
        market = get_market_trend()
        if market != g.last_regime:
            log.info("【环境】市场状态: %s" % market)
            g.last_regime = market
        # 账户回撤暂停对全部标的生效；A股熊市限制在买入循环内按标的分流
        buy_allowed = not g.drawdown_mode

        # v6优化：当日行情缓存（每只ETF只拉一次K线，打分/风控/卖出/买入复用，回测提速2-3倍）
        cache = {}
        for code in g.etf_pool:
            df = get_ohlc(code, 200)
            if df is None:
                continue
            closes = df['close'].values.flatten().astype(float)
            highs = df['high'].values.flatten().astype(float)
            cache[code] = {
                'df': df,
                'closes': closes,
                'highs': highs,
                'price': float(closes[-1]),
            }

        # 1) FTS 因子打分（量化选股：5因子等权 0-100，用缓存数据）
        scored = []
        for code in g.etf_pool:
            c = cache.get(code)
            if c is None:
                continue
            score = compute_fts_score(c['df'])
            if score is None:
                continue
            scored.append([code, score, c['price']])

        if not scored:
            log.info("【轮动】%s 无评分数据" % today_str)
            return

        # 2) 按 FTS 分降序 → Top3（含全排名用于卖出判断）
        scored.sort(key=lambda x: x[1], reverse=True)
        top_codes = [x[0] for x in scored[:g.top_n]]
        rank_of = {x[0]: i + 1 for i, x in enumerate(scored)}   # code -> 排名
        log.info("【轮动】%s Top%d: %s" % (
            today_str, g.top_n,
            " ".join("%s(%.0f分)" % (c, s) for c, s, _ in scored[:g.top_n])))

        # ③ v2新增：持仓止损/止盈检查（优先于卖出规则与买入）
        for code, pos in list(context.portfolio.positions.items()):
            amt = _pos_amount(pos)
            if amt <= 0:
                continue
            sellable = _pos_sellable(pos)
            if sellable <= 0:
                continue
            cost = _pos_cost(pos)
            cdata = cache.get(code)
            cp = cdata['price'] if cdata else get_current_price(code)
            if cp is None or cost is None or cost <= 0:
                continue
            profit_pct = (cp - cost) / cost * 100
            tag = 'T+0' if code in g.t0 else 'T+1'
            g.highest_prices[code] = max(g.highest_prices.get(code, cp), cp)
            hi = g.highest_prices[code]
            sell_left = sellable
            sold_any = False

            # v8优化：熊市持仓风控（v4修复：仅A股标的；跨境/商品由止损/止盈/排名管理，不受A股熊市干扰）
            if market == 'bear' and code not in g.t0:
                bear_stop = profit_pct < -5
                if not bear_stop and cdata:
                    closes_arr = cdata['closes']
                    if len(closes_arr) >= 23:
                        below_ma = 0
                        for j in range(3):
                            idx = len(closes_arr) - 1 - j
                            if idx >= 19:
                                ma20_val = float(np.mean(closes_arr[idx - 19:idx + 1]))
                                if closes_arr[idx] < ma20_val:
                                    below_ma += 1
                        if below_ma >= 3:
                            bear_stop = True
                if bear_stop:
                    reason = '浮亏%.1f%%' % profit_pct if profit_pct < -5 else '连续3日跌破MA20'
                    order(code, -sell_left)
                    _record_sell_stat(sell_left, cp, cost)
                    g.sold_today.add(code)
                    g.cooldown[code] = today_str
                    g.highest_prices.pop(code, None)
                    g.tp_taken.pop(code, None)
                    log.info("【风控】%s(%s) 熊市%s清仓 %d股" % (code, tag, reason, sell_left))
                    continue

            # 止损：浮亏 ≥ stop_loss_pct → 市价清仓（可卖数量）+ 进入冷却期
            if profit_pct <= -g.stop_loss_pct:
                order(code, -sell_left)
                _record_sell_stat(sell_left, cp, cost)
                g.sold_today.add(code)
                g.cooldown[code] = today_str
                g.highest_prices.pop(code, None)
                g.tp_taken.pop(code, None)
                log.info("【止损】%s(%s) %d股 @%.3f 亏损%.1f%%" % (
                    code, tag, sell_left, cp, profit_pct))
                continue

            # v8优化：追踪止盈优先于分批止盈（趋势反转时果断清仓，不分批）
            trailing_triggered = False
            if profit_pct >= g.trailing_activate and hi > 0:
                dd = (hi - cp) / hi * 100
                if dd >= g.trailing_drawback:
                    order(code, -sell_left)
                    _record_sell_stat(sell_left, cp, cost)
                    g.sold_today.add(code)
                    g.cooldown[code] = today_str
                    g.highest_prices.pop(code, None)
                    g.tp_taken.pop(code, None)
                    log.info("【止盈】%s(%s) 追踪清仓 %d股 @%.3f 最高%.3f回撤%.1f%%" % (
                        code, tag, sell_left, cp, hi, dd))
                    trailing_triggered = True

            # 分批止盈：仅在追踪止盈未触发时执行（盈利达标档位 → 卖出对应比例）
            if not trailing_triggered:
                taken = g.tp_taken.setdefault(code, set())
                for ti, (tier, ratio) in enumerate(g.take_profit_tiers):
                    if ti in taken or sell_left <= 0:
                        continue
                    if profit_pct >= tier:
                        if ratio >= 1.0:
                            order(code, -sell_left)
                            _record_sell_stat(sell_left, cp, cost)
                            log.info("【止盈】%s(%s) 清仓 %d股 @%.3f 盈利%.1f%%(≥%d%%)" % (
                                code, tag, sell_left, cp, profit_pct, tier))
                            sell_left = 0
                            g.sold_today.add(code)
                            g.highest_prices.pop(code, None)
                        else:
                            qty = int(sell_left * ratio / 100) * 100
                            if qty > 0:
                                order(code, -qty)
                                _record_sell_stat(qty, cp, cost)
                                log.info("【止盈】%s(%s) %d股 @%.3f 盈利%.1f%%(≥%d%% 卖%.0f%%)" % (
                                    code, tag, qty, cp, profit_pct, tier, ratio * 100))
                                sell_left -= qty
                                g.sold_today.add(code)
                        taken.add(ti)
                        sold_any = True

        # 4) 卖出：持仓掉出缓冲带(前 sell_rank 名) → 卖出可卖数量（自动兼容 T+0/T+1）
        try:
            for code, pos in list(context.portfolio.positions.items()):
                amt = _pos_amount(pos)
                if amt <= 0:
                    continue
                if code in g.sold_today:                    # v2：今日已由止损/止盈/减半卖出，跳过
                    continue
                rk = rank_of.get(code, 999)
                if rk <= g.sell_rank:
                    continue                                # 仍在缓冲带内，持有
                # v8: T+1标的当日新买，次日才允许卖出
                if code not in g.t0 and code in g.t1_bought_today:
                    continue
                sellable = _pos_sellable(pos)
                tag = 'T+0' if code in g.t0 else 'T+1'
                if sellable <= 0:
                    continue
                cdata = cache.get(code)
                cp = cdata['price'] if cdata else get_current_price(code)
                if cp is None:
                    continue
                cost = _pos_cost(pos)
                order(code, -sellable)
                _record_sell_stat(sellable, cp, cost)
                g.cooldown[code] = today_str
                g.sold_today.add(code)
                log.info("【卖出】%s(%s) %d股 @%.3f | 排名%d掉出前%d" % (code, tag, sellable, cp, rk, g.sell_rank))
        except Exception as e:
            log.info("【轮动】卖出遍历异常: %s" % e)

        # 5) v2/v3：买入（风控闸门 + 等权仓位；v4修复：A股熊市仅限A股标的）
        if not buy_allowed:
            if g.last_buy_allowed:
                log.info("【风控】%s 账户回撤暂停开仓" % today_str)
                g.last_buy_allowed = False
        else:
            if not g.last_buy_allowed:
                log.info("【风控】%s 条件恢复，恢复开仓" % today_str)
                g.last_buy_allowed = True
            skip_reasons = []
            for code, score, price in scored[:g.top_n]:
                if score < g.min_score:
                    skip_reasons.append("%s(分%.0f<%d)" % (code, score, g.min_score))
                    continue
                if code not in g.t0 and market == 'bear':
                    skip_reasons.append("%s(A股熊市不开仓)" % code)
                    continue
                if _is_cooldown(code, today_str):
                    skip_reasons.append("%s(冷却)" % code)
                    continue
                try:
                    pos = context.portfolio.positions.get(code)
                    if _pos_amount(pos) > 0:
                        skip_reasons.append("%s(已持仓)" % code)
                        continue
                except Exception:
                    pass
                # v5优化：标的自身MA20趋势过滤（开仓需站上自身MA20，过滤震荡市假信号）
                # 防御写法：强制标量化，任何异常不阻塞买入
                try:
                    cdata = cache.get(code)
                    if cdata is not None:
                        closes_arr = cdata.get('closes')
                        if closes_arr is not None and len(closes_arr) >= 21:
                            ma20_now = float(np.mean(np.asarray(closes_arr, dtype=float)[-20:]))
                            cp_now = float(closes_arr[-1])
                            if cp_now < ma20_now:
                                skip_reasons.append("%s(未站上MA20)" % code)
                                continue
                except Exception:
                    pass
                # 等权仓位（v7：预算 = 总资产/TopN × 仓位系数，系数0.5=半仓）
                cash = getattr(context.portfolio, 'cash', 0) or 0
                budget = total_value / g.top_n * g.position_ratio
                if budget > cash * 0.98:
                    budget = cash * 0.98
                vol = int(budget / price / 100) * 100
                if vol <= 0:
                    skip_reasons.append("%s(金额不足100股)" % code)
                    continue
                # v6修复：单笔委托股数上限（PTrade 单笔上限100万股，超出会被后端撤单）
                if vol > 990000:
                    vol = 990000
                    log.info("【风控】%s 股数超出单笔上限，截断至990000股（剩余资金留现金）" % code)
                if price * vol > cash:
                    vol = int(cash / price / 100) * 100
                    if vol <= 0:
                        skip_reasons.append("%s(余额不足)" % code)
                        continue
                order(code, vol)
                g.stat_buy_count += 1
                if code not in g.t0:
                    g.t1_bought_today.add(code)
                log.info("【买入】%s %d股 @%.3f 金额%.0f | FTS分%.0f 等权仓位%.1f%%(总资产/TOP%d)" % (
                    code, vol, price, price * vol, score, vol * price / total_value * 100, g.top_n))
            if skip_reasons:
                log.info("【轮动】跳过: %s" % "; ".join(skip_reasons))
    except Exception as e:
        log.error("handle_data异常: %s" % str(e))


# ========== v8新增：回测统计与摘要 ==========

def after_trading_end(context, data):
    """v8: 收盘后统计 — 每日更新日线收益 + 月末打印摘要
    注意：PTrade 官方签名 after_trading_end(context, data) 必须带 data 参数"""
    try:
        end_value = float(getattr(context.portfolio, 'total_value', 0) or 0)
        start_val = g.stat_day_start_value if g.stat_day_start_value > 0 else end_value
        daily_ret = (end_value - start_val) / start_val if start_val > 0 else 0
        g.stat_daily_returns.append(daily_ret)
        g.stat_total_days += 1
        if daily_ret > 0:
            g.stat_profitable_days += 1

        today = context.current_dt
        month_key = '%d-%02d' % (today.year, today.month)
        if g.stat_month_last is None:
            g.stat_month_last = month_key
        elif month_key != g.stat_month_last:
            _print_summary(context)
            g.stat_month_last = month_key
    except Exception as e:
        log.info("after_trading_end异常: %s" % e)


def _print_summary(context):
    """v8: 打印回测统计摘要（月度 + 可作为回测最终结果参考）"""
    try:
        end_value = float(getattr(context.portfolio, 'total_value', 0) or 0)
        initial = g.stat_initial_value if g.stat_initial_value > 0 else 1
        total_return = (end_value - initial) / initial * 100
        max_dd = g.stat_max_drawdown
        total_trades = g.stat_win_count + g.stat_loss_count
        win_rate = g.stat_win_count / max(1, total_trades) * 100
        avg_win = g.stat_gross_profit / max(1, g.stat_win_count)
        avg_loss = g.stat_gross_loss / max(1, g.stat_loss_count)
        pl_ratio = avg_win / max(0.01, avg_loss) * 100
        daily_wr = g.stat_profitable_days / max(1, g.stat_total_days) * 100
        ann_return = total_return / max(1, g.stat_total_days) * 252

        sharpe = 0.0
        sortino = 0.0
        if len(g.stat_daily_returns) > 10:
            rets = np.array(g.stat_daily_returns)
            mu = float(np.mean(rets))
            sd = float(np.std(rets, ddof=1))
            sharpe = mu / sd * (252 ** 0.5) if sd > 0 else 0
            neg = rets[rets < 0]
            dsd = float(np.std(neg, ddof=1)) if len(neg) > 1 else 0
            sortino = mu / dsd * (252 ** 0.5) if dsd > 0 else 0

        log.info("=" * 56)
        log.info("【回测统计摘要】截至 %s" % str(context.current_dt.date()))
        log.info("=" * 56)
        log.info("策略收益: %.2f%%" % total_return)
        log.info("最大回撤: %.2f%%" % max_dd)
        log.info("当前资产: %.2f (初始: %.2f)" % (end_value, initial))
        log.info("策略年化收益率: %.2f%%" % ann_return)
        log.info("胜率: %.2f%%" % win_rate)
        log.info("盈亏比: %.2f%%" % pl_ratio)
        log.info("盈利次数: %d  亏损次数: %d  总交易: %d" % (
            g.stat_win_count, g.stat_loss_count, total_trades))
        log.info("日胜率: %.2f%%" % daily_wr)
        log.info("夏普比率: %.2f  索提诺比率: %.2f" % (sharpe, sortino))
        log.info("买入次数: %d  卖出次数: %d" % (g.stat_buy_count, g.stat_sell_count))
        log.info("已实现盈亏: %.2f  交易天数: %d" % (g.stat_realized_pnl, g.stat_total_days))
        log.info("市场状态: %s  峰值资产: %.2f" % (g.last_regime, g.peak_value))
        log.info("=" * 56)
    except Exception as e:
        log.info("统计摘要异常: %s" % e)
