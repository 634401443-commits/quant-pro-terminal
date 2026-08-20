// ============================================================================
// QUANT PRO · 多维度交叉验证因果推理引擎
// v2.0 — 2026-08-07
// ============================================================================

// ===== 类型定义 =====

export interface ValidationResult {
  name: string;
  status: 'pass' | 'warn' | 'fail' | 'skip';
  score: number; // 0-100
  detail: string;
  subItems?: { label: string; value: string; status: 'pass' | 'warn' | 'fail' | 'skip' }[];
}

export interface EnhancedCausalChain {
  // 基础字段
  event: string;
  fundFlow: string;
  marketPerf: string;
  confidence: number;
  relatedStock: string;
  stockCode: string;
  stockIndustry: string;
  evidenceCount: number;
  directionConsistent: boolean;

  // 新增字段
  eventTime: string;
  eventType: string;
  eventTag: string;

  // 交叉验证结果
  validations: ValidationResult[];

  // 综合评估
  comprehensiveScore: number;
  starRating: string;
  positionAdvice: string;
  stopLossAdvice: string;
  takeProfitAdvice: string;
  operationAdvice: string;

  // 动态进化
  remainingPotency: number;
  decayType: string;
  decayDetail: string;
}

// ===== 风格映射表 =====

const STYLE_MAP: Record<string, { primary: string; secondary: string }> = {
  '半导体': { primary: '成长', secondary: '动量' },
  '电子': { primary: '成长', secondary: '动量' },
  '计算机': { primary: '成长', secondary: '动量' },
  '通信': { primary: '成长', secondary: '动量' },
  '传媒': { primary: '成长', secondary: '动量' },
  '医药生物': { primary: '成长', secondary: '质量' },
  '电力设备': { primary: '成长', secondary: '周期' },
  '汽车': { primary: '成长', secondary: '周期' },
  '银行': { primary: '价值', secondary: '质量' },
  '非银金融': { primary: '周期', secondary: '动量' },
  '房地产': { primary: '价值', secondary: '周期' },
  '食品饮料': { primary: '质量', secondary: '价值' },
  '煤炭': { primary: '周期', secondary: '价值' },
  '钢铁': { primary: '周期', secondary: '价值' },
  '有色金属': { primary: '周期', secondary: '价值' },
  '化工': { primary: '周期', secondary: '价值' },
  '机械设备': { primary: '周期', secondary: '成长' },
  '建筑装饰': { primary: '周期', secondary: '价值' },
  '国防军工': { primary: '成长', secondary: '周期' },
  '农林牧渔': { primary: '周期', secondary: '价值' },
  '环保': { primary: '周期', secondary: '成长' },
  '社会服务': { primary: '质量', secondary: '价值' },
  '建筑材料': { primary: '周期', secondary: '价值' },
};

// ===== 衰减系数 =====

const DECAY_LAMBDA: Record<string, number> = {
  '消息驱动': 0.17,   // 半衰期≈4小时
  '数据驱动': 0.03,   // 半衰期≈24小时
  '政策驱动': 0.004,  // 半衰期≈7天
  '结构驱动': 0.001,  // 半衰期≈30天
};

const DECAY_HALF_LIFE: Record<string, string> = {
  '消息驱动': '4小时',
  '数据驱动': '24小时',
  '政策驱动': '7天',
  '结构驱动': '30天',
};

// ============================================================================
// 验证1: 多因子共振验证
// ============================================================================

export function validateFactorResonance(
  stock: any,
  factorScores: number[],
  factorNames: string[]
): ValidationResult {
  const industry = stock.industry || '';
  const style = STYLE_MAP[industry];

  if (!style) {
    return {
      name: '多因子共振',
      status: 'skip',
      score: 50,
      detail: `行业"${industry}"无风格映射，跳过共振验证`,
    };
  }

  // factorScores: [价值, 成长, 质量, 动量, 波动率, 规模]
  const valueScore = factorScores[0] || 50;
  const growthScore = factorScores[1] || 50;
  const qualityScore = factorScores[2] || 50;
  const momentumScore = factorScores[3] || 50;

  const subItems: ValidationResult['subItems'] = [];
  let totalScore = 0;
  let maxScore = 3;

  // 检查主风格
  const primaryFactor = style.primary;
  let primaryScore = 50;
  let primaryName = '';
  if (primaryFactor === '成长') { primaryScore = growthScore; primaryName = '成长'; }
  else if (primaryFactor === '价值') { primaryScore = valueScore; primaryName = '价值'; }
  else if (primaryFactor === '质量') { primaryScore = qualityScore; primaryName = '质量'; }
  else if (primaryFactor === '周期') { primaryScore = momentumScore; primaryName = '动量(周期代理)'; }

  if (primaryScore > 60) {
    totalScore += 2;
    subItems.push({ label: `${primaryName}因子`, value: `${primaryScore}分，方向一致`, status: 'pass' });
  } else if (primaryScore >= 40) {
    totalScore += 1;
    subItems.push({ label: `${primaryName}因子`, value: `${primaryScore}分，中性`, status: 'warn' });
  } else {
    totalScore -= 1;
    subItems.push({ label: `${primaryName}因子`, value: `${primaryScore}分，方向不符`, status: 'fail' });
  }

  // 检查动量因子
  if (momentumScore > 60) {
    totalScore += 1;
    subItems.push({ label: '动量因子', value: `${momentumScore}分，动能确认`, status: 'pass' });
  } else if (momentumScore < 40) {
    totalScore -= 1;
    maxScore += 1;
    subItems.push({ label: '动量因子', value: `${momentumScore}分，动能不足`, status: 'fail' });
  } else {
    subItems.push({ label: '动量因子', value: `${momentumScore}分，中性`, status: 'warn' });
  }

  // 转换为0-100分
  const normalizedScore = Math.max(0, Math.min(100, ((totalScore + maxScore) / (maxScore * 2)) * 100));

  const passed = totalScore >= 2;
  const warning = totalScore === 1;

  return {
    name: '多因子共振',
    status: passed ? 'pass' : warning ? 'warn' : 'fail',
    score: Math.round(normalizedScore),
    detail: `${industry} → ${style.primary}风格，共振评分${totalScore >= 0 ? '+' : ''}${totalScore}分（满分+${maxScore}分）`,
    subItems,
  };
}

// ============================================================================
// 验证2: 干扰因子排除验证
// ============================================================================

export function validateInterferenceExclusion(
  stock: any,
  indices: any[],
  industryChange: number
): ValidationResult {
  const stockChange = stock.change || 0;

  // 获取大盘涨跌幅（沪深300或上证指数）
  const hs300 = indices.find((i: any) => i.code === '000300');
  const shIndex = indices.find((i: any) => i.code === '000001');
  const marketChange = hs300?.change || shIndex?.change || 0;

  // 行业涨跌幅
  const indChange = industryChange || 0;

  // 计算各贡献
  const marketContribution = marketChange * 0.7;
  const industryContribution = indChange * 0.3;
  const randomVol = 0.5;

  // 净事件驱动贡献
  const netContribution = stockChange - marketContribution - industryContribution - randomVol;

  const subItems = [
    { label: '大盘贡献', value: `${marketContribution >= 0 ? '+' : ''}${marketContribution.toFixed(2)}%（大盘${marketChange >= 0 ? '+' : ''}${marketChange.toFixed(2)}%×0.7）`, status: 'pass' as const },
    { label: '行业贡献', value: `${industryContribution >= 0 ? '+' : ''}${industryContribution.toFixed(2)}%（行业${indChange >= 0 ? '+' : ''}${indChange.toFixed(2)}%×0.3）`, status: 'pass' as const },
    { label: '随机波动', value: `+${randomVol.toFixed(2)}%`, status: 'pass' as const },
    { label: '净事件驱动', value: `${netContribution >= 0 ? '+' : ''}${netContribution.toFixed(2)}%`, status: netContribution > 5 ? 'pass' as const : netContribution > 2 ? 'warn' as const : 'fail' as const },
  ];

  let score = 20;
  let status: 'pass' | 'warn' | 'fail' = 'fail';
  let detail = '';

  if (Math.abs(netContribution) > 5) {
    score = 100;
    status = 'pass';
    detail = `净贡献${netContribution >= 0 ? '+' : ''}${netContribution.toFixed(2)}%（>5%），强事件驱动，因果链成立`;
  } else if (Math.abs(netContribution) > 2) {
    score = 60;
    status = 'warn';
    detail = `净贡献${netContribution >= 0 ? '+' : ''}${netContribution.toFixed(2)}%（2-5%），中事件驱动，因果链有效但弱化`;
  } else {
    score = 20;
    status = 'fail';
    detail = `净贡献${netContribution >= 0 ? '+' : ''}${netContribution.toFixed(2)}%（<2%），弱事件驱动，因果链降级`;
  }

  return { name: '干扰因子排除', status, score, detail, subItems };
}

// ============================================================================
// 验证3: 多时间尺度验证
// ============================================================================

export function validateTimeframe(stock: any): ValidationResult {
  const kline = stock.miniKline || stock.factors?.miniKline || [];
  const rsi = stock.factors?.rsi || 50;
  const bollPos = stock.factors?.bollPosition || 50;
  const maBullish = stock.factors?.maBullish;

  if (kline.length < 20) {
    return {
      name: '多时间尺度',
      status: 'skip',
      score: 50,
      detail: 'K线数据不足，跳过多时间尺度验证',
    };
  }

  // 简化版：用日K线数据代替5min/60min/Daily
  // 用最近5根K线作为"短期"，最近20根作为"中期"，全部作为"长期"
  const closes = kline;
  const ma5 = closes.slice(-5).reduce((a: number, b: number) => a + b, 0) / 5;
  const ma20 = closes.slice(-20).reduce((a: number, b: number) => a + b, 0) / 20;
  const currentPrice = closes[closes.length - 1];

  // 短期方向（MA5 vs 价格）
  const shortDir = currentPrice > ma5 ? '多头' : '空头';

  // 中期方向（MA5 vs MA20）
  const midDir = ma5 > ma20 ? '多头' : '空头';

  // 长期方向（MA20斜率 + RSI + 布林位置）
  const ma20First = closes.slice(-20, -10).reduce((a: number, b: number) => a + b, 0) / 10;
  const longDir = ma20 > ma20First && rsi > 50 ? '多头' : ma20 < ma20First && rsi < 50 ? '空头' : '中性';

  const subItems = [
    { label: '短期（MA5）', value: `${shortDir}（价格${currentPrice > ma5 ? '>' : '<'}MA5=${ma5.toFixed(2)}）`, status: shortDir === '多头' ? 'pass' as const : 'fail' as const },
    { label: '中期（MA5/MA20）', value: `${midDir}（MA5=${ma5.toFixed(2)} ${ma5 > ma20 ? '>' : '<'} MA20=${ma20.toFixed(2)}）`, status: midDir === '多头' ? 'pass' as const : 'fail' as const },
    { label: '长期（MA20斜率+RSI）', value: `${longDir}（RSI=${rsi.toFixed(0)}，布林${bollPos.toFixed(0)}%）`, status: longDir === '多头' ? 'pass' as const : longDir === '中性' ? 'warn' as const : 'fail' as const },
  ];

  // 一致性评分
  const bullCount = [shortDir, midDir, longDir].filter(d => d === '多头').length;
  const neutralCount = [shortDir, midDir, longDir].filter(d => d === '中性').length;

  let consistencyScore = 0;
  let status: 'pass' | 'warn' | 'fail' = 'fail';
  let detail = '';

  if (bullCount === 3) {
    consistencyScore = 3;
    status = 'pass';
    detail = '三尺度方向一致（多头），强一致（+3分）';
  } else if (bullCount === 2 && neutralCount === 1) {
    consistencyScore = 2;
    status = 'pass';
    detail = '短期+中期一致，长期中性，中一致（+2分）';
  } else if (bullCount === 2) {
    consistencyScore = 2;
    status = 'pass';
    detail = '两尺度多头一致，中一致（+2分）';
  } else if (bullCount === 1) {
    consistencyScore = 1;
    status = 'warn';
    detail = '仅一尺度多头，弱一致（+1分）';
  } else {
    consistencyScore = -1;
    status = 'fail';
    detail = '三尺度方向不一致，无一致性（-1分）';
  }

  const score = Math.max(0, Math.min(100, (consistencyScore / 3) * 100));

  return { name: '多时间尺度', status, score: Math.round(score), detail, subItems };
}

// ============================================================================
// 验证4: 负向因果检查
// ============================================================================

export function validateNegativeCausal(
  stock: any,
  allStocks: any[]
): ValidationResult {
  const subItems: ValidationResult['subItems'] = [];
  let hasNegative = false;
  let negativeCount = 0;

  // 1. 资金流出检查（用成交额方向作为代理）
  const stockChange = stock.change || 0;
  const stockTurnover = stock.turnover || 0;
  const allTurnovers = allStocks.map(s => s.turnover || 0).filter(v => v > 0);
  const avgTurnover = allTurnovers.length > 0
    ? allTurnovers.reduce((a, b) => a + b, 0) / allTurnovers.length
    : 0;
  const turnoverRatio = avgTurnover > 0 ? stockTurnover / avgTurnover : 1;

  // 如果涨但成交萎缩，可能是虚假突破
  if (stockChange > 3 && turnoverRatio < 0.7) {
    subItems.push({ label: '量价背离', value: `涨幅${stockChange.toFixed(1)}%但成交萎缩${(turnoverRatio).toFixed(2)}倍`, status: 'fail' });
    hasNegative = true;
    negativeCount++;
  } else {
    subItems.push({ label: '量价配合', value: `成交${turnoverRatio.toFixed(2)}倍均值，量价${stockChange > 0 && turnoverRatio > 1 ? '同向' : '正常'}`, status: 'pass' });
  }

  // 2. RSI超买检查
  const rsi = stock.factors?.rsi || 50;
  if (rsi > 80) {
    subItems.push({ label: 'RSI超买', value: `RSI=${rsi.toFixed(0)}，严重超买`, status: 'fail' });
    hasNegative = true;
    negativeCount++;
  } else if (rsi > 70) {
    subItems.push({ label: 'RSI偏高', value: `RSI=${rsi.toFixed(0)}，接近超买`, status: 'warn' });
  } else {
    subItems.push({ label: 'RSI正常', value: `RSI=${rsi.toFixed(0)}，正常区间`, status: 'pass' });
  }

  // 3. 布林位置检查
  const bollPos = stock.factors?.bollPosition || 50;
  if (bollPos > 95) {
    subItems.push({ label: '布林上轨', value: `布林位置${bollPos.toFixed(0)}%，触及上轨`, status: 'fail' });
    hasNegative = true;
    negativeCount++;
  } else if (bollPos > 85) {
    subItems.push({ label: '布林高位', value: `布林位置${bollPos.toFixed(0)}%，偏高`, status: 'warn' });
  } else {
    subItems.push({ label: '布林位置', value: `${bollPos.toFixed(0)}%，正常`, status: 'pass' });
  }

  // 4. 最大回撤检查
  const maxDD = stock.factors?.maxDrawdown || 0;
  if (maxDD < -20) {
    subItems.push({ label: '历史回撤', value: `20日最大回撤${maxDD.toFixed(1)}%，波动剧烈`, status: 'warn' });
  } else {
    subItems.push({ label: '历史回撤', value: `20日最大回撤${maxDD.toFixed(1)}%，可控`, status: 'pass' });
  }

  // 5. 融券/大宗/减持/龙虎榜 → 数据暂未接入
  subItems.push({ label: '融券余额', value: '暂未接入', status: 'skip' });
  subItems.push({ label: '大宗交易', value: '暂未接入', status: 'skip' });

  let score = 100;
  let status: 'pass' | 'warn' | 'fail' = 'pass';
  let detail = '';

  if (negativeCount >= 2) {
    score = 0;
    status = 'fail';
    detail = `发现${negativeCount}个反向信号，因果链受到挑战`;
  } else if (negativeCount === 1 || hasNegative) {
    score = 50;
    status = 'warn';
    detail = '存在弱反向信号，需谨慎';
  } else {
    score = 100;
    status = 'pass';
    detail = '无反向信号，因果链未受挑战';
  }

  return { name: '负向因果检查', status, score, detail, subItems };
}

// ============================================================================
// 验证5: 宏观归因验证
// ============================================================================

export function validateMacroAttribution(
  factorScores: number[]
): ValidationResult {
  // factorScores: [价值, 成长, 质量, 动量, 波动率, 规模]
  const valueScore = factorScores[0] || 50;
  const growthScore = factorScores[1] || 50;
  const momentumScore = factorScores[3] || 50;
  const volScore = factorScores[4] || 50;

  // 简化版：用因子得分推断宏观象限
  // 成长>价值 + 波动率适中 → 复苏象限
  // 成长>价值 + 波动率高 → 过热象限
  // 价值>成长 + 波动率高 → 滞涨象限
  // 价值>成长 + 波动率低 → 衰退象限

  let quadrant = '';
  let quadrantDetail = '';

  if (growthScore > valueScore) {
    if (volScore < 60) {
      quadrant = '复苏';
      quadrantDetail = `成长${growthScore}>价值${valueScore}，波动率适中${volScore}`;
    } else {
      quadrant = '过热';
      quadrantDetail = `成长${growthScore}>价值${valueScore}，波动率偏高${volScore}`;
    }
  } else {
    if (volScore > 60) {
      quadrant = '滞涨';
      quadrantDetail = `价值${valueScore}>成长${growthScore}，波动率偏高${volScore}`;
    } else {
      quadrant = '衰退';
      quadrantDetail = `价值${valueScore}>成长${growthScore}，波动率低${volScore}`;
    }
  }

  // 判断市场风格
  let marketStyle = '';
  if (growthScore > valueScore && growthScore > 60) {
    marketStyle = '成长占优';
  } else if (valueScore > growthScore && valueScore > 60) {
    marketStyle = '价值占优';
  } else {
    marketStyle = '风格均衡';
  }

  // 验证一致性
  let consistencyScore = 0;
  let status: 'pass' | 'warn' | 'fail' = 'warn';
  let detail = '';

  if ((quadrant === '复苏' || quadrant === '过热') && marketStyle === '成长占优') {
    consistencyScore = 2;
    status = 'pass';
    detail = `${quadrant}象限+成长占优，宏观与市场一致（+2分）`;
  } else if ((quadrant === '衰退' || quadrant === '滞涨') && marketStyle === '价值占优') {
    consistencyScore = 2;
    status = 'pass';
    detail = `${quadrant}象限+价值占优，宏观与市场一致（+2分）`;
  } else if (marketStyle === '风格均衡') {
    consistencyScore = 1;
    status = 'warn';
    detail = `${quadrant}象限+风格均衡，中性（+1分）`;
  } else {
    consistencyScore = -1;
    status = 'fail';
    detail = `${quadrant}象限+${marketStyle}，宏观与市场背离（-1分）`;
  }

  const score = consistencyScore >= 2 ? 100 : consistencyScore === 1 ? 60 : 20;

  const subItems = [
    { label: '宏观象限', value: `${quadrant}（${quadrantDetail}）`, status: 'pass' as const },
    { label: '市场风格', value: marketStyle, status: 'pass' as const },
    { label: '动量趋势', value: momentumScore > 50 ? '趋势占优' : '趋势偏弱', status: momentumScore > 50 ? 'pass' as const : 'warn' as const },
    { label: '数据来源', value: '因子得分推断（降级方案）', status: 'warn' as const },
  ];

  return { name: '宏观归因', status, score, detail, subItems };
}

// ============================================================================
// 验证6: 同类历史回测验证
// ============================================================================

export function validateHistoricalBacktest(
  stock: any,
  tradeRecords: any[]
): ValidationResult {
  // 尝试从localStorage读取历史因果链记录
  let historyRecords: any[] = [];

  try {
    const raw = localStorage.getItem('causal_chain_history');
    if (raw) {
      historyRecords = JSON.parse(raw);
    }
  } catch {
    // ignore
  }

  // 也检查交易记录
  const allRecords = [...historyRecords, ...tradeRecords];

  if (allRecords.length < 10) {
    return {
      name: '同类历史回测',
      status: 'skip',
      score: 50,
      detail: `数据积累中（当前${allRecords.length}条，需10条同类记录才能生成统计）`,
      subItems: [
        { label: '样本量', value: `${allRecords.length}条（不足10条）`, status: 'warn' },
        { label: '数据状态', value: '数据积累中', status: 'skip' },
      ],
    };
  }

  // 筛选同类记录（异动类型相同、幅度相近、板块相似）
  const stockChange = Math.abs(stock.change || 0);
  const stockIndustry = stock.industry || '';

  const similar = allRecords.filter(r => {
    const rChange = Math.abs(r.change || r.profit || 0);
    const rIndustry = r.industry || '';
    return (
      Math.abs(rChange - stockChange) < 5 &&
      (rIndustry === stockIndustry || rIndustry === '')
    );
  });

  if (similar.length < 3) {
    return {
      name: '同类历史回测',
      status: 'warn',
      score: 50,
      detail: `同类记录仅${similar.length}条，样本量不足`,
      subItems: [
        { label: '检索范围', value: `共${allRecords.length}条，同类${similar.length}条`, status: 'warn' },
        { label: '数据状态', value: '样本量不足', status: 'warn' },
      ],
    };
  }

  // 统计胜率
  const win1 = similar.filter(r => (r.day1 || r.profit || 0) > 0).length;
  const win3 = similar.filter(r => (r.day3 || r.profit || 0) > 0).length;
  const win5 = similar.filter(r => (r.day5 || r.profit || 0) > 0).length;
  const avg5 = similar.reduce((sum, r) => sum + (r.day5 || r.profit || 0), 0) / similar.length;
  const maxDD5 = Math.min(...similar.map(r => r.day5 || r.profit || 0));

  const winRate5 = win5 / similar.length;
  const winRate1 = win1 / similar.length;

  let score = 20;
  let status: 'pass' | 'warn' | 'fail' = 'fail';
  let detail = '';

  if (winRate5 > 0.7) {
    score = 100;
    status = 'pass';
    detail = `5日胜率${(winRate5 * 100).toFixed(1)}%（>70%），历史表现优秀`;
  } else if (winRate5 >= 0.5) {
    score = 60;
    status = 'warn';
    detail = `5日胜率${(winRate5 * 100).toFixed(1)}%（50-70%），表现中等`;
  } else {
    score = 20;
    status = 'fail';
    detail = `5日胜率${(winRate5 * 100).toFixed(1)}%（<50%），历史表现不佳`;
  }

  return {
    name: '同类历史回测',
    status,
    score,
    detail,
    subItems: [
      { label: '样本量', value: `${similar.length}条同类（总${allRecords.length}条）`, status: similar.length >= 10 ? 'pass' : 'warn' },
      { label: '1日胜率', value: `${(winRate1 * 100).toFixed(1)}%（${win1}/${similar.length}）`, status: winRate1 > 0.5 ? 'pass' : 'fail' },
      { label: '5日胜率', value: `${(winRate5 * 100).toFixed(1)}%（${win5}/${similar.length}）`, status: winRate5 > 0.5 ? 'pass' : 'fail' },
      { label: '5日均收益', value: `${avg5 >= 0 ? '+' : ''}${avg5.toFixed(2)}%`, status: avg5 > 0 ? 'pass' : 'fail' },
      { label: '5日最大回撤', value: `${maxDD5.toFixed(2)}%`, status: 'warn' },
    ],
  };
}

// ============================================================================
// 因果链衰减计算
// ============================================================================

export function calculateCausalDecay(
  eventType: string,
  initialPotency: number,
  hoursElapsed: number
): { remaining: number; detail: string; halfLife: string } {
  const lambda = DECAY_LAMBDA[eventType] || DECAY_LAMBDA['数据驱动'];
  const halfLife = DECAY_HALF_LIFE[eventType] || '24小时';

  const remaining = initialPotency * Math.exp(-lambda * hoursElapsed);

  const detail = `初始效力${initialPotency.toFixed(0)}% × e^(-${lambda}×${hoursElapsed}h) = ${remaining.toFixed(1)}%`;

  return { remaining, detail, halfLife };
}

// ============================================================================
// 综合因果强度评分
// ============================================================================

export function calculateComprehensiveScore(
  baseConfidence: number,
  validations: ValidationResult[]
): {
  score: number;
  starRating: string;
  positionAdvice: string;
  stopLossAdvice: string;
  takeProfitAdvice: string;
  operationAdvice: string;
} {
  // 权重
  const weights: Record<string, number> = {
    '基础置信度': 0.30,
    '多因子共振': 0.20,
    '干扰因子排除': 0.15,
    '多时间尺度': 0.10,
    '负向因果检查': 0.10,
    '宏观归因': 0.10,
    '同类历史回测': 0.05,
  };

  let score = baseConfidence * weights['基础置信度'];

  for (const v of validations) {
    const w = weights[v.name] || 0;
    score += v.score * w;
  }

  score = Math.max(0, Math.min(100, Math.round(score * 10) / 10));

  // 分级
  let starRating = '';
  let positionAdvice = '';
  let stopLossAdvice = '';
  let takeProfitAdvice = '';
  let operationAdvice = '';

  if (score >= 85) {
    starRating = '★★★★★ 极强';
    positionAdvice = '5-8%';
    stopLossAdvice = '-5%';
    takeProfitAdvice = '+15%';
    operationAdvice = '果断介入，可适度加仓';
  } else if (score >= 70) {
    starRating = '★★★★ 强';
    positionAdvice = '3-5%';
    stopLossAdvice = '-5%';
    takeProfitAdvice = '+12%';
    operationAdvice = '正常介入，标准仓位';
  } else if (score >= 55) {
    starRating = '★★★ 中';
    positionAdvice = '1-3%';
    stopLossAdvice = '-4%';
    takeProfitAdvice = '+10%';
    operationAdvice = '试探性介入，小仓位';
  } else if (score >= 40) {
    starRating = '★★ 弱';
    positionAdvice = '0-1%';
    stopLossAdvice = '-3%';
    takeProfitAdvice = '+8%';
    operationAdvice = '谨慎观察，暂不建议';
  } else {
    starRating = '★ 极弱';
    positionAdvice = '0%';
    stopLossAdvice = '—';
    takeProfitAdvice = '—';
    operationAdvice = '不交易，继续等待';
  }

  return { score, starRating, positionAdvice, stopLossAdvice, takeProfitAdvice, operationAdvice };
}

// ============================================================================
// 主构建函数: 构建增强版因果链
// ============================================================================

export function buildEnhancedCausalChain(
  stocks: any[],
  industryCards: any[],
  indices: any[],
  factorScores: number[],
  factorNames: string[],
  tradeRecords: any[] = []
): EnhancedCausalChain | null {
  if (!stocks || stocks.length === 0) return null;

  // 从涨幅最大的异动标的正向推导
  const sorted = [...stocks].sort((a, b) => Math.abs(b.change || 0) - Math.abs(a.change || 0));
  const target = sorted[0];
  if (!target || Math.abs(target.change || 0) < 2) return null;

  const isUp = (target.change || 0) > 0;
  const changePct = (target.change || 0).toFixed(1);
  const industryName = target.industry && target.industry !== '其他' ? target.industry : '相关';

  // 成交额计算
  const allTurnovers = stocks.map(s => s.turnover || 0).filter(v => v > 0);
  const marketAvgTurnover = allTurnovers.length > 0
    ? allTurnovers.reduce((a, b) => a + b, 0) / allTurnovers.length
    : 0;
  const targetTurnover = target.turnover || 0;
  const turnoverRatio = marketAvgTurnover > 0 ? targetTurnover / marketAvgTurnover : 1;

  // 触发事件
  const matchingCard = industryCards.find(c => c.name === industryName);
  let eventText = '';
  if (matchingCard && matchingCard.drivingLogic) {
    eventText = `${target.name}${isUp ? '大涨' : '大跌'}${changePct}%，${matchingCard.drivingLogic}`;
  } else {
    eventText = isUp
      ? `${target.name}（${industryName}）大涨${changePct}%，带动${industryName}板块跟涨`
      : `${target.name}（${industryName}）大跌${changePct}%，拖累${industryName}板块走弱`;
  }

  // 资金确认
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
    fundFlow = '资金流向数据暂未接入（降级方案：成交额放大比例替代）';
  }

  // 市场表现
  const industryChange = matchingCard?.change || 0;
  const marketPerf = `${target.name} ${isUp ? '+' : ''}${changePct}%，${industryName}板块${industryChange >= 0 ? '+' : ''}${industryChange.toFixed(1)}%`;

  // 基础置信度
  const directionConsistent = isUp ? turnoverRatio >= 1 : turnoverRatio <= 1;
  const evidenceCount = 3;
  const evidenceScore = evidenceCount / 3;
  const consistencyScore = directionConsistent ? 1.0 : 0.5;
  const baseConfidence = Math.round(evidenceScore * consistencyScore * 100);

  // 异动类型
  const eventType = isUp ? '大涨' : '大跌';
  const isVolumeSurge = turnoverRatio > 2;
  const eventTypeWithVolume = isVolumeSurge ? `${eventType}+放量` : eventType;

  // 事件标签
  let eventTag = '其他';
  if (matchingCard?.drivingLogic) {
    const logic = matchingCard.drivingLogic;
    if (logic.includes('政策') || logic.includes('文件')) eventTag = '政策';
    else if (logic.includes('财报') || logic.includes('数据')) eventTag = '财报';
    else if (logic.includes('板块') || logic.includes('联动')) eventTag = '行业';
    else if (logic.includes('产品') || logic.includes('技术')) eventTag = '产品';
  }

  // 衰减类型推断
  let decayType = '结构驱动';
  if (eventTag === '政策') decayType = '政策驱动';
  else if (eventTag === '财报') decayType = '数据驱动';
  else if (eventTag === '行业' || eventTag === '产品') decayType = '消息驱动';

  // ===== 运行6个交叉验证 =====
  const validations: ValidationResult[] = [];

  // 1. 多因子共振
  validations.push(validateFactorResonance(target, factorScores, factorNames));

  // 2. 干扰因子排除
  validations.push(validateInterferenceExclusion(target, indices, industryChange));

  // 3. 多时间尺度
  validations.push(validateTimeframe(target));

  // 4. 负向因果检查
  validations.push(validateNegativeCausal(target, stocks));

  // 5. 宏观归因
  validations.push(validateMacroAttribution(factorScores));

  // 6. 同类历史回测
  validations.push(validateHistoricalBacktest(target, tradeRecords));

  // ===== 综合评分 =====
  const decision = calculateComprehensiveScore(baseConfidence, validations);

  // ===== 因果衰减 =====
  // 假设事件发生在当前时间（0小时前），剩余效力=初始效力
  const decay = calculateCausalDecay(decayType, decision.score, 0);

  // ===== 构建完整因果链 =====
  return {
    event: eventText,
    fundFlow,
    marketPerf,
    confidence: baseConfidence,
    relatedStock: target.name,
    stockCode: target.code,
    stockIndustry: industryName,
    evidenceCount,
    directionConsistent,
    eventTime: new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }),
    eventType: eventTypeWithVolume,
    eventTag,
    validations,
    comprehensiveScore: decision.score,
    starRating: decision.starRating,
    positionAdvice: decision.positionAdvice,
    stopLossAdvice: decision.stopLossAdvice,
    takeProfitAdvice: decision.takeProfitAdvice,
    operationAdvice: decision.operationAdvice,
    remainingPotency: decay.remaining,
    decayType,
    decayDetail: `${decayType}，半衰期${decay.halfLife}，当前剩余效力${decay.remaining.toFixed(1)}%`,
  };
}
