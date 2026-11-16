@echo off
setlocal
cd /d "%~dp0"
echo SOFTWARE ORIGINAL - 17 flops SB x BB 40 BB, open 2 BB, BBA 1 BB.
echo O banco antigo fica preservado. Estes dados usam uma pasta nova.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.campaign_download --family sb40-next16 --output runtime\hu\sb40-17 --resume
) else (
  py -3.12 -m strategy.campaign_download --family sb40-next16 --output runtime\hu\sb40-17 --resume
)
set "hu_sb40_17_exit=%errorlevel%"
if "%hu_sb40_17_exit%"=="0" echo Banco: runtime\hu\sb40-17\bank\library.json
echo Este arquivo instala dados. Nao inicia o bot nem movimenta o mouse.
pause
exit /b %hu_sb40_17_exit%
