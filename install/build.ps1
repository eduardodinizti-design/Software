# build.ps1 — compila o HENRIQUE num app windowed (dist\Henrique\Henrique.exe). Idempotente.
# Uso (da raiz do repo _repo_software):  powershell -ExecutionPolicy Bypass -File install\build.ps1
$ErrorActionPreference = 'Stop'

# garante CWD = raiz do repo (o spec referencia iniciar_suprema.py relativo ao CWD)
$repo = Split-Path -Parent $PSScriptRoot      # ...\_repo_software
Set-Location $repo
Write-Host ">>> Build do Henrique a partir de: $repo"

# PyInstaller presente?
python -c "import PyInstaller" 2>$null
if (-not $?) {
    Write-Host "PyInstaller nao encontrado. Instalando..."
    python -m pip install --upgrade pyinstaller
}

# limpa saidas antigas (idempotente)
foreach ($d in @('build\Henrique', 'dist\Henrique')) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
}

# compila
python -m PyInstaller --noconfirm --clean install\henrique.spec

if (Test-Path 'dist\Henrique\Henrique.exe') {
    Write-Host ""
    Write-Host ">>> OK: dist\Henrique\Henrique.exe"
    Write-Host ">>> Agora rode install\instalar.ps1 (no notebook) para criar o atalho + copiar as ranges."
} else {
    Write-Host ">>> FALHOU: dist\Henrique\Henrique.exe nao foi gerado. Veja o log acima." -ForegroundColor Red
    exit 1
}
