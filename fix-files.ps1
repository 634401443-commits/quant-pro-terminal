# Fix FactorPage.tsx - broken template literal in tooltip formatter
$factorFile = 'D:\股票仪表盘\app_17beuetfu9m (2)\src\pages\FactorPage\FactorPage.tsx'
$lines = [System.IO.File]::ReadAllLines($factorFile)
$fixed = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match 'formatter:.*ftsLabels') {
        Write-Host "Found broken line at index $i"
        $bt = [char]96   # backtick `
        $dl = [char]36   # dollar sign $
        # Build the replacement using single-quoted strings (literal) + char codes
        $newLine = '      tooltip: { position: ' + "'top'" + ', formatter: (p: any) => ' + $bt + $dl + '{ftsLabels[p.data[1]]} ' + [char]0x00d7 + ' ' + $bt + $dl + '{ftsLabels[p.data[0]]}<br/>' + [char]0x76f8 + [char]0x5173 + [char]0x7cfb + [char]0x6570 + ': ' + $bt + $dl + '{p.data[2]}' + $bt + ' },'
        $lines[$i] = $newLine
        Write-Host "Replaced with: $newLine"
        $fixed = $true
        break
    }
}
if ($fixed) {
    [System.IO.File]::WriteAllLines($factorFile, $lines)
    Write-Host "FactorPage.tsx fixed successfully"
} else {
    Write-Host "Pattern not found in FactorPage.tsx"
}

# Fix RotationPage.tsx - duplicate Activity import
$rotFile = 'D:\股票仪表盘\app_17beuetfu9m (2)\src\pages\RotationPage\RotationPage.tsx'
$c2 = [System.IO.File]::ReadAllText($rotFile)
$oldImport = "import { Zap, Activity } from 'lucide-react';"
$newImport = "import { Zap } from 'lucide-react';"
if ($c2.Contains($oldImport)) {
    $c2 = $c2.Replace($oldImport, $newImport)
    [System.IO.File]::WriteAllText($rotFile, $c2)
    Write-Host "RotationPage.tsx fixed - removed duplicate Activity import"
} else {
    Write-Host "Duplicate import not found in RotationPage.tsx"
}
