import { useState, useMemo } from 'react';
import { Link2, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, XCircle, HelpCircle, Brain, Gauge, Clock, TrendingUp, TrendingDown, Target } from 'lucide-react';
import { RISE_COLOR, FALL_COLOR } from '@/lib/chart-colors';
import type { EnhancedCausalChain, ValidationResult } from '@/lib/causal-engine';

interface Props {
  chain: EnhancedCausalChain | null;
}

// 状态图标
function StatusIcon({ status }: { status: ValidationResult['status'] }) {
  switch (status) {
    case 'pass': return <CheckCircle className="size-3.5 shrink-0" style={{ color: RISE_COLOR }} />;
    case 'warn': return <AlertTriangle className="size-3.5 shrink-0 text-amber-500" />;
    case 'fail': return <XCircle className="size-3.5 shrink-0" style={{ color: FALL_COLOR }} />;
    case 'skip': return <HelpCircle className="size-3.5 shrink-0 text-muted-foreground" />;
  }
}

// 评分条
function ScoreBar({ score, label }: { score: number; label?: string }) {
  const color = score >= 80 ? RISE_COLOR : score >= 60 ? '#f59e0b' : score >= 40 ? '#f97316' : FALL_COLOR;
  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-[10px] text-muted-foreground whitespace-nowrap">{label}</span>}
      <div className="flex-1 h-1.5 rounded-full bg-muted/50 overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${score}%`, backgroundColor: color }} />
      </div>
      <span className="text-[10px] font-bold" style={{ color }}>{score}分</span>
    </div>
  );
}

export default function CausalChainPanel({ chain }: Props) {
  const [expandedValidations, setExpandedValidations] = useState<Record<string, boolean>>({});
  const [showValidations, setShowValidations] = useState(true);

  const toggleValidation = (name: string) => {
    setExpandedValidations(prev => ({ ...prev, [name]: !prev[name] }));
  };

  if (!chain) {
    return (
      <div className="rounded-lg border border-border/40 bg-card/40 p-3">
        <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
          <Link2 className="size-3.5 text-primary" />
          核心因果链 · 多维度验证
        </h3>
        <div className="flex items-center justify-center h-[200px] text-xs text-muted-foreground">
          今日无显著异动（涨跌幅&gt;2%），市场处于随机波动状态
        </div>
      </div>
    );
  }

  // 综合评估星级颜色
  const starColor = chain.comprehensiveScore >= 85
    ? RISE_COLOR : chain.comprehensiveScore >= 70
      ? '#22c55e' : chain.comprehensiveScore >= 55
        ? '#f59e0b' : chain.comprehensiveScore >= 40
          ? '#f97316' : FALL_COLOR;

  const passCount = chain.validations.filter(v => v.status === 'pass').length;
  const warnCount = chain.validations.filter(v => v.status === 'warn').length;
  const failCount = chain.validations.filter(v => v.status === 'fail').length;
  const skipCount = chain.validations.filter(v => v.status === 'skip').length;

  return (
    <div className="rounded-lg border border-border/40 bg-card/40 p-3">
      <h3 className="text-xs font-semibold text-foreground mb-3 flex items-center gap-1.5">
        <Link2 className="size-3.5 text-primary" />
        核心因果链 · 多维度验证
        <span className="text-[10px] font-bold ml-auto" style={{ color: starColor }}>
          {chain.comprehensiveScore.toFixed(1)}分
        </span>
      </h3>

      {/* ===== 综合评估（置顶突出） ===== */}
      <div className="rounded-lg bg-gradient-to-r from-primary/10 via-primary/5 to-transparent p-3 mb-3 border border-primary/20">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-foreground flex items-center gap-1">
            <Brain className="size-3.5 text-primary" />
            综合因果强度评估
          </span>
          <span className="text-sm font-bold" style={{ color: starColor }}>
            {chain.starRating}
          </span>
        </div>

        {/* 评估明细 */}
        <div className="space-y-1.5 mb-2">
          <div className="text-[10px] text-muted-foreground">
            基础置信度：{chain.confidence}% × 0.30 = {(chain.confidence * 0.30).toFixed(1)}
          </div>
          {chain.validations.map(v => (
            <div key={v.name} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <StatusIcon status={v.status} />
              <span>{v.name}：{v.score}分 × {(v.name === '多因子共振' ? '0.20' : v.name === '干扰因子排除' ? '0.15' : v.name === '多时间尺度' ? '0.10' : v.name === '负向因果检查' ? '0.10' : v.name === '宏观归因' ? '0.10' : '0.05')} = {(v.score * (v.name === '多因子共振' ? 0.20 : v.name === '干扰因子排除' ? 0.15 : v.name === '多时间尺度' ? 0.10 : v.name === '负向因果检查' ? 0.10 : v.name === '宏观归因' ? 0.10 : 0.05)).toFixed(1)}</span>
            </div>
          ))}
          <div className="border-t border-border/20 pt-1.5 mt-1.5">
            <ScoreBar score={chain.comprehensiveScore} label="综合评分" />
          </div>
        </div>

        {/* 决策建议 */}
        <div className="flex items-center gap-3 text-[10px]">
          <div className="px-2 py-1 rounded bg-muted/30">
            <span className="text-muted-foreground">仓位 </span>
            <span className="font-bold text-foreground">{chain.positionAdvice}</span>
          </div>
          <div className="px-2 py-1 rounded bg-muted/30">
            <span className="text-muted-foreground">止损 </span>
            <span className="font-bold" style={{ color: FALL_COLOR }}>{chain.stopLossAdvice}</span>
          </div>
          <div className="px-2 py-1 rounded bg-muted/30">
            <span className="text-muted-foreground">止盈 </span>
            <span className="font-bold" style={{ color: RISE_COLOR }}>{chain.takeProfitAdvice}</span>
          </div>
          <div className="px-2 py-1 rounded bg-muted/30">
            <span className="text-muted-foreground">剩余效力 </span>
            <span className="font-bold text-foreground">{chain.remainingPotency.toFixed(1)}%</span>
          </div>
        </div>

        <div className="mt-2 text-[10px] font-medium text-primary flex items-center gap-1">
          <Target className="size-3" />
          {chain.operationAdvice}
        </div>
      </div>

      {/* ===== 基础因果链 ===== */}
      <div className="space-y-2 mb-3">
        <div className="flex items-start gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">触发事件</span>
          <span className="text-xs text-foreground">{chain.event}</span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">异动时间</span>
          <span className="text-xs text-foreground">{chain.eventTime} · {chain.eventType} · {chain.eventTag}</span>
        </div>
        <div className="h-px bg-border/30" />
        <div className="flex items-start gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">资金确认</span>
          <span className="text-xs text-foreground">{chain.fundFlow}</span>
        </div>
        <div className="h-px bg-border/30" />
        <div className="flex items-start gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">市场表现</span>
          <span className="text-xs text-foreground">{chain.marketPerf}</span>
        </div>
        <div className="flex items-start gap-2">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap mt-0.5">关联标的</span>
          <span className="text-xs font-medium text-foreground">{chain.relatedStock}（{chain.stockCode}）· {chain.stockIndustry}</span>
        </div>
      </div>

      {/* ===== 交叉验证折叠面板 ===== */}
      <div className="border border-border/20 rounded-lg overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-3 py-2 bg-muted/20 hover:bg-muted/30 transition-colors"
          onClick={() => setShowValidations(!showValidations)}
        >
          <span className="text-[10px] font-medium text-foreground flex items-center gap-2">
            <Gauge className="size-3" />
            交叉验证
            <span className="text-muted-foreground font-normal">
              {passCount}通过 {warnCount}警告 {failCount}未通过 {skipCount > 0 ? `${skipCount}跳过` : ''}
            </span>
          </span>
          {showValidations ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        </button>

        {showValidations && (
          <div className="divide-y divide-border/10">
            {chain.validations.map(v => (
              <div key={v.name}>
                <button
                  className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/10 transition-colors"
                  onClick={() => toggleValidation(v.name)}
                >
                  <StatusIcon status={v.status} />
                  <span className="text-[10px] font-medium text-foreground flex-1 text-left">{v.name}</span>
                  <span className="text-[10px] text-muted-foreground">{v.score}分</span>
                  {expandedValidations[v.name] ? <ChevronDown className="size-2.5" /> : <ChevronRight className="size-2.5" />}
                </button>

                {expandedValidations[v.name] && (
                  <div className="px-3 pb-2 space-y-1">
                    <div className="text-[10px] text-muted-foreground leading-relaxed">{v.detail}</div>

                    {v.subItems && v.subItems.length > 0 && (
                      <div className="mt-1.5 space-y-0.5">
                        {v.subItems.map((sub, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-[10px]">
                            <StatusIcon status={sub.status} />
                            <span className="text-muted-foreground">{sub.label}：</span>
                            <span className="text-foreground">{sub.value}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 衰减信息 */}
      <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
        <Clock className="size-3" />
        <span>因果衰减：{chain.decayDetail}</span>
      </div>
    </div>
  );
}