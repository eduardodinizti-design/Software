@echo off
setlocal
cd /d "%~dp0"
echo SOFTWARE ORIGINAL - 34 flops SB x BB 40 BB, open 2 BB, BBA 1 BB.
echo Preserva os bancos anteriores; instala em runtime\hu\sb40-34.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.campaign_download --family sb40-34 --output runtime\hu\sb40-34 --resume
) else (
  py -3.12 -m strategy.campaign_download --family sb40-34 --output runtime\hu\sb40-34 --resume
)
set "hu_sb40_34_exit=%errorlevel%"
if "%hu_sb40_34_exit%"=="0" echo Banco: runtime\hu\sb40-34\bank\library.json
echo Este arquivo instala dados. Nao inicia o bot nem movimenta o mouse.
pause
exit /b %hu_sb40_34_exit%
