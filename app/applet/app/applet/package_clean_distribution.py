import os
import zipfile
from pathlib import Path

def create_clean_zip():
    download_dir = Path("public/downloads")
    download_dir.mkdir(parents=True, exist_ok=True)
    
    zip_path = download_dir / "VisualPilot_Bot_Clean_v3.0.zip"
    
    essential_files = [
        "bot_standalone.py",
        "window_stream.py",
        "yolo_card_detector.py",
        "prepare_templates.py",
        "requirements.txt"
    ]
    
    print(f"[*] Criando pacote limpo em {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file in essential_files:
            # check root or app/applet
            if os.path.exists(file):
                zipf.write(file, arcname=file)
                print(f"    [+] Adicionado ao ZIP: {file}")
            elif os.path.exists(os.path.join("app/applet", file)):
                zipf.write(os.path.join("app/applet", file), arcname=file)
                print(f"    [+] Adicionado ao ZIP (de app/applet): {file}")
            else:
                print(f"    [!] Arquivo não encontrado: {file}")

    print(f"[+] Pacote limpo gerado com sucesso: {zip_path}")

if __name__ == "__main__":
    create_clean_zip()
