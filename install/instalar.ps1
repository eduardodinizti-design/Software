# instalar.ps1 — INSTALADOR do Henrique no notebook. Roda a partir da pasta que contem `Henrique\`
# (a saida do build, ou a pasta descompactada do pacote).
#   powershell -ExecutionPolicy Bypass -File instalar.ps1
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot

# 1) localizar a pasta do app (Henrique\Henrique.exe) — aceita este dir, .\Henrique, .\dist\Henrique
$cands = @("$here\Henrique", "$here\dist\Henrique", $here) | Where-Object { Test-Path "$_\Henrique.exe" }
if (-not $cands) { Write-Host "Nao achei Henrique.exe. Rode o build primeiro (install\build.ps1)." -ForegroundColor Red; exit 1 }
$appSrc = $cands[0]
Write-Host ">>> App: $appSrc"

# 2) instalar em %LOCALAPPDATA%\NVT\Henrique
$dest = Join-Path $env:LOCALAPPDATA 'NVT\Henrique'
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force "$appSrc\*" $dest
$exe = Join-Path $dest 'Henrique.exe'
Write-Host ">>> Instalado em: $dest"

# 3) RANGES no caminho FIXO que o codigo espera (C:\Meus Projetos\Aplicativos) — caveat de portabilidade
$aplic = 'C:\Meus Projetos\Aplicativos'
New-Item -ItemType Directory -Force -Path $aplic | Out-Null
$rsrc = Join-Path $dest '_internal\ranges'          # PyInstaller 6 poe datas em _internal\
if (-not (Test-Path $rsrc)) { $rsrc = Join-Path $dest 'ranges' }
foreach ($fn in @('nvt-ranges-validados.json', 'nvt-ranges-deep.json')) {
    $s = Join-Path $rsrc $fn
    if (Test-Path $s) { Copy-Item -Force $s (Join-Path $aplic $fn); Write-Host ">>> range copiada: $fn" }
    elseif (-not (Test-Path (Join-Path $aplic $fn))) { Write-Host "AVISO: range $fn ausente no pacote E em $aplic — o Henrique nao decide sem ela." -ForegroundColor Yellow }
}

# 4) atalho "NVT Henrique" no Desktop
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'NVT Henrique.lnk'))
$lnk.TargetPath = $exe
$lnk.WorkingDirectory = $dest
$ico = Join-Path $dest '_internal\assets\nvt.ico'
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Description = 'NVT Henrique — agente da Suprema'
$lnk.Save()
Write-Host ">>> Atalho 'NVT Henrique' criado no Desktop."

# 4b) coletor de logs + atalho "Coletar logs do Henrique" (p/ o Eduardo exportar e anexar)
$coletor = Join-Path $here 'coletar_logs.ps1'
if (Test-Path $coletor) {
    Copy-Item -Force $coletor (Join-Path $dest 'coletar_logs.ps1')
    $lnk2 = $ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Coletar logs do Henrique.lnk'))
    $lnk2.TargetPath = "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe"
    $lnk2.Arguments = "-ExecutionPolicy Bypass -File `"$(Join-Path $dest 'coletar_logs.ps1')`""
    $lnk2.WorkingDirectory = $dest
    if (Test-Path $ico) { $lnk2.IconLocation = $ico }
    $lnk2.Description = 'Junta os logs da ultima sessao do Henrique em Documentos\NVT_Henrique e abre'
    $lnk2.Save()
    Write-Host ">>> Atalho 'Coletar logs do Henrique' criado no Desktop."
}

# 5) Tesseract-OCR (o anti-sit-out usa OCR do botao 'Estou de volta')
$tess = @("$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
          "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe") | Where-Object { Test-Path $_ }
if ($tess) { Write-Host ">>> Tesseract OK: $($tess[0])" }
else { Write-Host "ATENCAO: Tesseract-OCR NAO encontrado. Instale de https://github.com/UB-Mannheim/tesseract/wiki (o anti-sit-out precisa dele)." -ForegroundColor Yellow }

Write-Host ""
Write-Host ">>> PRONTO. Abra a Suprema numa mesa, depois clique no atalho 'NVT Henrique' no Desktop."
