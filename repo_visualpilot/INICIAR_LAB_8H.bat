@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Este executor precisa do ambiente Python do projeto nesta pasta.
  echo Nao e o executavel da Central. Consulte docs\lab-overnight\README.md.
  pause
  exit /b 1
)
echo Laboratorio com limite de 8 horas. Mantenha o computador ligado e sem suspender.
echo Para parar, abra PARAR_LAB_NOTURNO.bat. Resultados: sessions\overnight\RELATORIO.txt.
".venv\Scripts\python.exe" -m visualpilot.lab.overnight --hours 8 --output sessions/overnight --resume-stopped
pause
