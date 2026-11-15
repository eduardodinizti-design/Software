@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" verificar_executor_hu.py --windows-owned
) else (
  py -3.12 verificar_executor_hu.py --windows-owned
)
echo.
echo O resultado esta em runtime\hu\verificacao-...\resultado.json
echo Esta janela de teste NAO valida os cliques no PPPoker.
pause
endlocal
