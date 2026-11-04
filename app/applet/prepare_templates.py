"""
VisualPilot - prepare_templates.py
Automatiza a geração de templates de cartas (ranks e naipes) a partir de recortes na pasta `raw_captures/`.
Aplica threshold de Otsu para contraste máximo e salva na pasta `templates_cards/`.
"""
from __future__ import annotations
import os
import cv2
import numpy as np
from pathlib import Path

def prepare_templates(raw_dir: str = "raw_captures", out_dir: str = "templates_cards"):
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)

    print(f"[*] Varrendo pasta de capturas brutas: '{raw_dir}'...")
    
    files = [f for f in os.listdir(raw_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not files:
        print(f"[!] A pasta '{raw_dir}' está vazia.")
        print(f"[*] Gerando templates sintéticos padrão (A a 2, naipes s, h, d, c) em '{out_dir}'...")
        
        ranks = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
        suits = ['s', 'h', 'd', 'c']

        for r in ranks:
            img = np.zeros((50, 40), dtype=np.uint8)
            cv2.putText(img, r, (5, 38), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3, cv2.LINE_AA)
            _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            out_path = os.path.join(out_dir, f"{r}.png")
            cv2.imwrite(out_path, binary)
            print(f"    [+] Template gerado: {out_path}")

        for s in suits:
            img = np.zeros((40, 40), dtype=np.uint8)
            cv2.putText(img, s.upper(), (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
            _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            out_path = os.path.join(out_dir, f"{s}.png")
            cv2.imwrite(out_path, binary)
            print(f"    [+] Template de naipe gerado: {out_path}")

        print(f"[+] Concluído! Todos os templates salvos em '{out_dir}'.")
        return

    processed = 0
    for filename in files:
        src_path = os.path.join(raw_dir, filename)
        img = cv2.imread(src_path, cv2.IMREAD_GRAYSCALE)
        if img is None or img.size == 0:
            continue

        # Binarização com Otsu para contraste máximo
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        base_name, _ = os.path.splitext(filename)
        clean_name = base_name.upper().strip()
        out_path = os.path.join(out_dir, f"{clean_name}.png")
        
        cv2.imwrite(out_path, binary)
        print(f"[+] Processado: {filename} -> {out_path}")
        processed += 1

    print(f"[*] Sucesso! {processed} templates processados e salvos em '{out_dir}'.")

if __name__ == "__main__":
    prepare_templates()
