# coletar_logs.ps1 — junta os logs da ULTIMA sessao do Henrique numa pasta facil (Documentos) e abre,
# pronto pro Eduardo ANEXAR no chat. Pega os 2 arquivos que importam: o .log do agente (decisoes/
# cliques/H2N/"[AG] fim") e o .jsonl cru do --dump-raw (o mais importante p/ reproduzir bug offline).
$ErrorActionPreference = 'SilentlyContinue'

$install = Join-Path $env:LOCALAPPDATA 'NVT\Henrique'
$cands = @("$install\_internal\logs", "$install\logs") | Where-Object { Test-Path $_ }
if (-not $cands) {
    Write-Host "Nao achei a pasta de logs ($install\_internal\logs). Rode o Henrique ao menos uma vez." -ForegroundColor Yellow
    Read-Host "Enter para sair"; exit
}
$logdir = $cands[0]

$dest = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("NVT_Henrique\sessao_" + (Get-Date -Format 'yyyy-MM-dd_HHmmss'))
New-Item -ItemType Directory -Force -Path $dest | Out-Null

$got = 0
# 1) .log do agente (stdout): captura o que ele decidiu/clicou/salvou
Get-ChildItem "$logdir\suprema_*.log" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 2 |
    ForEach-Object { Copy-Item $_.FullName $dest; $got++ }
# 2) .jsonl cru (--dump-raw): o stream de eventos p/ reproduzir bugs offline (ANEXE ESTE sempre)
Get-ChildItem "$logdir\suprema_raw\*.jsonl" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
    ForEach-Object { Copy-Item $_.FullName $dest; $got++ }

if ($got -eq 0) {
    Write-Host "Pasta de logs existe mas esta vazia ($logdir). Rode uma sessao do Henrique primeiro." -ForegroundColor Yellow
    Read-Host "Enter para sair"; exit
}
Write-Host ">>> $got arquivo(s) de log copiado(s) para:"
Write-Host "    $dest"
Write-Host ">>> Anexe TODOS os arquivos dessa pasta aqui no chat."
Start-Process explorer.exe $dest
