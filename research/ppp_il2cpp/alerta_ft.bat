@echo off
REM Alarme de MESA FINAL — toca quando qualquer torneio chega na FT e repete a cada 5 min
REM ate voce apertar ENTER (assumiu o controle). Precisa do PPPoker aberto.
cd /d "%~dp0"
echo ============================================================
echo   ALERTA DE MESA FINAL  (PPPoker aberto + jogando torneio)
echo   - Toca quando bater a mesa final
echo   - Repete a cada 5 min ate voce apertar ENTER
echo   - ENTER = assumi o controle (silencia)  ^|  Ctrl+C = sair
echo ============================================================
python -I alerta_ft.py %*
pause
