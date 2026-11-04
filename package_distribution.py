import os
import zipfile
from pathlib import Path

def create_distribution_zip():
    dist_dir = Path("public/downloads")
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / "VisualPilot_Bot_v1.0.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        repo_dir = Path("repo_visualpilot")
        if repo_dir.exists():
            for p in repo_dir.rglob("*"):
                if "__pycache__" in p.parts or ".git" in p.parts:
                    continue
                if p.is_file():
                    arcname = p.relative_to(repo_dir.parent)
                    zipf.write(p, arcname)

        bat_content = """@echo off
title VisualPilot Poker Bot - Central Operacional
echo Iniciando VisualPilot Bot Engine...
python -m pip install -r requirements.txt
python visualpilot/app.py
pause
"""
        zipf.writestr("run_bot.bat", bat_content)

        sh_content = """#!/bin/bash
echo "Iniciando VisualPilot Bot Engine..."
python3 -m pip install -r requirements.txt
python3 visualpilot/app.py
"""
        zipf.writestr("run_bot.sh", sh_content)

        req_content = """numpy>=1.20.0
opencv-python>=4.5.0
pytesseract>=0.3.8
requests>=2.25.0
"""
        zipf.writestr("requirements.txt", req_content)

        readme_content = """# VisualPilot Poker Bot - Pacote Distribuível v1.0

## Como Executar:
1. Instale o Python 3.10+ (Certifique-se de marcar 'Add Python to PATH').
2. No Windows, dê dois cliques em `run_bot.bat`. No Linux/Mac, execute `./run_bot.sh`.
3. O script instalará as dependências automaticamente e iniciará o motor de rastreamento multi-mesas, OCR temporal, State Machine e telemetria.
"""
        zipf.writestr("README.md", readme_content)

    print(f"Pacote distribuível criado com sucesso em: {zip_path}")

if __name__ == "__main__":
    create_distribution_zip()
