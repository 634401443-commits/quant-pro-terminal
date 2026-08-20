$ErrorActionPreference = "Stop"
$utf8 = [System.Text.Encoding]::UTF8

$path = "D:\股票仪表盘\app_17beuetfu9m (2)\src\pages\DashboardPage\DashboardPage.tsx"
$content = [System.IO.File]::ReadAllText($path, $utf8)
$lf = [char]10
$changes = 0

# 1) Add import for causal engine and CausalChainPanel
$importLine = "import { RISE_COLOR, FALL_COLOR, CHART_COLORS } from '@/lib/chart-colors';"
$newImport = "import { RISE_COLOR, FALL_COLOR, CHART_COLORS } from '@/lib/chart-colors';" + $lf + "import { buildEnhancedCausalChain } from '@/lib/causal-engine';" + $lf + "import CausalChainPanel from '@/components/CausalChainPanel';"

if ($content.Contains($importLine)) {
    $content = $content.Replace($importLine, $newImport)
    $changes++
    Write-Output "1: Added imports"
}

# 2) Replace the old causalChain useMemo with new enhanced version
$oldCausalMemo = "const causalChain = useMemo(() => buildCausalChain(realStocks, industryCards), [realStocks, industryCards]);"
$newCausalMemo = "const tradeRecords = useMemo(() => {" + $lf +
    "  try { const raw = localStorage.getItem('simulation_account'); if (!raw) return []; const a = JSON.parse(raw); return a.tradeRecords || []; } catch { return []; }" + $lf +
    "}, []);" + $lf +
    $lf +
    "const causalChain = useMemo(() => buildEnhancedCausalChain(realStocks, industryCards, indices, factorScores, FACTOR_NAMES, tradeRecords), [realStocks, industryCards, indices, factorScores, tradeRecords]);"

if ($content.Contains($oldCausalMemo)) {
    $content = $content.Replace($oldCausalMemo, $newCausalMemo)
    $changes++
    Write-Output "2: Updated causal chain useMemo"
} else {
    Write-Output "2: Pattern not found, trying index-based search"
    $idx = $content.IndexOf("const causalChain = useMemo")
    if ($idx -ge 0) {
        $endIdx = $content.IndexOf(");", $idx) + 2
        $endNext = $content.IndexOf($lf, $endIdx)
        if ($endNext -ge 0) $endIdx = $endNext
        $content = $content.Substring(0, $idx) + $newCausalMemo + $content.Substring($endIdx)
        $changes++
        Write-Output "2: Updated causal chain useMemo (via index)"
    }
}

# 3) Replace the old causal chain UI section (from "核心因果链" div to its closing)
# Find the section from '<div className="rounded-lg border border-border/40 bg-card/40 p-3">' near causal chain to just before next section
$searchStart = '        {/* 核心因果链 */}'
$searchEnd = '        </div>'
$idxStart = $content.IndexOf($searchStart)

if ($idxStart -ge 0) {
    # Find the closing div that matches the causal chain section
    # The section is followed by the 今日因子推荐 section
    $nextSection = $content.IndexOf('{/* ===== 今日因子推荐 =====}', $idxStart)
    if ($nextSection -ge 0) {
        # Find the closing div right before 今日因子推荐
        $idxEnd = $content.LastIndexOf($searchEnd, $nextSection - 1)
        if ($idxEnd -ge 0) {
            $idxEndEnd = $idxEnd + $searchEnd.Length
            $replacement = '        {/* 核心因果链 · 多维度验证 */}' + $lf +
                '        <CausalChainPanel chain={causalChain} />'
            $content = $content.Substring(0, $idxStart) + $replacement + $content.Substring($idxEndEnd)
            $changes++
            Write-Output "3: Replaced causal chain UI with CausalChainPanel"
        }
    } else {
        Write-Output "3: Could not find next section marker"
    }
} else {
    Write-Output "3: Could not find causal chain section start"
}

if ($changes -gt 0) {
    [System.IO.File]::WriteAllText($path, $content, $utf8)
    Write-Output "Total changes: $changes"
} else {
    Write-Output "No changes made"
}