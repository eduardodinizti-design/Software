@echo off
REM Inicia o NVT Tracker ao fundo (janela minimizada). So LE e GRAVA as maos; nunca clica.
REM Auto-descobre a janela do PPPoker. Para PARAR: feche a janela minimizada "NVT Tracker".
cd /d "C:\Meus Projetos\Aplicativos\_repo_software"
start "NVT Tracker (feche para parar)" /min python assistir_mesa.py --ranges "C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json" --record --no-hotkeys
echo.
echo Tracker iniciado em janela minimizada. Grava em logs\maos_bot\ANO\MES\DIA\^<torneio^>.jsonl
echo Para parar: feche a janela minimizada "NVT Tracker".
