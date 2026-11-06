@echo off
title VisualPilot Poker Bot - Standalone
cd /d "%~dp0"
echo [VisualPilot] Instalando dependencias necessarias...
python -m pip install opencv-python numpy pytesseract pillow --upgrade
echo.
echo [VisualPilot] Iniciando Bot...
python bot_standalone.py
pause