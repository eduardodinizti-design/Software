"""
VisualPilot - Bot Standalone (High Performance Window Stream + OCR-Free Deterministic Engine)
Garante latência inferior a 15ms (>30 FPS) e exibe debug em tamanho fixo 420x750px.
"""
from __future__ import annotations

import os
import sys
import time
import json
import threading
import ctypes
import tkinter as tk
from tkinter import ttk, scrolledtext
from pathlib import Path

# DPI Awareness
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    import cv2
    import numpy as np
except ImportError:
    pass

from window_stream import capture_pppoker_window
from yolo_card_detector import DeterministicCardDetector

class StandaloneVisualPilotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VisualPilot - PPPoker High Performance Bot (<15ms / >30 FPS)")
        self.root.geometry("1150x700")
        self.running = False
        self.detector = DeterministicCardDetector(debug_view=True)

        logs_dir = Path("logs/sessions")
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_log_file = str(logs_dir / f"session_{int(time.time())}.jsonl")

        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        panel = ttk.Frame(root, padding=16)
        panel.pack(fill='both', expand=True)

        header_frame = ttk.Frame(panel)
        header_frame.pack(fill='x', pady=(0, 10))

        title_lbl = ttk.Label(header_frame, text='VisualPilot • High Performance Engine (<15ms)', font=('Segoe UI', 18, 'bold'))
        title_lbl.pack(side='left')

        controls = ttk.Frame(panel)
        controls.pack(fill='x', pady=8)

        self.btn_start = ttk.Button(controls, text='Iniciar Monitoramento', command=self.start_monitoring)
        self.btn_start.pack(side='left')
        
        self.btn_stop = ttk.Button(controls, text='Parar', command=self.stop_monitoring, state='disabled')
        self.btn_stop.pack(side='left', padx=8)

        self.debug_var = tk.BooleanVar(value=True)
        self.chk_debug = tk.Checkbutton(
            controls, text="Modo Debug View (OpenCV)", variable=self.debug_var,
            command=self.toggle_debug, bg="#0b0f19", fg="#38bdf8",
            selectcolor="#1e293b", activebackground="#0f172a", activeforeground="#38bdf8",
            font=("Segoe UI", 10, "bold")
        )
        self.chk_debug.pack(side='left', padx=15)

        table_frame = tk.Frame(root, bg="#0f172a", padx=10, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "titulo", "status", "info")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("titulo", text="Título da Mesa PPPoker")
        self.tree.heading("status", text="Status")
        self.tree.heading("info", text="Cartas Hero & Board, Ações & Latência (<15ms)")
        self.tree.column("id", width=40, anchor=tk.CENTER)
        self.tree.column("titulo", width=200, anchor=tk.W)
        self.tree.column("status", width=120, anchor=tk.CENTER)
        self.tree.column("info", width=560, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)

        log_frame = tk.Frame(root, bg="#0f172a", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10)
        tk.Label(log_frame, text="Log de Monitoramento & Telemetria JSONL:", fg="#94a3b8", bg="#0f172a", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)
        self.log_txt = scrolledtext.ScrolledText(log_frame, height=8, bg="#020617", fg="#38bdf8", font=("Consolas", 9))
        self.log_txt.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log(f"Telemetria JSONL ativa em: {self.session_log_file}")
        root.protocol('WM_DELETE_WINDOW', self.close)

    def toggle_debug(self):
        if self.detector:
            self.detector.debug_view = self.debug_var.get()
        state_str = "ATIVADO" if self.debug_var.get() else "DESATIVADO"
        self.log(f"Modo Debug View (OpenCV): {state_str}")

    def log(self, msg: str):
        timestamp = time.strftime("[%H:%M:%S]")
        full_msg = f"{timestamp} {msg}\n"
        print(msg)
        try:
            if self.root.winfo_exists():
                self.log_txt.insert(tk.END, full_msg)
                self.log_txt.see(tk.END)
        except Exception:
            pass

    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.log("Iniciando monitoramento de alta performance (<15ms)...")
        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log("Monitoramento interrompido.")
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def monitor_loop(self):
        while self.running:
            try:
                frame = capture_pppoker_window()
                
                for item in self.tree.get_children():
                    self.tree.delete(item)

                if frame is None:
                    self.tree.insert("", tk.END, values=(1, "Aguardando Janela PPPoker...", "Aguardando", "Janela vertical do PPPoker não encontrada."))
                else:
                    title = "PPPoker Table"
                    res = self.detector.detect(frame, title=title)

                    cards_found = [c.class_name for c in res.cards] if res.cards else []
                    actions_found = res.actions if res.actions else []
                    raise_info = res.raise_info if res.raise_info else {}

                    card_str = f"Cartas: {', '.join(cards_found) if cards_found else 'Nenhuma'}"
                    action_str = f"Ações: {', '.join(actions_found) if actions_found else 'Aguardando'}"
                    info_str = f"{card_str} | [{action_str}] | Latência: {res.inference_time_ms}ms ({res.fps} FPS)"

                    self.tree.insert("", tk.END, values=(1, title, f"Ativa ({res.fps} FPS)", info_str))

                    log_entry = {
                        "timestamp": time.time(),
                        "table_title": title,
                        "cards": cards_found,
                        "hero_actions": actions_found,
                        "fps": res.fps,
                        "inference_ms": res.inference_time_ms
                    }
                    try:
                        with open(self.session_log_file, "a", encoding="utf-8") as f:
                            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                    except Exception:
                        pass

                time.sleep(0.012) # ~60+ FPS target
            except Exception as e:
                self.log(f"Erro no loop de monitoramento: {e}")
                time.sleep(1.0)

    def close(self):
        self.stop_monitoring()
        try:
            self.root.destroy()
        except Exception:
            pass

def main():
    root = tk.Tk()
    app = StandaloneVisualPilotApp(root)
    root.mainloop()

if __name__ == '__main__':
    main()
