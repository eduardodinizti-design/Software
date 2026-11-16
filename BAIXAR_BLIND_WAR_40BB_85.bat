@echo off
setlocal
cd /d "%~dp0"
echo SOFTWARE ORIGINAL - 85 flops SB x BB 40 BB apos entrega completa.
echo Preserva os bancos anteriores; instala em runtime\hu\sb40-85.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.campaign_download --family sb40-85 --output runtime\hu\sb40-85 --resume
) else (
  py -3.12 -m strategy.campaign_download --family sb40-85 --output runtime\hu\sb40-85 --resume
)
set "hu_sb40_85_exit=%errorlevel%"
if "%hu_sb40_85_exit%"=="0" echo Banco: runtime\hu\sb40-85\bank\library.json
echo Este arquivo instala dados. Nao inicia o bot nem movimenta o mouse.
pause
exit /b %hu_sb40_85_exit%
