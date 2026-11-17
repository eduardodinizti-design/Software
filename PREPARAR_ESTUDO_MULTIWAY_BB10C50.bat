@echo off
setlocal
cd /d "%~dp0"
echo Laboratorio: BB com aproximadamente 10%% squeeze e 50%% call. Nao liga o bot.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m tools.prepare_multiway_pilot --bb-preset bb10c50-lab-v1 --output runtime\estudos\mp-btn-bb40-bb10c50 --samples 5000
) else (
  py -3.12 -m tools.prepare_multiway_pilot --bb-preset bb10c50-lab-v1 --output runtime\estudos\mp-btn-bb40-bb10c50 --samples 5000
)
if errorlevel 1 (
  echo Preparacao interrompida. Confira a mensagem e preserve estudos anteriores.
  pause
  exit /b 1
)
echo Arquivos preparados. Frequencias sao HIPOTESE; nenhuma politica pos-flop foi resolvida.
echo Siga docs\GUIA_BB10C50_20261117.txt para o calculo HRC.
pause
