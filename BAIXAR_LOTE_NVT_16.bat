@echo off
setlocal
cd /d "%~dp0"
echo Baixa os 16 flops novos e o piloto anterior. Verifica hashes e consulta as tres ruas.
echo Os bancos ficam no disco; nao e necessario manter todas as politicas na RAM.
echo Precisa de internet e dezenas de GB livres no disco. Nao movimenta o mouse.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.batch_download
) else (
  py -3.12 -m strategy.batch_download
)
set "batch_download_exit=%errorlevel%"
echo.
if "%batch_download_exit%"=="0" (
  echo Banco salvo em runtime\hu\nvt-next16-...\bank\library.json
) else (
  echo Preserve a mensagem e os arquivos de diagnostico. Consulte o guia para retomar.
)
pause
exit /b %batch_download_exit%
