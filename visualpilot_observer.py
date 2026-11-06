"""
VisualPilot - Observer Diagnostic Script (visualpilot_observer.py)
Executa o pipeline de visão passiva em tempo real com métricas detalhadas de latência,
leitura de Hero e Board, e motivo de descarte ("NÃO IDENTIFICADO").
Instrução de 1 comando: python visualpilot_observer.py
"""
from __future__ import annotations
import os
import sys
import time
import cv2
from vision_pipeline import PPPokerObserverPipeline

def main():
    print("[*] Inicializando VisualPilot Observer (Senior CV Pipeline)...")
    pipeline = PPPokerObserverPipeline(templates_dir="templates_cards")

    cv2.namedWindow("VisualPilot - Observer Diagnostic", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("VisualPilot - Observer Diagnostic", 420, 750)

    print("[*] Observador ativo. Pressione 'q' na janela de vídeo para encerrar.")

    frame_count = 0
    total_latency = 0.0

    while True:
        t_start = time.perf_counter()
        frame, status = pipeline.capture_window()

        if frame is None:
            # Janela não encontrada, minimizada ou inválida
            canvas = np.zeros((720, 420, 3), dtype=np.uint8)
            cv2.putText(canvas, f"STATUS: {status}", (20, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("VisualPilot - Observer Diagnostic", canvas)
            
            if cv2.waitKey(50) & 0xFF == ord('q'):
                break
            continue

        results, debug_frame, latency_ms = pipeline.process_table(frame)
        
        frame_count += 1
        total_latency += latency_ms
        avg_latency = total_latency / frame_count

        board_cards = [results[k] for k in sorted(results.keys()) if 'board' in k]
        hero_cards = [results[k] for k in sorted(results.keys()) if 'hero' in k]

        print(f"[Frame #{frame_count}] Latência: {latency_ms:.1f}ms (Média: {avg_latency:.1f}ms) | Hero: {hero_cards} | Board: {board_cards}")

        # Adicionar métricas no topo do frame de debug
        fps = 1000.0 / max(0.1, latency_ms)
        cv2.putText(debug_frame, f"Latency: {latency_ms:.1f}ms | FPS: {fps:.1f}", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)

        cv2.imshow("VisualPilot - Observer Diagnostic", debug_frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    print("[*] Observador encerrado com sucesso.")

if __name__ == "__main__":
    import numpy as np
    main()
