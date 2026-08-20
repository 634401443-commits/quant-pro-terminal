# QUANT PRO 数据质量问题修复方案

> 版本：v1.0（方案稿，暂不实施）
> 日期：2026-08-08
> 依据：五粮液决策报告验证（TDX 交叉核对）诊断结论

---

## 一、问题根因与修复方向总览

基于验证报告诊断，三个问题根因对应三条修复链路：

| 根因 | 表现 | 修复方向 | 性质 |
|---|---|---|---|
| A. 财务数据陈旧/未接入 | ROE 35.2% 无支撑（真实 6.5%） | 智能打分链路接入 TDX 财务数据 | 数据链路打通 |
| B. K线窗口与字段不一致 | "历史最高 84.29" 错误（真实 60 日高 87.25） | 后端返回完整 OHLC + 更长窗口 | 数据契约调整 |
| C. ATR 降级近似 | ATR 0.95 vs 真实 1.76（差 84%） | ATR 改用真实 high/low 波幅 | 算法实现修正 |

三条链路互相独立，可分批实施、互不阻塞。

---

## 二、分项修复方案

### 2.1 A. ROE 财务数据陈旧

**现状**：后端 `custom_pool` 的 `compute_factors` 用代理值 `roe = clip(15 + revenueGrowth×0.3, 0, 50)`（`app.py:266`），估值类字段 pe/pb/ps 直接置 0。而前端 `useRealStockData` 已经消费 `tdx-financial-data.json`（`useRealStockData.ts:329-344`），文件中有五粮液真实 `roe: 6.5041`、`grossMargin: 81.43`。

**方案 A1（推荐）：后端读取 TDX 财务文件覆盖代理值**
- 后端 `compute_factors` 中，加载 `public/tdx-financial-data.json` 建立 `code → {roe, grossMargin, netMargin, revenueGrowth, profitGrowth}` 映射
- 代理值计算前先查映射，命中则用真实值，未命中才回退代理
- 预期效果：智能打分报告的 ROE/毛利率/净利率/增速全部来自通达信真实数据，质量因子回归真实水平
- 涉及文件：`app.py`（`compute_factors`）、`public/tdx-financial-data.json`（已有）
- 工作量：约 0.5 天（含测试）

**方案 A2：前端打分响应时合并财务数据**
- `InvestmentReport` 渲染前，用 code 查前端已加载的 tdx 财务 Map，覆盖 `result.factors.roe` 等字段
- 优点：不动后端；缺点：ROE 只影响报告展示，后端排序分（fts_composite）不受影响，两处可能不一致
- 涉及文件：`InvestmentReport.tsx`、`useRealStockData.ts`（暴露财务 Map）
- 工作量：约 0.5 天

**方案 A3（长期）：财务数据统一走后端单一接口**
- 后端新增 `/api/financial/{code}`，前端所有模块统一消费；废弃 tdx-financial-data.json 前端直读
- 预期效果：彻底消除"前端一个源、后端一个源"的双轨
- 涉及文件：`app.py`、`useRealStockData.ts`、`WatchlistPage.tsx`
- 工作量：约 1.5 天（含前后端联调）

### 2.2 B. 历史最高价窗口不一致

**现状**：后端 `get_kline` 抓取 200 根日K（含 high/low/volume），但 `custom_pool` 返回给前端的 `kline` 字段只取**最近 60 根 close**（`'kline': hist['close'][-60:].tolist()`）。前端 `calcMaxHigh` 对 60 根收盘价取 max → 五粮液得 84.29（实际是 60 根收盘价里的最高收盘，而验证基准 60 日最高价是 87.25，250 日高 131.85）。

**方案 B1（推荐）：返回字段升级为完整 OHLC，并增加 high/low 序列**
- `custom_pool` 返回结构扩展为 `{ kline: close[], high: number[], low: number[], open: number[] }`（各 60 根），或直接返回完整对象数组 `KlineItem[]`
- 前端 `ScoreResult` 接口同步扩展；`calcMaxHigh` 改用 `high` 序列取最高价
- 预期效果："历史最高"取真实最高价（60 日高 87.25），移动止盈 80.08 → 82.89，与 TDX 口径一致
- 涉及文件：`app.py`（custom_pool 响应）、`InvestmentReport.tsx`（ScoreResult/calcMaxHigh）、`EtfInvestmentReport.tsx`（如共用）
- 工作量：约 0.5-1 天

**方案 B2：窗口从 60 根扩展到 250 根**
- 仅把 `hist['close'][-60:]` 改为 `[-250:]`，不做 OHLC 拆分
- 预期效果：移动止盈基于 250 根（约一年）收盘价最高值，接近 131.85×0.95=125.26
- 注意：一年窗口的"最高价"对中短线报告可能过于宽松，需结合产品定位决策
- 涉及文件：`app.py`
- 工作量：约 15 分钟

**方案 B3：完全切换到 `kline-data.json`（本地 150 根，含 high/low）**
- 前端智能打分报告渲染前，用 `loadKlineFromJson()` 的 `000858` 数据（150 根、含 high/low）覆盖后端返回的 kline
- 预期效果：与因子选股/ETF 轮动同源，消除"前后端 K线不同源"；150 根含 2025-12 以来数据，60 日高 91.28
- 注意：数据是 08-05 快照，非实时；且 150 根仍覆盖不到 250 日
- 涉及文件：`InvestmentReport.tsx`、`WatchlistPage.tsx`
- 工作量：约 0.5 天

### 2.3 C. ATR 降级近似

**现状**：前端 `calcATR`（`InvestmentReport.tsx:131-141`）用"14 日日涨跌幅绝对值均值 × 现价"近似（代码注释"K线无高低价，使用降级近似"）。后端 K线**其实有 high/low**，只是没传给前端。

**方案 C1（推荐，配合 B1）：ATR 改用真实波幅**
- 标准 ATR 公式：`TR = max(high-low, |high-prevClose|, |low-prevClose|)`，14 日 TR 均值
- 前端 `calcATR` 接收 high/low 序列（来自 B1 扩展的响应字段），替换降级近似
- 预期效果：ATR 0.95 → ~1.76，ATR 止损 73.41 → 72.44，更贴近真实风险
- 依赖：B1 先行（需要 high/low 数据）
- 涉及文件：`InvestmentReport.tsx`（calcATR）、`EtfInvestmentReport.tsx`（同逻辑）
- 工作量：约 30 分钟（B1 完成后）

**方案 C2：降级近似保留 + 校准系数**
- 若短期不想动数据契约，对现近似值乘经验系数（约 1.8）逼近真实 ATR
- 优点：改动最小；缺点：系数是经验值，不同股票/行情下不稳
- 涉及文件：`InvestmentReport.tsx`
- 工作量：约 15 分钟

---

## 三、特别标注：立即根治 / 架构调整 / 接受现状

| 方案 | 类别 | 说明 |
|---|---|---|
| **C1（ATR 真实波幅）** | **能立刻根治** | 前提是 B1 的 high/low 字段先落地；B1+C1 合计约 1-1.5 天，修复后 ATR 与移动止盈同时回到真实口径 |
| B2（窗口扩 250） | 能立刻根治 | 单文件 15 分钟改动，但"历史最高"语义需产品确认 |
| A1（后端读 TDX 财务） | 能立刻根治 | 单文件改动，0.5 天；ROE/毛利率/净利率立即真实化 |
| A3（财务统一接口） | **需要架构调整** | 涉及前后端联调、废弃前端直读 JSON，属中长期重构 |
| B3（切 kline-data.json） | 需要架构调整 | 改变打分链路 K线来源，需评估实时性损失 |
| A2（前端合并财务） | 过渡方案 | 可快速落地但会造成"展示分与排序分口径分离" |
| C2（ATR 经验系数） | 过渡方案 | 临时缓解，不建议长期保留 |
| 买入区间 0.4% 偏差 | **可接受现状** | MA30 0.31 元偏差、买入区间轻微偏差属"够用"，不影响决策框架 |
| 近 1 月涨幅口径差异 | **可接受现状** | 交易日口径 vs 自然日口径差异，属口径选择而非错误 |

---

## 四、优先级排序

### P1（影响准确率，必须修）

| 优先级内排序 | 方案 | 理由 | 工作量 |
|---|---|---|---|
| 1 | **B1 + C1**（OHLC 字段 + ATR 真实波幅） | "历史最高价错误"是最严重问题，直接扭曲移动止盈；ATR 是止损核心参数。两者联动一次修完 | 1-1.5 天 |
| 2 | **A1**（后端接入 TDX 财务） | ROE 35.2% 无支撑会夸大质量因子评级，影响"推荐/强烈推荐"判定 | 0.5 天 |

### P2（影响体验，建议修）

| 方案 | 理由 | 工作量 |
|---|---|---|
| B2 或 B3（K线窗口/来源统一） | 消除前后端 K线不同源，移动止盈语义与产品定位对齐 | 0.5 天 |
| A2（前端财务合并，若 A1 短期无法排期） | 报告展示层先真实化 | 0.5 天 |

### P3（长期优化，可以搁置）

| 方案 | 理由 |
|---|---|
| A3（财务统一后端接口） | 架构级收敛，需前后端联调，当前双轨可运行 |
| C2（ATR 系数） | 仅作过渡，B1+C1 落地后废弃 |
| 评级阈值/评分体系统一（R3/R5） | 属数据一致性收尾，不影响单报告正确性 |

---

## 五、建议实施顺序

```
阶段一（P1，1.5-2 天）：
  B1 后端返回 OHLC + 前端 ScoreResult 扩展
  → C1 ATR 真实波幅（依赖 B1）
  → A1 后端读 TDX 财务覆盖代理值
  → 用五粮液回归验证：历史最高 87.25、ATR ~1.76、ROE 6.5%

阶段二（P2，1 天）：
  B2/B3 K线窗口与来源统一（与产品确认移动止盈语义）

阶段三（P3，长期）：
  A3 财务统一接口；评级/评分体系收敛
```

---

## 六、验收标准（以五粮液 000858.SZ 为例）

| 指标 | 修复前 | 修复后（预期） |
|---|---|---|
| 历史最高价 | 84.29（60 根收盘最高） | 87.25（60 根真实最高） |
| 移动止盈 | 80.08 | 82.89 |
| ATR(14) | 0.95（降级近似） | ~1.76（真实波幅） |
| ROE | 35.2%（代理值） | 6.50%（TDX 真实） |
| 止损 | 73.06（兜底巧合） | 72.44（真实 ATR）或维持兜底 |
| 买入区间 | 74.21-74.88 | 74.05-74.84（与 TDX 复算一致） |

---

## 附：涉及文件清单

| 文件 | 方案 | 角色 |
|---|---|---|
| `app.py` | A1 / B1 / B2 | 后端：TDX 财务覆盖、OHLC 字段、K线窗口 |
| `src/pages/WatchlistPage/components/InvestmentReport.tsx` | B1 / C1 / A2 | 前端：ScoreResult 扩展、ATR 真实波幅、财务合并 |
| `src/pages/RotationPage/components/EtfInvestmentReport.tsx` | C1 | 前端：ETF 报告 ATR 同步修复 |
| `src/pages/WatchlistPage/WatchlistPage.tsx` | B3 / A2 | 前端：K线来源切换、财务数据传入 |
| `src/hooks/useRealStockData.ts` | A2 / A3 | 前端：暴露财务 Map |
| `public/tdx-financial-data.json` | A1 | 数据：财务真实值来源（已有） |
| `public/kline-data.json` | B3 | 数据：150 根 OHLC（已有） |
