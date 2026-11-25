# Build do NVT BOT standalone (PyInstaller onedir, despachante nvtbot_main).
# Gera dist_bot\NVTBot\NVTBot.exe + INICIAR_BOT.bat. Copie a pasta NVTBot p/ o PC.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$name = "NVTBot"
$ranges1 = "C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json"
$ranges2 = "C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json"

Write-Host "Limpando build anterior..."
Remove-Item -Recurse -Force build_bot, dist_bot -ErrorAction SilentlyContinue

Write-Host "Rodando PyInstaller (pode levar alguns minutos)..."
python -m PyInstaller `
  --noconfirm --clean --onedir --console `
  --name "$name" `
  --distpath dist_bot --workpath build_bot `
  --paths "research\ppp_il2cpp" `
  --add-data "research\ppp_il2cpp\emitir_seats.js;research\ppp_il2cpp" `
  --add-data "research\ppp_il2cpp\capturar_maos.js;research\ppp_il2cpp" `
  --add-data "$ranges1;." `
  --add-data "$ranges2;." `
  --add-data "logs\exploit_db.json;logs" `
  --hidden-import operar_mesa `
  --hidden-import iniciar_bot `
  --hidden-import painel `
  --hidden-import emitir_seats `
  --hidden-import capturar_maos `
  --hidden-import win32api --hidden-import win32gui --hidden-import win32con `
  --hidden-import win32process --hidden-import win32ui `
  --hidden-import pytesseract `
  --collect-all frida `
  --collect-all cv2 `
  --collect-all tesserocr `
  nvtbot_main.py

if (Test-Path "dist_bot\$name\$name.exe") {
  # .bat de atalho dentro da pasta distribuida
  "@echo off`r`ncd /d `"%~dp0`"`r`nNVTBot.exe`r`npause" | Out-File -Encoding ascii "dist_bot\$name\INICIAR_BOT.bat"
  $mb = [math]::Round((Get-ChildItem "dist_bot\$name" -Recurse | Measure-Object Length -Sum).Sum/1MB,1)
  Write-Host "OK -> dist_bot\$name\ ($mb MB). Copie a pasta NVTBot p/ o outro PC e rode INICIAR_BOT.bat"
} else {
  Write-Host "FALHOU: dist_bot\$name\$name.exe nao foi gerado."
}
