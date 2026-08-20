# QUANT PRO - ETF轮动量化策略终端

基于 FastAPI + React + PTrade 的跨市场ETF轮动量化交易系统，覆盖从因子选股、回测验证到实盘信号传输的完整链路。

## 核心功能

### 后端服务 (app.py)
- **FastAPI 全栈架构**：单进程 FastAPI + React 前端 + SQLite 持久化
- **多因子选股模型**：价值、成长、质量、动量、波动率、技术六大因子混合打分
- **实时行情接入**：腾讯API为主，新浪API为备，东财API补充基本面数据
- **ETF轮动排名**：跨市场ETF池（A股 + 跨境 + 商品）实时轮动监控
- **K线数据管理**：自动拉取并缓存OHLC日K线，支持静态导出

### PTrade策略 (ptrade_fts_top3_hybrid.py)
- **FTS混合因子**：固定50/50混合权重，避免自动进化过拟合
- **波动率自适应止盈**：低波动(黄金/红利)3-4%，中波动(纳指/标普)5-7%，高波动(日经/创业板)8-10%
- **MA20趋势过滤**：开仓标的必须站上自身MA20，规避震荡市假信号
- **半仓风控**：实盘使用 position_ratio=0.5 控制风险
- **持仓闭环**：通过 POST /api/positions/report 回传持仓快照

### 信号桥接 (ptrade_bridge.py)
- `GET /api/signal/latest` — PTrade每日开盘前自动拉取最新信号
- `GET /api/positions/latest` — 获取最新持仓快照
- `POST /api/positions/report` — PTrade回传实盘持仓

### 回测与压力测试
- `stress_test.py` — 极端行情压力测试，半仓最大回撤6.4%
- 前端内置回测页面，支持自定义参数调优

## 项目结构

```
├── app.py                        # FastAPI 后端主程序
├── ptrade_fts_top3_hybrid.py     # PTrade 实盘策略（主力）
├── ptrade_fts_top3.py            # PTrade 策略（基础版）
├── ptrade_fts_top3_cross.py      # PTrade 策略（跨市场版）
├── ptrade_bridge.py              # 信号传输桥接服务
├── ptrade_rotation_self.py       # 轮动策略自运行模块
├── custom_pool.py                # 自选股池管理
├── factor_config.json            # 因子权重配置（后端与PTrade共用）
├── stress_test.py                # 压力测试脚本
├── fix_etf_kline.py              # ETF K线数据修复工具
├── restore_kline.py              # K线数据恢复工具
├── fix_kline_format.py           # K线格式修复工具
├── dashboard_v5.tsx              # 前端仪表盘主组件
├── DashboardPage_fixed.tsx       # 仪表盘页面（修复版）
├── causal-engine.ts              # 因果分析引擎
├── CausalChainPanel.tsx          # 因果链面板组件
├── tdx-financial-data.json       # TDX基本面数据缓存
├── stock_codes.txt               # 股票代码池
└── 跨市场ETF_Top3轮动_回测报告.html  # 回测报告
```

## 快速开始

### 1. 启动后端

```bash
pip install fastapi uvicorn numpy
python app.py
```

访问 http://localhost:8000

### 2. 部署PTrade策略

将 `ptrade_fts_top3_hybrid.py` 和 `factor_config.json` 上传至PTrade策略平台，策略每日开盘前自动调用 `GET /api/signal/latest` 获取信号。

### 3. 因子配置

编辑 `factor_config.json` 调整因子权重，后端与PTrade策略同步读取：

```json
{
  "价值因子": 20,
  "成长因子": 18,
  "质量因子": 22,
  "动量因子": 15,
  "波动率因子": 10,
  "技术因子": 15
}
```

## 关键约束

- PTrade单笔委托上限100万股，超出需截断至99万股
- 市场趋势判断按标的类别分流：A股熊市信号仅作用于A股ETF
- 核心ETF池包含10只跨市场标的（A股3 + 跨境5 + 商品2）
- 回测成本：ETF佣金万0.5（最低1元），滑点0.2%%
- 等权仓位分配：Top3标的各占约33%仓位

## 数据源优先级

| 数据类型 | 优先级 |
|----------|--------|
| K线行情 | 腾讯API > 新浪API |
| PE/PB估值 | 东财API > 腾讯API fallback |
| ROE/毛利率 | 东财API > TDX > 技术面代理 |

## 技术栈

- **后端**：Python, FastAPI, SQLite, NumPy
- **前端**：React, TypeScript, Vite
- **实盘**：PTrade量化平台
- **数据源**：腾讯行情API, 新浪财经API, 东方财富API, TDX

## License

MIT
