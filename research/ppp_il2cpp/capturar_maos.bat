@echo off
REM Capturador de MÃOS ao vivo (READ-ONLY) — roda ao fundo e salva cada mão no formato
REM texto Hand2Note (<base>\ANO\MES\DIA\<torneio>.txt). Precisa do PPPoker aberto.
REM Reconecta sozinho se o PPPoker fechar/abrir. Ctrl+C para sair.
cd /d "%~dp0"
echo ============================================================
echo   CAPTURADOR DE MAOS (somente leitura) - deixe rodando
echo   Salva em: _repo_software\logs\maos_h2n\ANO\MES\DIA\*.txt
echo   (use --base para outra pasta; Ctrl+C para sair)
echo ============================================================
python -I capturar_maos.py %*
pause
