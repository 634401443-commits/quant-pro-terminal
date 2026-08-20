# QUANT PRO 桌面版 一键打包脚本 (PowerShell)
# 用法: 在 PowerShell 中运行  .\build-desktop.ps1
# 前置: 已安装 Python3 / Node.js; 前端 node_modules 已安装
# 产物: D:\股票仪表盘\releases\QUANT_PRO_Setup_2.7.0.exe
#
# 注意:
# - 后端 PyInstaller exe 在含中文/非ASCII路径下无法运行(bootloader 缺陷)，构建产物复制到英文路径验证
# - electron-builder 的 app-builder.exe(Go 二进制)在本环境无法创建目录/写 AppData，
#   因此使用 --dir 模式产出 win-unpacked 后用原生 makensis 制作 NSIS 安装包
# - makensis 需要下载: nsis-3.0.4.1.7z (GitHub electron-userland/electron-builder-binaries)

$ErrorActionPreference = "Stop"
$root = "D:\股票仪表盘"
$frontend = Join-Path $root "app_17beuetfu9m (2)"
$buildRoot = "C:\Users\86157\quantpro-build"
$desktop = Join-Path $buildRoot "desktop"
$releases = Join-Path $root "releases"
$electronZip = "$env:LOCALAPPDATA\electron\Cache\215349163.zip"

Write-Host "==== QUANT PRO 桌面版打包开始 ====" -ForegroundColor Cyan

# ---- 0. 环境准备 ----
New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null
New-Item -ItemType Directory -Path $releases -Force | Out-Null

# ---- 1. 前端构建 (vite build -> dist/) ----
Write-Host "[1/5] 前端构建..." -ForegroundColor Yellow
Push-Location $frontend
try { npx vite build; if ($LASTEXITCODE -ne 0) { throw "vite build 失败" } } finally { Pop-Location }
Write-Host "[1/5] 前端构建完成" -ForegroundColor Green

# ---- 2. 后端打包 (PyInstaller -> dist\backend\QUANT_PRO_backend\) ----
Write-Host "[2/5] 后端 PyInstaller 打包..." -ForegroundColor Yellow
Push-Location $root
try {
  python -m PyInstaller QUANT_PRO.spec --noconfirm --clean --distpath "$root\dist\backend" --workpath "$root\build\pyinstaller"
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }
} finally { Pop-Location }
# 复制到英文构建路径
Write-Host "[2/5] 复制后端产物到英文路径..." -ForegroundColor Yellow
$bdst = Join-Path $buildRoot "backend\QUANT_PRO_backend"
if (Test-Path $bdst) { Remove-Item $bdst -Recurse -Force }
python -c "import shutil,os; shutil.copytree(r'$root\dist\backend\QUANT_PRO_backend', r'$bdst')"
Write-Host "[2/5] 后端打包完成" -ForegroundColor Green

# ---- 3. Electron 工程准备 ----
Write-Host "[3/5] 准备 Electron 工程..." -ForegroundColor Yellow
$desktopSrc = Join-Path $root "desktop"
if (Test-Path $desktop) { Remove-Item $desktop -Recurse -Force }
python -c "import shutil; shutil.copytree(r'$desktopSrc', r'$desktop', ignore=shutil.ignore_patterns('node_modules'))"
Push-Location $desktop
try {
  if (-not (Test-Path node_modules)) { npm install; if ($LASTEXITCODE -ne 0) { throw "npm install 失败" } }
} finally { Pop-Location }
# 解压 electron 到本地 dist（避免 app-builder 下载）
if (-not (Test-Path "$buildRoot\electron-dist\electron.exe")) {
  if (-not (Test-Path $electronZip)) {
    Invoke-WebRequest -Uri 'https://github.com/electron/electron/releases/download/v33.4.11/electron-v33.4.11-win32-x64.zip' -OutFile $electronZip -UseBasicParsing -TimeoutSec 600
  }
  & "$env:USERPROFILE\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\bin\7z.exe" x $electronZip "-o$buildRoot\electron-dist" -y
}
Write-Host "[3/5] Electron 工程就绪" -ForegroundColor Green

# ---- 4. electron-builder --dir (产出 win-unpacked) ----
Write-Host "[4/5] electron-builder 打包目录..." -ForegroundColor Yellow
$winUnpacked = "C:\Users\86157\quantpro-releases\win-unpacked"
New-Item -ItemType Directory -Path $winUnpacked -Force | Out-Null
Push-Location $desktop
try { npx electron-builder --win dir; if ($LASTEXITCODE -ne 0) { throw "electron-builder 失败" } } finally { Pop-Location }
Write-Host "[4/5] win-unpacked 生成" -ForegroundColor Green

# ---- 5. makensis 制作 NSIS 安装包 ----
Write-Host "[5/5] makensis 打包 NSIS..." -ForegroundColor Yellow
$makensis = "C:\Users\86157\.trae-cn\work\6a719e82aba1f4ba6842046a\nsis-tool\makensis.exe"
if (-not (Test-Path $makensis)) {
  $nsisZip = "C:\Users\86157\.trae-cn\work\6a719e82aba1f4ba6842046a\nsis-3.0.4.1.7z"
  if (-not (Test-Path $nsisZip)) {
    Invoke-WebRequest -Uri 'https://github.com/electron-userland/electron-builder-binaries/releases/download/nsis-3.0.4.1/nsis-3.0.4.1.7z' -OutFile $nsisZip -UseBasicParsing -TimeoutSec 300
  }
  & "$env:USERPROFILE\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\vm\tools\bin\7z.exe" x $nsisZip "-o$buildRoot\..\..\..\..\..\..\..\..\..\.trae-cn\work\6a719e82aba1f4ba6842046a\nsis-tool" -y
}
& $makensis "$root\quantpro.nsi"
if ($LASTEXITCODE -ne 0) { throw "makensis 失败" }
Write-Host "[5/5] NSIS 打包完成" -ForegroundColor Green

# ---- 输出 ----
$setup = Join-Path $releases "QUANT_PRO_Setup_2.7.0.exe"
if (Test-Path $setup) {
  Write-Host "`n安装包已生成: $setup" -ForegroundColor Green
  Write-Host "大小: $([Math]::Round((Get-Item $setup).Length / 1MB, 1)) MB" -ForegroundColor Green
} else {
  Write-Host "警告: 未找到安装包" -ForegroundColor Red
}
Write-Host "==== 打包结束 ====" -ForegroundColor Cyan
