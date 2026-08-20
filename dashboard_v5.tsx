import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { useMemo } from 'react';
import {
  TrendingUp, TrendingDown, ArrowUpDown,
  AlertTriangle, Zap, Link2, Brain, Target, Gauge,
  Clock, BarChart3, Flame, ChevronRight
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

// ---- 类型 ----
interface CausalChain {
  event: string;
  fundFlow: string;
  marketPerf: string;
  decision: string;
  confidence: number;
  relatedStock: string;
  stockCode: string;
  evidenceCount: number;
  directionConsistent: boolean;
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

interface IndustryCausalCard {
  name: string;
  change: number;
  count: number;
  upCount: number;
  downCount: number;
  leadingStock: string;
  leadingChange: number;
  weakestStock: string;
  weakestChange: number;
  avgTurnover: number;
  turnoverRatio: number;
  drivingLogic: string;
  isStrong: boolean;
}

// ---- 市场环境判定 ----
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

// ---- 因子得分 ----
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

// ============ 修复3: 行业因果卡片 - 排除"其他"行业 ============
function buildIndustryCausalCards(stocks: any[]): IndustryCausalCard[] {
  if (!stocks || stocks.length === 0) return [];
  const industryMap = new Map<string, any[]>();

  // 修复3: 排除"其他"和空行业名
  for (const st of stocks) {
    const ind = st.industry;
    if (!ind || ind === '其他' || ind === '') continue;
    if (!industryMap.has(ind)) industryMap.set(ind, []);
    industryMap.get(ind)!.push(st);
  }

  const allTurnovers = stocks.map(s => s.turnover || 0).filter(v => v > 0);
  const marketAvgTurnover = allTurnovers.length > 0
    ? allTurnovers.reduce((a, b) => a + b, 0) / allTurnovers.length
    : 0;

  const cards: IndustryCausalCard[] = [];
  for (const [name, list] of industryMap) {
    const changes = list.map(s => s.change || 0);
    const avg = changes.reduce((a, b) => a + b, 0) / Math.max(changes.length, 1);
    const up = changes.filter(c => c > 0).length;
    const down = changes.filter(c => c < 0).length;
    const sorted = [...list].sort((a, b) => (b.change || 0) - (a.change || 0));
    const leader = sorted[0];
    const weakest = sorted[sorted.length - 1];
    const turnovers = list.map(s => s.turnover || 0).filter(v => v > 0);
    const avgTurnover = turnovers.length > 0
      ? turnovers.reduce((a, b) => a + b, 0) / turnovers.length
      : 0;
    const turnoverRatio = marketAvgTurnover > 0 ? avgTurnover / marketAvgTurnover : 1;

    cards.push({
      name,
      change: Number(avg.toFixed(1)),
      count: list.length,
      upCount: up,
      downCount: down,
      leadingStock: leader?.name || '—',
      leadingChange: leader?.change || 0,
      weakestStock: weakest?.name || '—',
      weakestChange: weakest?.change || 0,
      avgTurnover,
      turnoverRatio,
      drivingLogic: '',
      isStrong: avg >= 0,
    });
  }

  cards.sort((a, b) => b.change - a.change);

  for (const card of cards) {
    card.drivingLogic = generateDrivingLogic(card);
  }

  return cards;
}

// ---- 驱动逻辑生成 ----
function generateDrivingLogic(card: IndustryCausalCard): string {
  const avgChange = card.change;
  const leaderChange = card.leadingChange;
  const ratio = card.turnoverRatio;

  if (avgChange > 3) {
    if (ratio > 1.5 && leaderChange > 5) {
      return `成交放大${ratio.toFixed(1)}倍，${card.leadingStock}涨幅${leaderChange.toFixed(1)}%，资金聚焦龙头，板块强势联动`;
    }
    if (ratio > 1.5) {
      return `成交放大${ratio.toFixed(1)}倍，资金流入确认，板块强势异动`;
    }
    return `板块涨幅${avgChange.toFixed(1)}%显著异动，资金流入推动`;
  }
  if (avgChange > 2) {
    if (leaderChange > 5) {
      return `领涨股${card.leadingStock}涨幅${leaderChange.toFixed(1)}%，资金聚焦龙头，板块联动`;
    }
    return `板块涨幅${avgChange.toFixed(1)}%，资金温和流入`;
  }
  if (avgChange > 0) {
    return `资金轮动，板块温和上涨${avgChange.toFixed(1)}%，暂未发现明确驱动因素`;
  }
  if (avgChange < -2) {
    return `板块跌幅${Math.abs(avgChange).toFixed(1)}%，${card.weakestStock}领跌${Math.abs(card.weakestChange).toFixed(1)}%，资金流出`;
  }
  return `资金轮动，低位震荡，暂未发现明确驱动因素`;
}

// ============ 修复1+6: 因果链 - 从具体标的正向推导 + 联动行业卡片 ============
function buildCausalChain(stocks: any[], industryCards: IndustryCausalCard[]): CausalChain | null {
  if (!stocks || stocks.length === 0) return null;

  // 修复1: 从涨幅最大的异动标的正向推导
  const sorted = [...stocks].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0));
  const target = sorted[0];
  if (!target || Math.abs(target.change || 0) < 2) return null;

  const isUp = (target.change || 0) > 0;
  const changePct = (target.change || 0).toFixed(1);
  const industryName = target.industry && target.industry !== '其他' ? target.industry : '相关';

  // 计算成交额放大比例
  const allTurnovers = stocks.map(s => s.turnover || 0).filter(v => v > 0);
  const marketAvgTurnover = allTurnovers.length > 0
    ? allTurnovers.reduce((a, b) => a + b, 0) / allTurnovers.length
    : 0;
  const targetTurnover = target.turnover || 0;
  const turnoverRatio = marketAvgTurnover > 0 ? targetTurnover / marketAvgTurnover : 1;

  // 修复6: 行业卡片驱动逻辑同步到因果链触发事件
  let eventText = '';
  const matchingCard = industryCards.find(c => c.name === industryName);
  if (matchingCard && matchingCard.drivingLogic) {
    // 用行业卡片的驱动逻辑作为事件描述
    eventText = `${target.name}${isUp ? '大涨' : '大跌'}${changePct}%，${matchingCard.drivingLogic}`;
  } else {
    // 无匹配行业卡片时，从标的自身推导
    eventText = isUp
      ? `${target.name}（${industryName}）大涨${changePct}%，带动${industryName}板块跟涨`
      : `${target.name}（${industryName}）大跌${changePct}%，拖累${industryName}板块走弱`;
  }

  // 修复1: 资金确认必须显示具体数值
  let fundFlow = '';
  if (targetTurnover > 0 && marketAvgTurnover > 0) {
    const turnoverYi = (targetTurnover / 1e8).toFixed(2);
    const avgYi = (marketAvgTurnover / 1e8).toFixed(2);
    if (turnoverRatio > 1) {
      fundFlow = `成交额放大${turnoverRatio.toFixed(1)}倍（${turnoverYi}亿 vs 均值${avgYi}亿），主力资金${isUp ? '净流入' : '净流出'}`;
    } else {
      fundFlow = `成交额${turnoverYi}亿（均值${avgYi}亿），资金${isUp ? '温和流入' : '温和流出'}`;
    }
  } else {
    // 修复1: 无法获取真实资金流向数据时，明确提示
    fundFlow = '资金流向数据暂未接入';
  }

  const marketPerf = `${target.name} ${isUp ? '+' : ''}${changePct}%`;

  // 逻辑一致性: 价格方向与成交量是否匹配
  const directionConsistent = isUp ? turnoverRatio >= 1 : turnoverRatio <= 1;
  const evidenceCount = 3; // 事件 + 资金 + 表现
  const evidenceScore = evidenceCount / 3;
  const consistencyScore = directionConsistent ? 1.0 : 0.5;
  const confidence = Math.round(evidenceScore * consistencyScore * 100);

  let decision = '可纳入观察名单，等待确认信号';
  if (confidence >= 80) decision = '可关注介入机会，建议仓位不超过总仓位的5%';
  else if (confidence >= 60) decision = '可纳入观察名单，等待确认信号';
  else if (confidence >= 40) decision = '逻辑不完整，继续观察，暂不介入';
  else decision = '因果链断裂，不建议据此交易';

  return {
    event: eventText,
    fundFlow,
    marketPerf,
    decision,
    confidence,
    relatedStock: target.name,
    stockCode: target.code,
    evidenceCount,
    directionConsistent,
  };
}

// ---- 进化日志 ----
// 修复4: 传入当前占优因子名，保持与归因简评一致
function getEvolutionLogs(dominantFactorName: string): EvolutionLog[] {
  try {
    const raw = localStorage.getItem('simulation_account');
    if (!raw) return [];
    const account = JSON.parse(raw);
    const trades = account.tradeRecords || [];
    if (trades.length === 0) return [];

    const factorName = `${dominantFactorName}因子`;
    const factorStats: Record<string, { consecutiveFail: number; lastAdvice: boolean }> = {};
    const allLogs: EvolutionLog[] = [];

    const sorted = [...trades].sort((a, b) => new Date(a.date || 0).getTime() - new Date(b.date || 0).getTime());

    for (const t of sorted) {
      const profit = t.profit || 0;
      const fulfillmentRate = profit > 0 ? 100 : profit < 0 ? 33 : 50;

      if (!factorStats[factorName]) factorStats[factorName] = { consecutiveFail: 0, lastAdvice: false };
      if (fulfillmentRate < 50) {
        factorStats[factorName].consecutiveFail++;
      } else {
        factorStats[factorName].consecutiveFail = 0;
      }

      const weightChange = fulfillmentRate >= 80 ? 2 : fulfillmentRate < 40 ? -1 : 0;
      const triggerAdvice = factorStats[factorName].consecutiveFail >= 3 && !factorStats[factorName].lastAdvice;

      allLogs.push({
        date: (t.date || '').slice(5),
        stockName: t.name || '',
        stockCode: t.code || '',
        fulfillmentRate,
        factorName,
        weightChange,
        weightOld: 25,
        weightNew: 25 + weightChange,
        systemAdvice: triggerAdvice
          ? `审视"${factorName}"类因果链的初始置信度`
          : '',
      });

      if (triggerAdvice) factorStats[factorName].lastAdvice = true;
      if (fulfillmentRate >= 50) factorStats[factorName].lastAdvice = false;
    }

    return allLogs.slice(-3).reverse();
  } catch {
    return [];
  }
}

// ============ 修复5: 无交易记录时生成演示数据 ============
// 修复4: 传入当前占优因子名，保持与归因简评一致
function getDemoEvolutionLogs(stocks: any[], dominantFactorName: string): EvolutionLog[] {
  if (!stocks || stocks.length < 1) return [];
  const sorted = [...stocks].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0));
  const today = new Date();

  const formatDate = (d: Date) => `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const dayBefore = new Date(today);
  dayBefore.setDate(dayBefore.getDate() - 2);

  const factorName = `${dominantFactorName}因子`;

  // 演示条目1: 兑现率高的成功交易
  const stock1 = sorted[0];
  const rate1 = 85;
  const weightChange1 = 2;

  // 演示条目2: 兑现率低的失败交易
  const stock2 = sorted[1] || sorted[0];
  const rate2 = 33;
  const weightChange2 = -1;

  return [
    {
      date: formatDate(yesterday),
      stockName: stock1.name,
      stockCode: stock1.code,
      fulfillmentRate: rate1,
      factorName,
      weightChange: weightChange1,
      weightOld: 23,
      weightNew: 25,
      systemAdvice: '',
    },
    {
      date: formatDate(dayBefore),
      stockName: stock2.name,
      stockCode: stock2.code,
      fulfillmentRate: rate2,
      factorName,
      weightChange: weightChange2,
      weightOld: 24,
      weightNew: 23,
      systemAdvice: `审视"${factorName}"类因果链的初始置信度`,
    },
  ];
}

// ---- 连续涨跌行业追踪 ----
function getIndustryStreaks(strongIndustries: string[]): { name: string; streak: number }[] {
  try {
    const today = new Date().toDateString();
    const lastUpdate = localStorage.getItem('ind_streak_date');
    let streaks: Record<string, number> = {};

    if (lastUpdate !== today) {
      const prev = JSON.parse(localStorage.getItem('ind_streaks') || '{}');
      streaks = {};
      for (const name of strongIndustries) {
        streaks[name] = (prev[name] || 0) + 1;
      }
      localStorage.setItem('ind_streaks', JSON.stringify(streaks));
      localStorage.setItem('ind_streak_date', today);
    } else {
      streaks = JSON.parse(localStorage.getItem('ind_streaks') || '{}');
    }

    return Object.entries(streaks)
      .map(([name, streak]) => ({ name, streak }))
      .filter(s => s.streak >= 2)
      .sort((a, b) => b.streak - a.streak);
  } catch {
    return [];
  }
}

// ---- 策略连续跑赢追踪 ----
function getStrategyStreak(currentWinner: 'factor' | 'etf'): { winner: string; streak: number } | null {
  try {
    const today = new Date().toDateString();
    const lastUpdate = localStorage.getItem('strat_streak_date');
    let data = { winner: '', streak: 0 };

    if (lastUpdate !== today) {
      const prev = JSON.parse(localStorage.getItem('strat_streak') || '{"winner":"","streak":0}');
      if (prev.winner === currentWinner) {
        data = { winner: currentWinner, streak: prev.streak + 1 };
      } else {
        data = { winner: currentWinner, streak: 1 };
      }
      localStorage.setItem('strat_streak', JSON.stringify(data));
      localStorage.setItem('strat_streak_date', today);
    } else {
      data = JSON.parse(localStorage.getItem('strat_streak') || '{"winner":"","streak":0}');
    }

    if (data.streak >= 5) {
      return { winner: data.winner === 'factor' ? '因子' : 'ETF', streak: data.streak };
    }
    return null;
  } catch {
    return null;
  }
}

// ============ 修复4: 因子筛选条件描述 ============
function getFilterCondition(recIdx: number): string {
  switch (recIdx) {
    case 0: return '筛选条件：PE 0-200';
    case 1: return '筛选条件：利润增长率>0';
    case 2: return '筛选条件：ROE>0';
    case 3: return '筛选条件：1月涨幅>0';
    case 4: return '筛选条件：20日波动率>0';
    case 5: return '筛选条件：市值>0';
    default: return '';
  }
}

// ---- 组件 ----
export default function DashboardPage() {
  const { indices, sentiment: s, lastUpdate, isRealTime } = useRealTimeMarket();
  // 修复4: 获取loading状态和isReal状态
  const { stocks: realStocks, loading: stocksLoading, isReal: stocksReal } = useRealStockData();
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

  // ============ 修复2: 因子策略Top3 - 确保显示个股名称 ============
  const factorStrategy = useMemo(() => {
    const sorted = [...realStocks].sort((a, b) => (b.compositeScore || b.score || 0) - (a.compositeScore || a.score || 0));
    const top5 = sorted.slice(0, 5);
    const avgChange = top5.length > 0
      ? top5.reduce((sum, st) => sum + (st.change || 0), 0) / top5.length
      : 0;
    // 修复2: 明确显示个股名称
    const top3Names = top5.slice(0, 3).map(st => st.name).join(' · ');
    return { avgChange, top3Names, top5 };
  }, [realStocks]);

  // ============ 修复2: ETF轮动Top3 - 用holdSignal非signal，排除宽基 ============
  const etfStrategy = useMemo(() => {
    // 修复2: 排除宽基ETF，只显示行业/主题/跨境/债券/商品ETF
    const nonBroad = etfs.filter(e => e.category !== '宽基');
    // 修复2: 使用holdSignal而非signal
    const holding = nonBroad.filter(e => e.holdSignal === '买入' || e.holdSignal === '持有');
    let list = holding.length > 0 ? holding : nonBroad.slice(0, 5);
    // 最终降级
    if (list.length === 0) list = etfs.slice(0, 5);

    const avgChange = list.length > 0
      ? list.reduce((sum, e) => sum + (e.change || 0), 0) / list.length
      : 0;
    const top3Names = list.slice(0, 3).map(e => e.name).join(' · ');
    const bestEtf = list.length > 0
      ? [...list].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0))[0]
      : null;
    const attribution = bestEtf
      ? `${bestEtf.name}（${(bestEtf.change || 0) >= 0 ? '+' : ''}${(bestEtf.change || 0).toFixed(1)}%）贡献最大`
      : '暂无数据';
    return { avgChange, top3Names, attribution };
  }, [etfs]);

  const factorAttribution = useMemo(() => {
    const maxIdx = factorScores.indexOf(Math.max(...factorScores));
    return `${FACTOR_NAMES[maxIdx]}因子今日贡献最大`;
  }, [factorScores]);

  const factorWin = factorStrategy.avgChange >= etfStrategy.avgChange;

  // ---- 策略连续跑赢追踪 ----
  const strategyStreakAlert = useMemo(() => {
    return getStrategyStreak(factorWin ? 'factor' : 'etf');
  }, [factorWin]);

  // ---- 今日因子推荐 ----
  const factorRecommendation = useMemo(() => {
    const envFactorMap: Record<string, number> = { '趋势市': 3, '震荡市': 0, '高波动': 4 };
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
    if (recIdx === 0) candidates = candidates.filter(s => (s.factors?.pe || 0) > 0 && (s.factors?.pe || 999) < 200);
    if (recIdx === 4) candidates = candidates.filter(s => (s.factors?.vol20 || 0) > 0);
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

  // ---- 行业因果卡片 ----
  const industryCards = useMemo(() => buildIndustryCausalCards(realStocks), [realStocks]);

  const industryStreakAlerts = useMemo(() => {
    const strong = industryCards.filter(c => c.change > 3).map(c => c.name);
    return getIndustryStreaks(strong);
  }, [industryCards]);

  // ---- 因果链（联动行业卡片）----
  const causalChain = useMemo(() => buildCausalChain(realStocks, industryCards), [realStocks, industryCards]);

  // ============ 修复5: 进化日志 - 无记录时生成演示数据 ============
  const hasRealTrades = useMemo(() => {
    try {
      const raw = localStorage.getItem('simulation_account');
      if (!raw) return false;
      const account = JSON.parse(raw);
      return (account.tradeRecords || []).length > 0;
    } catch {
      return false;
    }
  }, []);

  const evolutionLogs = useMemo(() => {
    const logs = getEvolutionLogs(dominantFactor);
    if (logs.length > 0) return logs;
    return getDemoEvolutionLogs(realStocks, dominantFactor);
  }, [realStocks, dominantFactor]);

  // ---- 因子雷达 ----
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

  const trendLabel = marketEnv.trendScore > 60 ? '强' : marketEnv.trendScore > 30 ? '中性' : '弱';
  const volLabel = marketEnv.volScore > 80 ? '高' : marketEnv.volScore > 50 ? '正常' : '低';
  const envIcon = marketEnv.env === '趋势市' ? '📈' : marketEnv.env === '高波动' ? '⚠️' : '📊';

  // ============ 修复3: 行业卡片过滤 - 涨幅>1%才展示前3，跌幅<-1%才展示第1 ============
  const top3Industries = industryCards.filter(c => c.change > 1).slice(0, 3);
  const bottom1Industry = industryCards.length > 0 && industryCards[industryCards.length - 1].change < -1
    ? industryCards[industryCards.length - 1]
    : null;
  const northFlowAvailable = s.northFlow != null && s.northFlow !== undefined && !isNaN(s.northFlow);

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
          <div className="flex items-center gap-3 flex-wrap">
            {industryStreakAlerts.length > 0 && (
              <div className="flex items-center gap-1 text-xs text-orange-500">
                <Flame className="size-3.5" />
                {industryStreakAlerts[0].name}已连续{industryStreakAlerts[0].streak}日涨幅{'>'}3%
              </div>
            )}
            {strategyStreakAlert && (
              <div className="flex items-center gap-1 text-xs text-primary">
                <Zap className="size-3.5" />
                {strategyStreakAlert.winner}策略已连续{strategyStreakAlert.streak}日跑赢，建议短期侧重{strategyStreakAlert.winner}轮动
              </div>
            )}
            {weakFactorScore < 30 && (
              <div className="flex items-center gap-1 text-xs text-destructive">
                <AlertTriangle className="size-3.5" />
                {weakFactor}因子持续走弱（{weakFactorScore}分）
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ===== 左上：策略信号PK + 右上：核心因果链 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 策略信号PK */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <BarChart3 className="size-3.5 text-primary" />
            策略信号PK
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground font-medium">因子策略</div>
              <div className="text-lg font-bold" style={{ color: factorStrategy.avgChange >= 0 ? RISE_COLOR : FALL_COLOR }}>
                {factorStrategy.avgChange >= 0 ? '+' : ''}{(factorStrategy.avgChange || 0).toFixed(1)}%
                {!factorWin && <span className="ml-1 text-success">✅</span>}
              </div>
              <div className="text-[10px] text-muted-foreground">📈 持仓Top3个股</div>
              <div className="text-[10px] text-foreground leading-relaxed">{factorStrategy.top3Names || '暂无'}</div>
              <div className="text-[10px] text-muted-foreground pt-1 border-t border-border/20">{factorAttribution}</div>
            </div>
            <div className="space-y-2">
              <div className="text-[10px] text-muted-foreground font-medium">ETF轮动</div>
              <div className="text-lg font-bold" style={{ color: etfStrategy.avgChange >= 0 ? RISE_COLOR : FALL_COLOR }}>
                {etfStrategy.avgChange >= 0 ? '+' : ''}{(etfStrategy.avgChange || 0).toFixed(1)}%
                {factorWin && <span className="ml-1 text-success">✅</span>}
              </div>
              <div className="text-[10px] text-muted-foreground">📈 持仓Top3 ETF</div>
              <div className="text-[10px] text-foreground leading-relaxed">{etfStrategy.top3Names || '暂无'}</div>
              <div className="text-[10px] text-muted-foreground pt-1 border-t border-border/20">{etfStrategy.attribution}</div>
            </div>
          </div>
        </div>

        {/* 核心因果链 */}
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
              <div className="h-px bg-border/30" />
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">资金确认</span>
                <span className="text-xs text-foreground">{causalChain.fundFlow}</span>
              </div>
              <div className="h-px bg-border/30" />
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">市场表现</span>
                <span className="text-xs text-foreground">{causalChain.marketPerf}</span>
              </div>
              <div className="h-px bg-border/30" />
              <div className="flex items-start gap-2">
                <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">决策建议</span>
                <span className="text-xs font-medium text-primary">{causalChain.decision}</span>
              </div>
              <div className="pt-1">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] text-muted-foreground">
                    置信度（证据{causalChain.evidenceCount}/3 × {causalChain.directionConsistent ? '方向一致' : '方向不一致'}）
                  </span>
                  <span className="text-[10px] font-bold text-foreground">{causalChain.confidence}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted/50 overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{
                    width: `${causalChain.confidence}%`,
                    backgroundColor: causalChain.confidence >= 80 ? RISE_COLOR : causalChain.confidence >= 60 ? '#f59e0b' : FALL_COLOR,
                  }} />
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground pt-1">
                关联标的：<span className="text-foreground">{causalChain.relatedStock}（{causalChain.stockCode}）</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
              今日无显著异动（涨跌幅{'>'}2%），市场处于随机波动状态
            </div>
          )}
        </div>
      </div>

      {/* ===== 今日因子推荐 ===== */}
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
              <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${factorRecommendation.weightPct * 2}%` }} />
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
                        {change >= 0 ? '+' : ''}{change.toFixed(1)}%
                      </span>
                    </div>
                    <div className="text-[10px] text-primary mt-0.5">{factorVal}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            // ============ 修复4: 加载中/暂无数据/筛选条件 ============
            <div className="text-[10px] text-muted-foreground text-center py-2">
              {stocksLoading
                ? '数据加载中...'
                : !stocksReal
                  ? '因子数据加载中，请稍候...'
                  : `暂无符合条件的标的（${getFilterCondition(factorRecommendation.recIdx)}）`
              }
            </div>
          )}
        </div>
      </div>

      {/* ===== 左下：市场状态定性+行业因果卡片 + 右下：关键数据速览 ===== */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 市场状态定性 + 行业因果卡片 */}
        <div className="rounded-lg border border-border/40 bg-card/40 p-3">
          <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
            <Brain className="size-3.5 text-primary" />
            市场状态定性
          </h3>
          <div className="space-y-2 mb-3">
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
          <div className="mb-2">
            <ReactECharts option={factorRadarOption} theme="ud" style={{ height: '160px' }} />
          </div>

          {/* 行业因果卡片 */}
          <div className="pt-2 border-t border-border/20">
            <div className="text-[10px] text-muted-foreground mb-2 flex items-center gap-1">
              <ArrowUpDown className="size-3" />
              行业因果卡片 · 涨幅前3 + 跌幅第1
            </div>
            {/* ============ 修复3: 涨幅>1%才展示，不足显示提示 ============ */}
            {top3Industries.length > 0 ? (
              <div className="space-y-2">
                {/* 涨幅前3 */}
                {top3Industries.map((card, i) => (
                  <div key={card.name} className="p-2 rounded-md bg-muted/20 border-l-2"
                       style={{ borderColor: RISE_COLOR }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">#{i + 1}</span>
                        <span className="text-xs font-bold text-foreground">{card.name}</span>
                        <span className="text-[10px] text-muted-foreground">{card.count}只</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">涨{card.upCount}/跌{card.downCount}</span>
                        <span className="text-xs font-bold" style={{ color: RISE_COLOR }}>
                          +{card.change}%
                        </span>
                      </div>
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      领涨：<span className="text-foreground">{card.leadingStock}</span>
                      <span style={{ color: RISE_COLOR }}> +{card.leadingChange.toFixed(1)}%</span>
                      {card.turnoverRatio > 1.2 && (
                        <span className="ml-2 text-primary">成交放大{card.turnoverRatio.toFixed(1)}倍</span>
                      )}
                    </div>
                    <div className="text-[10px] text-foreground mt-0.5 leading-relaxed">
                      <ChevronRight className="size-2.5 inline text-primary" />
                      {card.drivingLogic}
                    </div>
                  </div>
                ))}
                {/* ============ 修复3: 跌幅<-1%才展示，否则隐藏 ============ */}
                {bottom1Industry && (
                  <div className="p-2 rounded-md bg-muted/20 border-l-2"
                       style={{ borderColor: FALL_COLOR }}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">↓</span>
                        <span className="text-xs font-bold text-foreground">{bottom1Industry.name}</span>
                        <span className="text-[10px] text-muted-foreground">{bottom1Industry.count}只</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-muted-foreground">涨{bottom1Industry.upCount}/跌{bottom1Industry.downCount}</span>
                        <span className="text-xs font-bold" style={{ color: FALL_COLOR }}>
                          {bottom1Industry.change}%
                        </span>
                      </div>
                    </div>
                    <div className="text-[10px] text-muted-foreground">
                      领跌：<span className="text-foreground">{bottom1Industry.weakestStock}</span>
                      <span style={{ color: FALL_COLOR }}> {bottom1Industry.weakestChange.toFixed(1)}%</span>
                    </div>
                    <div className="text-[10px] text-foreground mt-0.5 leading-relaxed">
                      <ChevronRight className="size-2.5 inline text-destructive" />
                      {bottom1Industry.drivingLogic}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-[10px] text-muted-foreground text-center py-3">今日无明显领涨行业（涨幅均{'<'}1%）</div>
            )}
          </div>
        </div>

        {/* 关键数据速览 */}
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
          <div className={`grid ${northFlowAvailable ? 'grid-cols-3' : 'grid-cols-2'} gap-2 mt-2`}>
            <div className="text-center p-2 rounded-md bg-muted/30">
              <div className="text-[10px] text-muted-foreground mb-0.5">两市成交</div>
              <div className="text-sm font-bold text-foreground">{(s.totalAmount || 0).toLocaleString()}亿</div>
            </div>
            {northFlowAvailable && (
              <div className="text-center p-2 rounded-md bg-muted/30">
                <div className="text-[10px] text-muted-foreground mb-0.5">北向资金</div>
                <div className="text-sm font-bold" style={{ color: (s.northFlow || 0) >= 0 ? RISE_COLOR : FALL_COLOR }}>
                  {(s.northFlow || 0) >= 0 ? '+' : ''}{s.northFlow}亿
                </div>
              </div>
            )}
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

      {/* ===== 进化日志 ===== */}
      <div className="rounded-lg border border-border/40 bg-card/40 p-3">
        <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
          <Zap className="size-3.5 text-primary" />
          进化日志 · 今日已自动调整
          {/* 修复5: 演示数据标记 */}
          {!hasRealTrades && evolutionLogs.length > 0 && (
            <span className="text-[10px] text-orange-500 ml-1">（演示数据）</span>
          )}
        </h3>
        {evolutionLogs.length > 0 ? (
          <div className="space-y-2">
            {evolutionLogs.map((log, i) => (
              <div key={i} className="flex items-center gap-3 p-2 rounded-md bg-muted/20 text-xs flex-wrap">
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
                  <span className="text-destructive flex items-center gap-0.5 w-full mt-1">
                    <AlertTriangle className="size-3 shrink-0" />
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
