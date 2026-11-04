"""
VisualPilot - PPPoker Standalone Bot & Scanner
Executável local em Python com Interface Tkinter, YOLOv8 Spatial Slot Mapper, CLAHE Normalization, HSV Color Isolation e Telemetria JSONL.
"""

from __future__ import annotations
import os
import sys
import time
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import tkinter as tk
from tkinter import ttk, scrolledtext

import cv2
import numpy as np

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

# Importar detector YOLOv8 local
try:
    from yolo_card_detector import YOLOv8CardDetector
except ImportError:
    YOLOv8CardDetector = None

# Windows API para captura de janelas se disponível
WIN32_AVAILABLE = False
if sys.platform == "win32":
    try:
        import ctypes
        from ctypes import wintypes
        WIN32_AVAILABLE = True
    except Exception:
        pass


def normalize_frame(frame_bgr: np.ndarray) -> np.ndarray:
    """
    Normaliza brilho e contraste usando CLAHE (Contrast Limited Adaptive Histogram Equalization)
    no espaço de cores LAB.
    """
    try:
        lab = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        normalized = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        return normalized
    except Exception:
        return frame_bgr


def preprocess_hsv_isolation(frame_bgr: np.ndarray) -> np.ndarray:
    """
    Pré-processamento HSV: isola regiões de alto brilho e naipes coloridos das cartas,
    neutralizando o fundo (feltro escuro da mesa) para máxima precisão na inferência YOLO.
    """
    try:
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        
        # Isolar elementos claros e cartas (V > 135)
        mask_cards = cv2.inRange(v, 135, 255)
        isolated = cv2.bitwise_and(frame_bgr, frame_bgr, mask=mask_cards)
        
        # Neutralizar o fundo escuro (feltro) para cinza neutro
        bg_mask = cv2.bitwise_not(mask_cards)
        neutral_bg = np.full_like(frame_bgr, (45, 45, 45))
        neutral_masked = cv2.bitwise_and(neutral_bg, neutral_bg, mask=bg_mask)
        
        final_processed = cv2.add(isolated, neutral_masked)
        return final_processed
    except Exception:
        return frame_bgr


class StandaloneVisualPilotApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("VisualPilot - PPPoker Standalone (HSV Isolation + CLAHE + YOLOv8)")
        self.root.geometry("1100x750")
        self.root.configure(bg="#0f172a")

        self.running = False
        self.monitor_thread = None

        # Criar pastas de logs automaticamente
        self.logs_dir = Path("logs/sessions")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.session_log_file = self.logs_dir / f"session_{int(time.time())}.jsonl"

        # Inicializar detector YOLOv8 com Debug View ativado por padrão
        self.detector = None
        if YOLOv8CardDetector is not None:
            try:
                self.detector = YOLOv8CardDetector(debug_view=True)
                print("[VisualPilot] YOLOv8 Card Detector com HSV Isolation carregado.")
            except Exception as e:
                print(f"[VisualPilot] Aviso: Falha ao carregar YOLOv8: {e}")

        self.create_widgets()

    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg="#1e293b", padx=15, pady=15)
        header_frame.pack(fill=tk.X, padx=10, pady=10)

        title_lbl = tk.Label(
            header_frame,
            text="VisualPilot • PPPoker Scanner, HSV Isolation & YOLOv8",
            font=("Arial", 16, "bold"),
            fg="#38bdf8",
            bg="#1e293b"
        )
        title_lbl.pack(side=tk.LEFT)

        # Controls
        ctrl_frame = tk.Frame(self.root, bg="#0f172a", padx=10, pady=5)
        ctrl_frame.pack(fill=tk.X, padx=10)

        self.btn_start = tk.Button(
            ctrl_frame,
            text="Iniciar Monitoramento",
            command=self.start_monitoring,
            bg="#10b981",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=5
        )
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(
            ctrl_frame,
            text="Parar",
            command=self.stop_monitoring,
            bg="#ef4444",
            fg="white",
            font=("Arial", 10, "bold"),
            padx=10,
            pady=5,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        # Debug View Checkbutton
        self.debug_var = tk.BooleanVar(value=True)
        self.chk_debug = tk.Checkbutton(
            ctrl_frame,
            text="Modo Debug View (OpenCV)",
            variable=self.debug_var,
            command=self.toggle_debug,
            bg="#0f172a",
            fg="#38bdf8",
            selectcolor="#1e293b",
            activebackground="#0f172a",
            activeforeground="#38bdf8",
            font=("Arial", 10, "bold")
        )
        self.chk_debug.pack(side=tk.LEFT, padx=15)

        # Status Table View
        table_frame = tk.Frame(self.root, bg="#0f172a", padx=10, pady=10)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "titulo", "status", "info")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
        self.tree.heading("id", text="ID")
        self.tree.heading("titulo", text="Título da Mesa PPPoker")
        self.tree.heading("status", text="Status")
        self.tree.heading("info", text="Cartas YOLOv8, Ações & HSV Isolation")

        self.tree.column("id", width=40, anchor=tk.CENTER)
        self.tree.column("titulo", width=180, anchor=tk.W)
        self.tree.column("status", width=110, anchor=tk.CENTER)
        self.tree.column("info", width=560, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Logs
        log_frame = tk.Frame(self.root, bg="#0f172a", padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10)

        tk.Label(log_frame, text="Log de Monitoramento & Telemetria JSONL:", fg="#94a3b8", bg="#0f172a", font=("Arial", 9, "bold")).pack(anchor=tk.W)
        self.log_txt = scrolledtext.ScrolledText(log_frame, height=8, bg="#020617", fg="#38bdf8", font=("Consolas", 9))
        self.log_txt.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log(f"Telemetria JSONL ativa em: {self.session_log_file}")

    def toggle_debug(self):
        if self.detector:
            self.detector.debug_view = self.debug_var.get()
        state_str = "ATIVADO" if self.debug_var.get() else "DESATIVADO"
        self.log(f"Modo Debug View (OpenCV): {state_str}")

    def log(self, msg: str):
        timestamp = time.strftime("[%H:%M:%S]")
        full_msg = f"{timestamp} {msg}\n"
        print(msg)
        if self.root.winfo_exists():
            self.log_txt.insert(tk.END, full_msg)
            self.log_txt.see(tk.END)

    def start_monitoring(self):
        if self.running:
            return
        self.running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.log("Iniciando monitoramento com HSV Isolation, CLAHE e Debug View...")

        self.monitor_thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        self.running = False
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.log("Monitoramento interrompido pelo usuário.")
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    def find_poker_windows(self) -> List[Tuple[int, str, Tuple[int, int, int, int]]]:
        windows = []
        if not WIN32_AVAILABLE:
            return windows

        user32 = ctypes.windll.user32

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def fn_enum(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    title_lower = title.lower()

                    blacklist = [
                        "explorador", "explorer", "visualpilot", "downloads", "documentos", 
                        "chrome", "edge", "firefox", "cmd", "powershell", "notepad", 
                        "visual studio", "code", "gemini", "whatsapp", "telegram"
                    ]
                    if any(b in title_lower for b in blacklist):
                        return True

                    whitelist = ["pppoker", "mppoker"]
                    if any(w in title_lower for w in whitelist):
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        width = rect.right - rect.left
                        height = rect.bottom - rect.top
                        
                        if width > 350 and height > 350:
                            windows.append((hwnd, title, (rect.left, rect.top, rect.right, rect.bottom)))
            return True

        user32.EnumWindows(fn_enum, 0)
        return windows

    def monitor_loop(self):
        while self.running:
            try:
                tables = self.find_poker_windows()
                
                for item in self.tree.get_children():
                    self.tree.delete(item)

                if not tables:
                    self.tree.insert("", tk.END, values=(1, "Aguardando Mesas PPPoker...", "Aguardando", "Nenhuma mesa oficial do PPPoker detectada."))
                else:
                    for idx, (hwnd, title, box) in enumerate(tables, 1):
                        left, top, right, bottom = box
                        info_str = f"Box: {box}"
                        cards_found = []
                        actions_found = []
                        raise_info = {}
                        fps_val = 0.0

                        if ImageGrab and right > left + 50 and bottom > top + 50:
                            try:
                                pil_img = ImageGrab.grab(bbox=(left, top, right, bottom))
                                frame_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                                
                                # 1. Normalização CLAHE (Brilho/Contraste)
                                frame_bgr = normalize_frame(frame_bgr)
                                
                                # 2. Pré-processamento HSV (Isolamento de cartas e neutralização de fundo)
                                frame_bgr = preprocess_hsv_isolation(frame_bgr)

                                if self.detector:
                                    res = self.detector.detect(frame_bgr)
                                    fps_val = res.fps
                                    cards_found = [c.class_name for c in res.cards] if res.cards else []
                                    actions_found = res.actions if res.actions else []
                                    raise_info = res.raise_info if res.raise_info else {}
                                    
                                    card_str = f"Cartas: {', '.join(cards_found) if cards_found else 'Nenhuma'}"
                                    action_str = f"Ações: {', '.join(actions_found) if actions_found else 'Aguardando'}"
                                    slider_str = f"Raise: {raise_info.get('bet_size', 'N/A')}" if raise_info.get('is_open') else "Raise: Fechado"
                                    
                                    info_str = f"{card_str} | [{action_str}] | {slider_str} | {res.inference_time_ms}ms ({res.fps} FPS)"
                            except Exception as ex:
                                info_str = f"Erro captura/YOLO: {ex}"
                        
                        self.tree.insert("", tk.END, values=(idx, title, "Ativa (HSV + CLAHE)", info_str))

                        log_entry = {
                            "timestamp": time.time(),
                            "table_id": idx,
                            "table_title": title,
                            "box": box,
                            "cards": cards_found,
                            "hero_actions": actions_found,
                            "raise_sizing": raise_info,
                            "fps": fps_val
                        }
                        try:
                            with open(self.session_log_file, "a", encoding="utf-8") as f:
                                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
                        except Exception:
                            pass

                time.sleep(0.4)
            except Exception as e:
                self.log(f"Erro no loop de monitoramento: {e}")
                time.sleep(2.0)


def main():
    root = tk.Tk()
    app = StandaloneVisualPilotApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
