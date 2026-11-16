@echo off
setlocal
cd /d "%~dp0"
echo SOFTWARE ORIGINAL - piloto SB x BB 40 BB, open 2 BB, big-blind ante 1 BB.
echo Baixa a arvore completa e confere acoes, frequencias e sizes nas tres ruas.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.campaign_download --family sb40 --output runtime\hu\sb40 --resume
) else (
  py -3.12 -m strategy.campaign_download --family sb40 --output runtime\hu\sb40 --resume
)
set "hu_sb40_exit=%errorlevel%"
if "%hu_sb40_exit%"=="0" echo Banco: runtime\hu\sb40\bank\library.json
echo Este arquivo instala dados. Nao inicia o bot nem movimenta o mouse.
pause
exit /b %hu_sb40_exit%
