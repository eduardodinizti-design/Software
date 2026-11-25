@echo off
REM ============================================================
REM   NVT BOT - launcher completo. Duplo-clique e pronto.
REM   Sobe: operador ARMADO + exploit(HUD) + auto-fechar-bustada
REM         + capturador de maos (alimenta a DB).
REM   Precisa do PPPoker aberto com a mesa.
REM   Feche a janela (ou Ctrl+C) para parar TUDO.
REM ============================================================
cd /d "%~dp0"
python iniciar_bot.py
pause
