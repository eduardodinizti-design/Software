@echo off
setlocal
cd /d "%~dp0"
echo Preparacao de laboratorio MP x BTN x BB 40 BB. Nao liga o bot nem o HRC.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m tools.prepare_multiway_pilot --output runtime\estudos\mp-btn-bb40 --samples 5000
) else (
  py -3.12 -m tools.prepare_multiway_pilot --output runtime\estudos\mp-btn-bb40 --samples 5000
)
if errorlevel 1 (
  echo Preparacao interrompida. Preserve estudos anteriores e confira a mensagem acima.
  pause
  exit /b 1
)
echo Preparado. Siga docs\GUIA_MULTIWAY_MP_BTN_BB40_20261116.txt no HRC Pro.
echo Frequencias e melhores linhas ainda precisam ser calculadas. Nenhum clique foi enviado.
pause
