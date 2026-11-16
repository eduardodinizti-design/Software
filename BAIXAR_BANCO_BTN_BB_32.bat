@echo off
setlocal
cd /d "%~dp0"
echo SOFTWARE ORIGINAL - banco de 32 flops completos BTN x BB, 25 BB.
echo Baixa dados e verifica as tres ruas. Precisa de dezenas de GB de DISCO.
echo Retoma apenas a pasta identificada como pertencente a este banco.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.campaign_download --family btn32 --output runtime\hu\btn32 --resume
) else (
  py -3.12 -m strategy.campaign_download --family btn32 --output runtime\hu\btn32 --resume
)
set "hu_btn32_exit=%errorlevel%"
if "%hu_btn32_exit%"=="0" echo Banco: runtime\hu\btn32\bank\library.json
echo Este arquivo instala dados. Nao inicia o bot nem movimenta o mouse.
pause
exit /b %hu_btn32_exit%
