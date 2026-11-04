import sys
import os
import cv2
import numpy as np

sys.path.append("repo_visualpilot")

from visualpilot.pppoker.card_recognition import CardRecognitionEngine

def main():
    image_path = "public/assets/aistudio/_FDB60F6B-7FAD-4C6D-B8D9-7C8B884199AC__1a424c2e.png"
    if not os.path.exists(image_path):
        print(f"[!] Erro: Imagem não encontrada em {image_path}")
        return

    print(f"[*] Carregando imagem de teste do usuário: {image_path}")
    frame = cv2.imread(image_path)
    if frame is None:
        print("[!] Erro ao decodificar imagem com OpenCV.")
        return

    h, w = frame.shape[:2]
    print(f"[*] Dimensões da captura: {w}x{h}")

    engine = CardRecognitionEngine(four_color_mode=True, game_variant="NLH")
    engine.table_width = w
    engine.table_height = h
    engine._init_rois("NLH")

    result = engine.read_table_frame(frame)

    print("\n--- RESULTADO DA LEITURA DE CARTAS ---")
    print(f"Status: {result['status']}")
    print(f"Hero Cards: {result['hero_cards']}")
    print(f"Board Cards: {result['board_cards']}")
    print(f"Invariante de 52 cartas (sem duplicadas): {result['invariant_passed']}")
    print(f"Avaliação da Mão: {result['hand_evaluation']}")
    print("---------------------------------------")

    annotated = frame.copy()
    for card in result['cards']:
        ymin, xmin, ymax, xmax = card['box']
        c_str = card['card_str'] or "Vazio"
        color = (0, 255, 0) if card['card_str'] else (0, 0, 255)
        cv2.rectangle(annotated, (xmin, ymin), (xmax, ymax), color, 2)
        cv2.putText(annotated, f"{card['slot_id']}:{c_str}", (xmin, max(20, ymin - 10)), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    os.makedirs("public/modulo2_evidencias", exist_ok=True)
    out_annotated = "public/modulo2_evidencias/annotated_user_test.png"
    cv2.imwrite(out_annotated, annotated)
    print(f"[*] Imagem anotada salva em: {out_annotated}")

if __name__ == "__main__":
    main()
