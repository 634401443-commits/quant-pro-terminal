import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Activity, ArrowUpDown, Layers,
  AlertTriangle, Zap, Link2, Brain, Target, Award, Gauge,
  Clock, BarChart3, PieChart, ChevronRight
} from 'lucide-react';
import { useRealTimeMarket } from '@/hooks/useRealTimeMarket';
import { useRealStockData } from '@/hooks/useRealStockData';
import { useRealTimeETF } from '@/hooks/useRealTimeETF';
import MarketIndexCard from '@/components/MarketIndexCard';
import { RISE_COLOR, FALL_COLOR, CHART_COLORS } from '@/lib/chart-colors';

const FACTOR_NAMES = ['价值', '成长', '质量', '动量', '波动率', '规模'];

const STRATEGY_MAP: Record<string, Record<string, string>> = {
  '趋势市': { '动量': '右侧交易，追强不追弱', '价值': '趋势中配置低估值补涨标的', '成长': '趋势中配置成长龙头', 'default': '右侧交易，追强不追弱' },
  '震荡市': { '价值': '均衡配置，侧重低估值蓝筹', '成长': '精选高成长个股，轻指数重结构', 'default': '均衡配置，侧重低估值蓝筹' },
  '高波动': { 'default': '降低仓位，严控止损，观望为主' },
};
const POSITION_MAP: Record<string, string> = { '趋势市': '6-7成', '震荡市': '4-5成', '高波动': '3成以下' };

interface CausalChain {
  event: string;
  fundFlow: string;
  marketPerf: string;
  decision: string;
  confidence: number;
  relatedStock: string;
  stockCode: string;
}

interface EvolutionLog {
  date: string;
  stockName: string;
  stockCode: string;
  fulfillmentRate: number;
  factorName: string;
  weightChange: number;
  weightOld: number;
  weightNew: number;
  systemAdvice: string;
}

interface IndustryDetail {
  name: string;
  change: number;
  count: number;
  upCount: number;
  downCount: number;
  leadingStock: string;
  leadingChange: number;
  weakestStock: string;
  weakestChange: number;
}

function determineMarketEnv(indices: any[], sentiment: any) {
  const shIndex = indices.find((i: any) => i.code === '000001') || indices[0];
  const kline: number[] = shIndex?.kline || [];
  let trendScore = 50;
  if (kline.length >= 20) {
    const ma20 = kline.slice(-20).reduce((a: number, b: number) => a + b, 0) / 20;
    const ma5 = kline.slice(-5).reduce((a: number, b: number) => a + b, 0) / 5;
    const slope = ma20 > 0 ? (ma5 - ma20) / ma20 * 100 : 0;
    trendScore = Math.min(100, Math.max(0, 50 + slope * 10));
  }
  let volScore = 50;
  if (kline.length >= 20) {
    const rets: number[] = [];
    for (let i = 1; i < kline.length; i++) {
      if (kline[i - 1] > 0) rets.push((kline[i] - kline[i - 1]) / kline[i - 1]);
    }
    const r20 = rets.slice(-20);
    const mean = r20.reduce((a, b) => a + b, 0) / Math.max(r20.length, 1);
    const variance = r20.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(r20.length, 1);
    volScore = Math.min(100, Math.max(0, Math.sqrt(variance) * 100 * 20));
  }
  let env = '震荡市';
  if (volScore > 80) env = '高波动';
  else if (trendScore > 60) env = '趋势市';
  return { env, trendScore: Math.round(trendScore), volScore: Math.round(volScore) };
}

function calcFactorScores(stocks: any[]) {
  if (!stocks || stocks.length === 0) return [50, 50, 50, 50, 50, 50];
  const s = stocks.slice(0, 100);
  const safeAvg = (arr: number[]) => {
    const v = arr.filter(x => isFinite(x) && x > 0);
    return v.length > 0 ? v.reduce((a, b) => a + b, 0) / v.length : 50;
  };
  const peVals = s.map((st: any) => st.factors?.pe || 0).filter((v: number) => v > 0 && v < 200);
  const valueScore = peVals.length > 0 ? Math.min(100, Math.max(20, 100 - safeAvg(peVals) / 2)) : 50;
  const growthScore = Math.min(100, Math.max(20, safeAvg(s.map((st: any) => st.factors?.profitGrowth || 0))));
  const qualityScore = Math.min(100, Math.max(20, safeAvg(s.map((st: any) => st.factors?.roe || 0)) * 2));
  const momScore = Math.min(100, Math.max(20, 50 + safeAvg(s.map((st: any) => st.factors?.change1m || 0))));
  const volScore = Math.min(100, Math.max(20, 100 - safeAvg(s.map((st: any) => st.factors?.vol20 || 0)) * 10));
  return [Math.round(valueScore), Math.round(growthScore), Math.round(qualityScore), Math.round(momScore), Math.round(volScore), 60];
}

function getStrategyAdvice(env: string, dominantFactor: string): string {
  const map = STRATEGY_MAP[env] || STRATEGY_MAP['震荡市'];
  return map[dominantFactor] || map['default'] || '均衡配置';
}

function buildCausalChain(stocks: any[]): CausalChain | null {
  if (!stocks || stocks.length === 0) return null;
  const anomalies = stocks.filter(s => Math.abs(s.change || 0) >= 3);
  if (anomalies.length === 0) return null;
  anomalies.sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0));
  const target = anomalies[0];
  const isUp = (target.change || 0) > 0;
  const changePct = (target.change || 0).toFixed(2);
  const event = isUp
    ? `${target.industry || '相关'}板块今日领涨，${target.name}涨幅显著`
    : `${target.industry || '相关'}板块今日走弱，${target.name}跌幅显著`;
  const fundFlow = isUp ? '成交活跃，主力资金偏多' : '成交萎缩，资金偏空';
  const marketPerf = `${target.name} ${isUp ? '+' : ''}${changePct}%`;
  const confidence = 67;
  let decision = '可纳入观察名单，等待确认信号';
  if (confidence >= 80) decision = '可关注介入机会';
  return {
    event,
    fundFlow,
    marketPerf,
    decision,
    confidence,
    relatedStock: target.name,
    stockCode: target.code,
  };
}

function getEvolutionLogs(): EvolutionLog[] {
  try {
    const raw = localStorage.getItem('simulation_account');
    if (!raw) return [];
    const account = JSON.parse(raw);
    const trades = account.tradeRecords || [];
    if (trades.length === 0) return [];
    return trades.slice(-3).reverse().map((t: any) => {
      const profit = t.profit || 0;
      const fulfillmentRate = profit > 0 ? 100 : profit < 0 ? 33 : 50;
      const factorName = '动量因子';
      const weightChange = fulfillmentRate >= 80 ? 2 : fulfillmentRate < 40 ? -1 : 0;
      return {
        date: (t.date || '').slice(5),
        stockName: t.name || '',
        stockCode: t.code || '',
        fulfillmentRate,
        factorName,
        weightChange,
        weightOld: 25,
        weightNew: 25 + weightChange,
        systemAdvice: fulfillmentRate < 50 ? `审视"${factorName}"类因果链的初始置信度` : '',
      };
    });
  } catch {
    return [];
  }
}

function buildIndustryDetails(stocks: any[]): IndustryDetail[] {
  const industryMap = new Map<string, any[]>();
  for (const st of stocks) {
    const ind = st.industry || '其他';
    if (!industryMap.has(ind)) industryMap.set(ind, []);
    industryMap.get(ind)!.push(st);
  }
  const details: IndustryDetail[] = [];
  for (const [name, list] of industryMap) {
    const changes = list.map(s => s.change || 0);
    const avg = changes.reduce((a, b) => a + b, 0) / Math.max(changes.length, 1);
    const up = changes.filter(c => c > 0).length;
    const down = changes.filter(c => c < 0).length;
    const sorted = [...list].sort((a, b) => (b.change || 0) - (a.change || 0));
    const leader = sorted[0];
    const weakest = sorted[sorted.length - 1];
    details.push({
      name,
      change: Number(avg.toFixed(2)),
      count: list.length,
      upCount: up,
      downCount: down,
      leadingStock: leader?.name || '—',
      leadingChange: leader?.change || 0,
      weakestStock: weakest?.name || '—',
      weakestChange: weakest?.change || 0,
    });
  }
  return details.sort((a, b) => b.change - a.change);
}

export default function DashboardPage() {
  const { indices, sentiment: s, lastUpdate, isRealTime } = useRealTimeMarket();
  const { stocks: realStocks } = useRealStockData();
  const { etfs } = useRealTimeETF();

  const marketEnv = useMemo(() => determineMarketEnv(indices, s), [indices, s]);
  const factorScores = useMemo(() => calcFactorScores(realStocks), [realStocks]);

  const dominantFactorIdx = useMemo(() => {
    let maxIdx = 0;
    for (let i = 1; i < factorScores.length; i++) {
      if (factorScores[i] > factorScores[maxIdx]) maxIdx = i;
    }
    return maxIdx;
  }, [factorScores]);

  const weakFactorIdx = useMemo(() => {
    let minIdx = 0;
    for (let i = 1; i < factorScores.length; i++) {
      if (factorScores[i] < factorScores[minIdx]) minIdx = i;
    }
    return minIdx;
  }, [factorScores]);

  const dominantFactor = FACTOR_NAMES[dominantFactorIdx] || '价值';
  const weakFactor = FACTOR_NAMES[weakFactorIdx] || '质量';
  const weakFactorScore = factorScores[weakFactorIdx] || 0;
  const strategyAdvice = getStrategyAdvice(marketEnv.env, dominantFactor);
  const positionAdvice = POSITION_MAP[marketEnv.env] || '4-5成';

  const factorStrategy = useMemo(() => {
    const sorted = [...realStocks].sort((a, b) => (b.compositeScore || b.score || 0) - (a.compositeScore || a.score || 0));
    const top5 = sorted.slice(0, 5);
    const avgChange = top5.length > 0
      ? top5.reduce((sum, st) => sum + (st.change || 0), 0) / top5.length
      : 0;
    const top3Names = top5.slice(0, 3).map(st => st.name).join(' · ');
    return { avgChange, top3Names, top5 };
  }, [realStocks]);

  const etfStrategy = useMemo(() => {
    const holding = etfs.filter(e => e.signal === 'buy' || e.signal === 'hold').slice(0, 5);
    const list = holding.length > 0 ? holding : etfs.slice(0, 5);
    const avgChange = list.length > 0
      ? list.reduce((sum, e) => sum + (e.change || 0), 0) / list.length
      : 0;
    const top3Names = list.slice(0, 3).map(e => e.name).join(' · ');
    const bestEtf = list.length > 0
      ? [...list].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0))[0]
      : null;
    const attribution = bestEtf
      ? `${bestEtf.name}（${(bestEtf.change || 0) >= 0 ? '+' : ''}${(bestEtf.change || 0).toFixed(2)}%）贡献最大`
      : '暂无数据';
    return { avgChange, top3Names, attribution };
  }, [etfs]);

  const factorAttribution = useMemo(() => {
    const maxIdx = factorScores.indexOf(Math.max(...factorScores));
    return `${FACTOR_NAMES[maxIdx]}因子今日贡献最大`;
  }, [factorScores]);

  const factorRecommendation = useMemo(() => {
    const envFactorMap: Record<string, number> = {
      '趋势市': 3,
      '震荡市': 0,
      '高波动': 4,
    };
    const recIdx = envFactorMap[marketEnv.env] ?? dominantFactorIdx;
    const recName = FACTOR_NAMES[recIdx] || '价值';
    const recScore = factorScores[recIdx] || 50;

    const sortFn = (a: any, b: any): number => {
      const fa = a.factors || {};
      const fb = b.factors || {};
      switch (recIdx) {
        case 0: return (fa.pe || 999) - (fb.pe || 999);
        case 1: return (fb.profitGrowth || 0) - (fa.profitGrowth || 0);
        case 2: return (fb.roe || 0) - (fa.roe || 0);
        case 3: return (fb.change1m || 0) - (fa.change1m || 0);
        case 4: return (fa.vol20 || 999) - (fb.vol20 || 999);
        case 5: return (fb.totalMarketCap || 0) - (fa.totalMarketCap || 0);
        default: return 0;
      }
    };

    let candidates = [...realStocks].sort(sortFn);
    if (recIdx === 0) {
      candidates = candidates.filter(s => (s.factors?.pe || 0) > 0 && (s.factors?.pe || 999) < 200);
    }
    if (recIdx === 4) {
      candidates = candidates.filter(s => (s.factors?.vol20 || 0) > 0);
    }
    const top3 = candidates.slice(0, 3);

    const reasonMap: Record<string, string> = {
      '趋势市': `当前趋势市环境，动量因子历史胜率最高，得分${recScore}分`,
      '震荡市': `当前震荡市环境，价值因子防御性强，得分${recScore}分`,
      '高波动': `当前高波动环境，低波动因子回撤风险最小，得分${recScore}分`,
    };
    const reason = reasonMap[marketEnv.env] || `${recName}因子得分${recScore}分，综合表现最优`;

    let weightPct: number;
    if (recScore >= 80) weightPct = 28;
    else if (recScore >= 60) weightPct = 23;
    else if (recScore >= 40) weightPct = 18;
    else weightPct = 12;

    return { recName, recScore, recIdx, top3, reason, weightPct };
  }, [marketEnv, factorScores, dominantFactorIdx, realStocks]);

  const causalChain = useMemo(() => buildCausalChain(realStocks), [realStocks]);
  const evolutionLogs = useMemo(() => getEvolutionLogs(), []);

  const factorRadarOption = useMemo<EChartsOption>(() => ({
    tooltip: { trigger: 'item' },
    radar: {
      indicator: FACTOR_NAMES.map(name => ({ name, max: 100 })),
      radius: '60%',
      center: ['50%', '50%'],
      axisName: { fontSize: 10, color: 'var(--muted-foreground)' },
      splitLine: { lineStyle: { color: 'var(--border)' } },
      splitArea: { show: false },
    },
    series: [{
      type: 'radar',
      data: [{
        value: factorScores,
        name: '因子得分',
        areaStyle: { color: `${CHART_COLORS[0]}40` },
        lineStyle: { color: CHART_COLORS[0], width: 2 },
        itemStyle: { color: CHART_COLORS[0] },
      }],
    }],
  }), [factorScores]);

  // ---- 行业详情数据 ----
  const industryDetails = useMemo(() => buildIndustryDetails(realStocks), [realStocks]);

  const industrySummary = useMemo(() => {
    if (industryDetails.length === 0) return { upInd: 0, downInd: 0, strongest: null, weakest: null, total: 0 };
    const upInd = industryDetails.filter(d => d.change > 0).length;
    const downInd = industryDetails.filter(d => d.change < 0).length;
    return {
      upInd,
      downInd,
      strongest: industryDetails[0],
      weakest: industryDetails[industryDetails.length - 1],
      total: industryDetails.length,
    };
  }, [industryDetails]);

  // ---- 行业涨跌幅图（15个行业，丰富tooltip）----
  const industryBarOption = useMemo<EChartsOption>(() => {
    const topN = industryDetails.slice(0, 15);
    return {
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const p = Array.isArray(params) ? params[0] : params;
          const idx = topN.length - 1 - p.dataIndex;
          const d = topN[idx];
          if (!d) return '';
          const sign = d.change >= 0 ? '+' : '';
          return `<b>${d.name}</b><br/>` +
            `平均涨跌: ${sign}${d.change}%<br/>` +
            `成分股: ${d.count}只（涨${d.upCount}/跌${d.downCount}）<br/>` +
            `领涨: ${d.leadingStock}（${d.leadingChange >= 0 ? '+' : ''}${d.leadingChange.toFixed(2)}%）<br/>` +
            `领跌: ${d.weakestStock}（${d.weakestChange >= 0 ? '+' : ''}${d.weakestChange.toFixed(2)}%）`;
        },
      },
      grid: { left: '3%', right: '8%', bottom: '3%', top: '3%', containLabel: true },
      xAxis: { type: 'value', axisLabel: { fontSize: 10, formatter: '{value}%' } },
      yAxis: {
        type: 'category',
        data: topN.map(d => d.name).reverse(),
        axisLabel: { fontSize: 10 },
      },
      series: [{
        type: 'bar',
        data: topN.map(d => d.change).reverse().map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? RISE_COLOR : FALL_COLOR,
            borderRadius: v >= 0 ? [0, 3, 3, 0] : [3, 0, 0, 3],
          },
        })),
        barWidth: '60%',
        label: {
          show: true,
          position: 'right',
          fontSize: 10,
          formatter: (p: any) => `${p.value > 0 ? '+' : ''}${p.value}%`,
        },
      }],
    };
  }, [industryDetails]);

  const trendLabel = marketEnv.trendScore > 60 ? '强' : marketEnv.trendScore > 30 ? '中性' : '弱';
  const volLabel = marketEnv.volScore > 80 ? '高' : marketEnv.volScore > 50 ? '正常' : '低';
  const envIcon = marketEnv.env === '趋势市' ? '📈' : marketEnv.env === '高波动' ? '⚠️' : '📊';
  const factorWin = factorStrategy.avgChange >= etfStrategy.avgChange;

  return (
    <div className="space-y-4">
      {/* ===== 模块A：市场状态横幅 ===== */}
      <div className="rounded-lg border border-primary/30 bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-foreground">{envIcon} {marketEnv.env}</span>
            </div>
            <div className="text-xs text-muted-foreground">
              占优因子：<span className="font-bold text-primary">{dominantFactor}</span>
              <span className="ml-1">（{factorScores[dominantFactorIdx]}分 vs {FACTOR_NAMES[dominantFactorIdx === 0 ? 1 : 0]} {factorScores[dominantFactorIdx === 0 ? 1 : 0]}分）</span>
            </div>
            <div className="text-xs text-muted-foreground">
              建议：<span className="font-bold text-foreground">{strategyAdvice}</span>
            </div>
            <div className="text-xs text-muted-foreground">
              仓位：<span className="font-bold text-foreground">{positionAdvice}</span>
            </div>
          </div>
          {weakFactorScore < 30 && (
            <div className="flex items-center gap-1 text-xs text-destructive">
              <AlertTriangle className="size-3.5" />
              {weakFactor}因子持续走弱（{weakFactorScore}分）
            </div>
          )}
        </div>
      </div>

      {/* ===== 模块B & C：策略信号PK + 核心因果链 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 模块B：策略信号PK */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <BarChart3 className="size-3.5 text-primary" />
            策略信号PK
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground font-medium">因子策略</div>
              <div className="text-lg font-bold" style={{ color: factorStrategy.avgChange >= 0 ? RISE_COLOR : FALL_COLOR }}>
                {factorStrategy.avgChange >= 0 ? '+' : ''}{factorStrategy.avgChange.toFixed(2)}%
                {!factorWin && <span className="ml-1 text-success">✅</span>}
              </div>
              <div className="text-[10px] text-muted-foreground">持仓Top3</div>
              <div className="text-[10px] text-foreground leading-relaxed">{factorStrategy.top3Names || '暂无'}</div>
              <div className="text-[10px] text-muted-foreground pt-1 border-t border-border/20">
                {factorAttribution}
              </div>
            </div>
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground font-medium">ETF轮动</div>
              <div className="text-lg font-bold" style={{ color: etfStrategy.avgChange >= 0 ? RISE_COLOR : FALL_COLOR }}>
                {etfStrategy.avgChange >= 0 ? '+' : ''}{etfStrategy.avgChange.toFixed(2)}%
                {factorWin && <span className="ml-1 text-success">✅</span>}
              </div>
              <div className="text-[10px] text-muted-foreground">持仓Top3</div>
              <div className="text-[10px] text-foreground leading-relaxed">{etfStrategy.top3Names || '暂无'}</div>
              <div className="text-[10px] text-muted-foreground pt-1 border-t border-border/20">
                {etfStrategy.attribution}
              </div>
            </div>
          </div>
        </div>

        {/* 模块C：核心因果链 */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <Link2 className="size-3.5 text-primary" />
            核心因果链
          </h3>
          {causalChain ? (
            <div className="space-y-2">
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">触发事件</span>
                <span className="text-xs text-foreground">{causalChain.event}</span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground/50">
                <div className="h-px flex-1 bg-border/30" />
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">资金确认</span>
                <span className="text-xs text-foreground">{causalChain.fundFlow}</span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground/50">
                <div className="h-px flex-1 bg-border/30" />
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">市场表现</span>
                <span className="text-xs text-foreground">{causalChain.marketPerf}</span>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground/50">
                <div className="h-px flex-1 bg-border/30" />
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">决策建议</span>
                <span className="text-xs font-medium text-primary">{causalChain.decision}</span>
              </div>
              <div className="pt-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">置信度</span>
                  <span className="text-[10px] font-bold text-foreground">{causalChain.confidence}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${causalChain.confidence}%`,
                      backgroundColor: causalChain.confidence >= 80 ? RISE_COLOR : causalChain.confidence >= 60 ? '#f59e0b' : FALL_COLOR,
                    }}
                  />
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground pt-1">
                关联标的：<span className="text-foreground">{causalChain.relatedStock}（{causalChain.stockCode}）</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
              今日无显著因果链，市场处于随机波动状态
            </div>
          )}
        </div>
      </div>

      {/* ===== 今日因子推荐条带 ===== */}
      <div className="rounded-lg border border-primary/20 bg-gradient-to-r from-primary/8 via-primary/3 to-transparent p-3">
        <div className="flex items-center gap-2 mb-2">
          <Target className="size-4 text-primary" />
          <h3 className="text-xs font-semibold text-foreground">今日因子推荐</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div className="flex flex-col justify-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">推荐因子</div>
            <div className="text-lg font-bold text-primary">{factorRecommendation.recName}</div>
            <div className="text-[10px] text-muted-foreground">得分 {factorRecommendation.recScore} / 100</div>
          </div>
          <div className="flex flex-col justify-center md:col-span-2">
            <div className="text-[10px] text-muted-foreground mb-0.5">推荐理由</div>
            <div className="text-xs text-foreground leading-relaxed">{factorRecommendation.reason}</div>
          </div>
          <div className="flex flex-col justify-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">权重建议</div>
            <div className="text-lg font-bold text-foreground">{factorRecommendation.weightPct}%</div>
            <div className="h-1.5 rounded-full bg-muted/50 overflow-hidden mt-1">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${factorRecommendation.weightPct * 2}%` }}
              />
            </div>
          </div>
        </div>
        <div className="mt-2 pt-2 border-t border-border/20">
          <div className="text-[10px] text-muted-foreground mb-1.5">推荐因子Top3标的</div>
          {factorRecommendation.top3.length > 0 ? (
            <div className="grid grid-cols-3 gap-2">
              {factorRecommendation.top3.map((stock, i) => {
                const change = stock.change || 0;
                const price = stock.price || 0;
                const factorVal = (() => {
                  const f = stock.factors || {};
                  switch (factorRecommendation.recIdx) {
                    case 0: return f.pe ? `PE ${f.pe.toFixed(1)}` : '—';
                    case 1: return f.profitGrowth != null ? `增长 ${f.profitGrowth.toFixed(1)}%` : '—';
                    case 2: return f.roe != null ? `ROE ${f.roe.toFixed(1)}%` : '—';
                    case 3: return f.change1m != null ? `1月涨幅 ${f.change1m.toFixed(1)}%` : '—';
                    case 4: return f.vol20 != null ? `波动率 ${f.vol20.toFixed(1)}%` : '—';
                    default: return '—';
                  }
                })();
                return (
                  <div key={stock.code || i} className="p-2 rounded-md bg-muted/20">
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-xs font-medium text-foreground">{stock.name}</span>
                      <span className="text-[10px] text-muted-foreground">#{i + 1}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">{stock.code} · {price.toFixed(2)}</span>
                      <span className="text-[10px] font-bold" style={{ color: change >= 0 ? RISE_COLOR : FALL_COLOR }}>
                        {change >= 0 ? '+' : ''}{change.toFixed(2)}%
                      </span>
                    </div>
                    <div className="text-[10px] text-primary mt-0.5">{factorVal}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-[10px] text-muted-foreground text-center py-2">暂无符合条件的标的</div>
          )}
        </div>
      </div>

      {/* ===== 模块D & E：市场状态定性 + 关键数据速览 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 模块D：市场状态定性 */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <Brain className="size-3.5 text-primary" />
            市场状态定性
          </h3>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">环境判定</span>
              <span className="text-sm font-bold text-foreground">{envIcon} {marketEnv.env}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">趋势强度</span>
              <span className="text-xs text-foreground">{trendLabel}（{marketEnv.trendScore}/100）</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">波动率状态</span>
              <span className="text-xs text-foreground">{volLabel}（{marketEnv.volScore}/100）</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">占优因子</span>
              <span className="text-xs font-bold text-primary">{dominantFactor}（得分{factorScores[dominantFactorIdx]}）</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[10px] text-muted-foreground">弱势因子</span>
              <span className="text-xs font-bold" style={{ color: weakFactorScore < 30 ? '#ef4444' : 'var(--muted-foreground)' }}>
                {weakFactor}（得分{weakFactorScore}）{weakFactorScore < 30 && ' ⚠️'}
              </span>
            </div>
            <div className="pt-2 border-t border-border/20">
              <div className="text-[10px] text-muted-foreground mb-1">综合策略建议</div>
              <div className="text-xs font-bold text-foreground">{strategyAdvice}</div>
            </div>
          </div>
          <div className="mt-2 pt-2 border-t border-border/20">
            <ReactECharts option={factorRadarOption} theme="ud" style={{ height: '180px' }} />
          </div>
        </div>

        {/* 模块E：关键数据速览 */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <Gauge className="size-3.5 text-primary" />
            关键数据速览
          </h3>
          <div className="grid grid-cols-2 gap-2">
            {indices.slice(0, 4).map(idx => (
              <MarketIndexCard key={idx.code} index={idx} />
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2 mt-2">
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">两市成交</div>
              <div className="text-sm font-bold text-foreground">{(s.totalAmount || 0).toLocaleString()}亿</div>
            </div>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">北向资金</div>
              <div className="text-sm font-bold" style={{ color: (s.northFlow || 0) >= 0 ? RISE_COLOR : FALL_COLOR }}>
                {(s.northFlow || 0) >= 0 ? '+' : ''}{s.northFlow || 0}亿
              </div>
            </div>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">涨跌比</div>
              <div className="text-sm font-bold">
                <span style={{ color: RISE_COLOR }}>{s.upCount || 0}</span>
                <span className="text-muted-foreground">/</span>
                <span style={{ color: FALL_COLOR }}>{s.downCount || 0}</span>
              </div>
            </div>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">涨停/跌停</div>
              <div className="text-sm font-bold">
                <span style={{ color: RISE_COLOR }}>{s.limitUp || 0}</span>
                <span className="text-muted-foreground">/</span>
                <span style={{ color: FALL_COLOR }}>{s.limitDown || 0}</span>
              </div>
            </div>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">赚钱效应</div>
              <div className="text-sm font-bold text-primary">{s.profitEffect || '—'}</div>
            </div>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">更新时间</div>
              <div className="text-sm font-bold text-foreground flex items-center justify-center gap-1">
                <Clock className="size-3" />
                <span className="text-[10px]">{lastUpdate || '—'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ===== 行业涨跌幅详情（全宽） ===== */}
      <div className="rounded-lg border border-border/40 bg-card/40 p-3">
        <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
          <ArrowUpDown className="size-3.5 text-primary" />
          行业涨跌幅详情
        </h3>
        {/* 汇总条 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-3">
          <div className="p-2 rounded-md bg-muted/30 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">上涨行业</div>
            <div className="text-sm font-bold" style={{ color: RISE_COLOR }}>{industrySummary.upInd}</div>
          </div>
          <div className="p-2 rounded-md bg-muted/30 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">下跌行业</div>
            <div className="text-sm font-bold" style={{ color: FALL_COLOR }}>{industrySummary.downInd}</div>
          </div>
          <div className="p-2 rounded-md bg-muted/30 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">最强行业</div>
            <div className="text-sm font-bold text-foreground">
              {industrySummary.strongest?.name || '—'}
              <span className="ml-1 text-xs" style={{ color: RISE_COLOR }}>
                {industrySummary.strongest ? `+${industrySummary.strongest.change}%` : ''}
              </span>
            </div>
          </div>
          <div className="p-2 rounded-md bg-muted/30 text-center">
            <div className="text-[10px] text-muted-foreground mb-0.5">最弱行业</div>
            <div className="text-sm font-bold text-foreground">
              {industrySummary.weakest?.name || '—'}
              <span className="ml-1 text-xs" style={{ color: FALL_COLOR }}>
                {industrySummary.weakest ? `${industrySummary.weakest.change}%` : ''}
              </span>
            </div>
          </div>
        </div>
        {/* 条形图 */}
        <ReactECharts option={industryBarOption} theme="ud" style={{ height: '380px' }} />
        {/* 详情表格 */}
        <div className="mt-3 pt-2 border-t border-border/20">
          <div className="text-[10px] text-muted-foreground mb-2">涨幅前5 / 跌幅前5 行业详情</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {/* 涨幅前5 */}
            <div>
              <div className="text-[10px] font-medium mb-1" style={{ color: RISE_COLOR }}>涨幅前5</div>
              <div className="space-y-1">
                {industryDetails.slice(0, 5).map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2 p-1.5 rounded bg-muted/15 text-[10px]">
                    <span className="text-muted-foreground w-4 text-center">{i + 1}</span>
                    <span className="font-medium text-foreground w-16 truncate">{d.name}</span>
                    <span className="font-bold w-12" style={{ color: RISE_COLOR }}>+{d.change}%</span>
                    <span className="text-muted-foreground">{d.count}只</span>
                    <span className="text-muted-foreground">涨{d.upCount}/跌{d.downCount}</span>
                    <span className="text-foreground ml-auto truncate">领涨: {d.leadingStock}</span>
                  </div>
                ))}
                {industryDetails.length === 0 && (
                  <div className="text-[10px] text-muted-foreground text-center py-2">暂无数据</div>
                )}
              </div>
            </div>
            {/* 跌幅前5 */}
            <div>
              <div className="text-[10px] font-medium mb-1" style={{ color: FALL_COLOR }}>跌幅前5</div>
              <div className="space-y-1">
                {[...industryDetails].reverse().slice(0, 5).map((d, i) => (
                  <div key={d.name} className="flex items-center gap-2 p-1.5 rounded bg-muted/15 text-[10px]">
                    <span className="text-muted-foreground w-4 text-center">{i + 1}</span>
                    <span className="font-medium text-foreground w-16 truncate">{d.name}</span>
                    <span className="font-bold w-12" style={{ color: FALL_COLOR }}>{d.change}%</span>
                    <span className="text-muted-foreground">{d.count}只</span>
                    <span className="text-muted-foreground">涨{d.upCount}/跌{d.downCount}</span>
                    <span className="text-foreground ml-auto truncate">领跌: {d.weakestStock}</span>
                  </div>
                ))}
                {industryDetails.length === 0 && (
                  <div className="text-[10px] text-muted-foreground text-center py-2">暂无数据</div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ===== 模块F：进化日志 ===== */}
      <div className="rounded-lg border border-border/40 bg-card/40 p-3">
        <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
          <Zap className="size-3.5 text-primary" />
          进化日志 · 今日已自动调整
        </h3>
        {evolutionLogs.length > 0 ? (
          <div className="space-y-2">
            {evolutionLogs.map((log, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-md bg-muted/20 text-xs">
                <span className="text-muted-foreground whitespace-nowrap font-mono">{log.date}</span>
                <span className="text-foreground font-medium whitespace-nowrap">
                  {log.stockName}（{log.stockCode}）
                </span>
                <span className="text-muted-foreground">逻辑兑现率</span>
                <span className="font-bold" style={{ color: log.fulfillmentRate >= 80 ? RISE_COLOR : log.fulfillmentRate < 40 ? FALL_COLOR : '#f59e0b' }}>
                  {log.fulfillmentRate}%
                </span>
                <span className="text-muted-foreground">→</span>
                <span className="text-foreground">
                  {log.factorName}权重
                  <span style={{ color: log.weightChange > 0 ? RISE_COLOR : log.weightChange < 0 ? FALL_COLOR : 'var(--muted-foreground)' }}>
                    {' '}{log.weightChange > 0 ? '+' : ''}{log.weightChange}%（{log.weightOld}%→{log.weightNew}%）
                  </span>
                </span>
                {log.systemAdvice && (
                  <span className="text-destructive flex items-center gap-0.5 ml-auto">
                    <AlertTriangle className="size-3" />
                    {log.systemAdvice}
                  </span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-muted-foreground text-center py-4">
            暂无交易记录，开始第一笔交易后系统将自动学习
          </div>
        )}
      </div>
    </div>
  );
}
