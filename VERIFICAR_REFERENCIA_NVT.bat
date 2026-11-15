@echo off
setlocal
cd /d "%~dp0"
echo Baixa o banco NVT completo, verifica hashes e testa uma mao sintetica.
echo Precisa de internet e espaco para o ZIP mais o banco extraido.
echo Este teste nao movimenta o mouse e nao clica no PPPoker.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m strategy.reference_download --verify
) else (
  py -3.12 -m strategy.reference_download --verify
)
set "reference_exit=%errorlevel%"
echo.
if "%reference_exit%"=="0" (
  echo Banco e verificacao salvos na pasta runtime\hu\nvt-reference-...
) else (
  echo A verificacao falhou. Preserve a mensagem acima e os arquivos de diagnostico.
)
pause
exit /b %reference_exit%
