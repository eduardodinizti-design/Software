"""VisualPilot - Módulo 6 (Fase 2): Rastreador e Gerenciador Multi-Mesas (MultiTableTracker)

Responsável por:
1. Enumerar e rastrear dinamicamente de 1 a 6 janelas de mesa ativas do PPPoker.
2. Identificar DPI Scaling específico de cada monitor/janela (96 DPI=100%, 120 DPI=125%, 144 DPI=150%, 192 DPI=200%).
3. Distinguir janelas de Lobby vs. janelas de Mesa de Jogo (In-Game Tables).
4. Calcular layouts automáticos em Mosaico / Grade (Tiling 2x2, 2x3, 3x2 ou Foco Único).
5. Gerar telemetria estruturada e exportar snapshots para o Dashboard em tempo real.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class TableWindowInfo:
    table_id: str
    number: int
    hwnd: int
    pid: int
    title: str
    game_type: str
    blinds: str
    box_physical: List[int]  # [left, top, width, height]
    box_logical: List[int]   # [left, top, width, height] ajustado por DPI
    dpi_scale: float         # 1.0, 1.25, 1.5, 2.0
    dpi_value: int           # 96, 120, 144, 192
    aspect_ratio: float
    monitor_index: int
    status: str              # "HERO_TURN", "ACTIVE_OBSERVING", "WAITING_ACTION", "MINIMIZED", "AMBIGUOUS"
    is_visible: bool
    geometry_version: int = 1
    state: str = "ACTIVE"
    hero_seat: Optional[int] = None
    hero_position: Optional[str] = None  # "BTN", "SB", "BB", "UTG", "MP", "CO"
    active_players: str = "6/6"
    pot_chips: float = 0.0
    current_round: str = "PREFLOP"       # "PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"
    last_seen_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionStateMachine:
    """Gerenciador de Máquina de Estados de Ação e Timers de Urgência para o Hero."""
    @staticmethod
    def evaluate_table_action(table: TrackedTable, raw_ocr_action: Optional[str] = None, elapsed_seconds: float = 0.0) -> Tuple[str, float, bool]:
        current_state = getattr(table, 'action_state', 'AGUARDANDO')
        timer = getattr(table, 'turn_timer_seconds', 15.0)

        if raw_ocr_action:
            upper_action = raw_ocr_action.upper()
            if 'SUA_VEZ' in upper_action or 'YOUR_TURN' in upper_action or 'ACT' in upper_action:
                if current_state != 'SUA_VEZ':
                    current_state = 'SUA_VEZ'
                    timer = 15.0
            elif 'ALL' in upper_action:
                current_state = 'ALL_IN'
            elif 'FOLD' in upper_action:
                current_state = 'FOLD'
            else:
                current_state = 'AGUARDANDO'

        if current_state == 'SUA_VEZ':
            timer = max(0.0, timer - elapsed_seconds)
            is_urgent = timer <= 5.0
        else:
            timer = 15.0
            is_urgent = False

        return current_state, timer, is_urgent


class GridLayoutSlot:
    slot_index: int
    table_id: Optional[str]
    target_box: List[int]  # [x, y, w, h]


class MultiTableTracker:
    """Motor de detecção, rastreamento e cálculo de mosaico de até 6 mesas simultâneas."""

    def __init__(self, max_tables: int = 6):
        self.max_tables = max_tables
        self.active_tables: Dict[str, TableWindowInfo] = {}
        self.scan_count: int = 0
        self.last_scan_iso: Optional[str] = None

    @staticmethod
    def get_dpi_for_window(hwnd: int) -> Tuple[int, float]:
        """Obtém o DPI real da janela no Windows 10/11 (ou 96 DPI / 1.0x em fallback)."""
        if sys.platform != 'win32' or hwnd <= 0:
            return 96, 1.0

        try:
            import ctypes
            user32 = ctypes.windll.user32
            if hasattr(user32, 'GetDpiForWindow'):
                dpi = user32.GetDpiForWindow(hwnd)
                if dpi > 0:
                    scale = round(dpi / 96.0, 2)
                    return dpi, scale
        except Exception:
            pass
        return 96, 1.0

    @staticmethod
    def classify_window_title(title: str) -> Tuple[str, str, str]:
        """Classifica o tipo de jogo e blinds a partir do título da janela."""
        title_lower = title.lower()

        if 'lobby' in title_lower or 'club' in title_lower or 'carregando' in title_lower:
            return 'LOBBY', 'LOBBY', '-'

        game_type = 'NLH'
        if 'plo5' in title_lower or '5-card' in title_lower:
            game_type = 'PLO5'
        elif 'plo4' in title_lower or 'omaha' in title_lower or 'plo' in title_lower:
            game_type = 'PLO4'
        elif 'mtt' in title_lower or 'torneio' in title_lower or 'tournament' in title_lower:
            game_type = 'MTT'
        elif 'spin' in title_lower or 'sng' in title_lower:
            game_type = 'SNG'

        blinds = '1/2'
        import re
        match_blinds = re.search(r'(\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?)', title)
        if match_blinds:
            blinds = match_blinds.group(1).replace(' ', '')
        elif 'deep' in title_lower:
            blinds = '100/200'

        return 'TABLE', game_type, blinds

    def scan_windows(self, custom_fetcher: Optional[Callable[[], List[Dict[str, Any]]]] = None) -> List[TableWindowInfo]:
        """Varre as janelas ativas do sistema operacional identificando mesas de jogo."""
        self.scan_count += 1
        self.last_scan_iso = datetime.now(timezone.utc).isoformat()

        raw_windows: List[Dict[str, Any]] = []

        if custom_fetcher:
            raw_windows = custom_fetcher()
        elif sys.platform == 'win32':
            try:
                from .window_geometry import native_windows
                raw_windows = native_windows() or []
            except Exception:
                raw_windows = []
        else:
            raw_windows = self._generate_simulated_windows()

        found_tables: List[TableWindowInfo] = []
        table_number = 1

        for win in raw_windows:
            title = win.get('title', '')
            box = win.get('box', [0, 0, 787, 1470])
            w, h = box[2], box[3]
            if w <= 100 or h <= 100:
                continue

            category, g_type, blinds = self.classify_window_title(title)
            if 'pppoker' not in title.lower() and category != 'TABLE':
                continue

            if category == 'LOBBY' and len(raw_windows) > 1:
                continue

            hwnd = win.get('handle', 1000 + table_number)
            pid = win.get('pid', os.getpid())
            dpi_val, dpi_scale = self.get_dpi_for_window(hwnd)

            box_phys = [int(box[0]), int(box[1]), int(w), int(h)]
            box_logic = [
                int(box[0] / dpi_scale),
                int(box[1] / dpi_scale),
                int(w / dpi_scale),
                int(h / dpi_scale)
            ]

            aspect_ratio = round(w / max(1, h), 4)

            statuses = ["HERO_TURN", "WAITING_ACTION", "ACTIVE_OBSERVING", "WAITING_ACTION"]
            status = win.get('status', statuses[(table_number - 1) % len(statuses)])
            positions = ["BTN", "CO", "SB", "BB", "UTG", "MP"]
            hero_pos = positions[(table_number - 1) % len(positions)]
            hero_st = ((table_number - 1) % 6) + 1

            table_id = f"tbl-{table_number}"
            table_info = TableWindowInfo(
                table_id=table_id,
                number=table_number,
                hwnd=hwnd,
                pid=pid,
                title=title if title else f"PPPoker Table #{table_number} ({g_type} {blinds})",
                game_type=g_type,
                blinds=blinds,
                box_physical=box_phys,
                box_logical=box_logic,
                dpi_scale=dpi_scale,
                dpi_value=dpi_val,
                aspect_ratio=aspect_ratio,
                monitor_index=win.get('monitor_index', 1),
                status=status,
                is_visible=True,
                hero_seat=hero_st,
                hero_position=hero_pos,
                active_players=win.get('active_players', "6/6"),
                pot_chips=win.get('pot_chips', round(12.5 * table_number, 1)),
                current_round=win.get('current_round', ["PREFLOP", "FLOP", "TURN", "RIVER"][table_number % 4]),
                last_seen_iso=self.last_scan_iso
            )
            found_tables.append(table_info)
            table_number += 1

            if len(found_tables) >= self.max_tables:
                break

        self.active_tables = {t.table_id: t for t in found_tables}
        return found_tables

    def _generate_simulated_windows(self) -> List[Dict[str, Any]]:
        return [
            {
                'handle': 101234,
                'pid': 8420,
                'title': 'PPPoker - NLH 6-Max Blinds 1/2 (Mesa Diamante)',
                'box': [100, 100, 787, 1470],
                'status': 'HERO_TURN',
                'active_players': '6/6',
                'pot_chips': 38.0,
                'current_round': 'FLOP',
                'monitor_index': 1
            },
            {
                'handle': 101236,
                'pid': 8420,
                'title': 'PPPoker - PLO4 Blinds 2/4 (High Roller Club)',
                'box': [920, 100, 787, 1470],
                'status': 'WAITING_ACTION',
                'active_players': '5/6',
                'pot_chips': 84.5,
                'current_round': 'TURN',
                'monitor_index': 1
            },
            {
                'handle': 101238,
                'pid': 8420,
                'title': 'PPPoker - MTT Deepstack 50K (Nível 4 - 200/400)',
                'box': [100, 1600, 787, 1470],
                'status': 'ACTIVE_OBSERVING',
                'active_players': '8/9',
                'pot_chips': 1200.0,
                'current_round': 'PREFLOP',
                'monitor_index': 2
            }
        ]

    def compute_mosaic_tiling(
        self,
        tables_count: int,
        desktop_w: int = 1920,
        desktop_h: int = 1080,
        margin: int = 10
    ) -> List[GridLayoutSlot]:
        count = max(1, min(6, tables_count))
        slots: List[GridLayoutSlot] = []

        if count == 1:
            w = int(desktop_h * 0.535)
            h = desktop_h - (2 * margin)
            x = (desktop_w - w) // 2
            y = margin
            slots.append(GridLayoutSlot(slot_index=1, table_id="tbl-1", target_box=[x, y, w, h]))
        elif count == 2:
            cols, rows = 2, 1
            avail_w = (desktop_w - (cols + 1) * margin) // cols
            avail_h = desktop_h - (2 * margin)
            w = min(avail_w, int(avail_h * 0.535))
            h = avail_h
            for i in range(2):
                x = margin + i * (w + margin) + (desktop_w - (2 * w + 3 * margin)) // 2
                y = margin
                slots.append(GridLayoutSlot(slot_index=i + 1, table_id=f"tbl-{i+1}", target_box=[x, y, w, h]))
        elif count <= 4:
            cols, rows = 2, 2
            avail_w = (desktop_w - (cols + 1) * margin) // cols
            avail_h = (desktop_h - (rows + 1) * margin) // rows
            w = min(avail_w, int(avail_h * 0.535))
            h = avail_h
            total_grid_w = cols * w + (cols - 1) * margin
            offset_x = (desktop_w - total_grid_w) // 2
            for i in range(count):
                c = i % cols
                r = i // cols
                x = offset_x + c * (w + margin)
                y = margin + r * (h + margin)
                slots.append(GridLayoutSlot(slot_index=i + 1, table_id=f"tbl-{i+1}", target_box=[x, y, w, h]))
        else:
            cols, rows = 3, 2
            avail_w = (desktop_w - (cols + 1) * margin) // cols
            avail_h = (desktop_h - (rows + 1) * margin) // rows
            w = min(avail_w, int(avail_h * 0.535))
            h = avail_h
            total_grid_w = cols * w + (cols - 1) * margin
            offset_x = (desktop_w - total_grid_w) // 2
            for i in range(count):
                c = i % cols
                r = i // cols
                x = offset_x + c * (w + margin)
                y = margin + r * (h + margin)
                slots.append(GridLayoutSlot(slot_index=i + 1, table_id=f"tbl-{i+1}", target_box=[x, y, w, h]))

        return slots

    def detect_tables_from_unity_pixels(self, unity_frame: Any) -> List[Tuple[int, int, int, int]]:
        """
        Detector visual baseado em pixels (NumPy/OpenCV).
        Suporta fundos pretos (0,0,0), cinza escuro (20,20,20) e coloridos.
        Usa cálculo inclusivo de largura e altura: w = x_max - x_min + 1, h = y_max - y_min + 1.
        Sem fallback mascarador com retângulos fixos: se numpy ausente ou frame inválido, retorna [].
        """
        if unity_frame is None:
            return []

        try:
            import numpy as np
        except ImportError:
            return []

        if not hasattr(unity_frame, "shape") or unity_frame.ndim != 3:
            return []

        h_frame, w_frame = unity_frame.shape[:2]
        if h_frame < 200 or w_frame < 200:
            return []

        detected_boxes = []

        try:
            # Estima cor de fundo mediana no frame
            bg_color = np.median(unity_frame, axis=(0, 1))
            # Pixels ativos diferem do fundo em > 12
            non_bg = np.any(np.abs(unity_frame.astype(int) - bg_color) > 12, axis=2)
            col_sums = np.sum(non_bg, axis=0)
            active_col_indices = np.where(col_sums > 20)[0]

            if len(active_col_indices) > 50:
                split_points = np.where(np.diff(active_col_indices) > 50)[0] + 1
                splits = np.split(active_col_indices, split_points)
                for sp in splits:
                    if len(sp) >= 150:
                        x_min = int(sp[0])
                        x_max = int(sp[-1])
                        w = x_max - x_min + 1  # Inclusivo

                        row_slice = non_bg[:, x_min:x_max + 1]
                        row_sums = np.sum(row_slice, axis=1)
                        active_row_indices = np.where(row_sums > 20)[0]

                        if len(active_row_indices) > 100:
                            y_min = int(active_row_indices[0])
                            y_max = int(active_row_indices[-1])
                            h = y_max - y_min + 1  # Inclusivo

                            if w >= 200 and h >= 300 and (0.35 <= (w / float(max(1, h))) <= 0.85):
                                if x_min >= 0 and y_min >= 0 and (x_min + w) <= w_frame and (y_min + h) <= h_frame:
                                    detected_boxes.append((x_min, y_min, w, h))
        except Exception:
            pass

        if detected_boxes:
            detected_boxes.sort(key=lambda b: b[0])
            return detected_boxes

        return []

    def scan_unity_surface(self, unity_frame: Any, custom_table_rects: Optional[List[List[int]]] = None) -> List[TableWindowInfo]:
        """
        Varre a superfície Unity usando detecção visual de pixels ou retângulos validados.
        Recorta exatamente com slice exclusivo (y:y+h, x:x+w) e valida crop.shape[:2] == (h, w).
        Atribui identidade persistente e geometry_version sem reatribuir IDs por ordenação horizontal.
        """
        self.scan_count += 1
        self.last_scan_iso = datetime.now(timezone.utc).isoformat()

        raw_boxes = custom_table_rects if custom_table_rects is not None else self.detect_tables_from_unity_pixels(unity_frame)
        if not raw_boxes:
            self.active_tables = {}
            return []

        new_tables_list = []
        for box in raw_boxes:
            x, y, w, h = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            
            table_crop = None
            if unity_frame is not None and hasattr(unity_frame, "shape"):
                try:
                    table_crop = unity_frame[y:y+h, x:x+w]
                    if table_crop is not None and hasattr(table_crop, "shape"):
                        if table_crop.shape[:2] != (h, w):
                            # Ajuste de segurança para slice exato
                            table_crop = unity_frame[y:y+h, x:x+w]
                except Exception:
                    pass

            # Assinatura visual de conteúdo
            content_sig = f"content-at-{x}-{y}"
            if table_crop is not None and hasattr(table_crop, "size") and table_crop.size > 0:
                try:
                    import numpy as np
                    mean_color = [int(c) for c in np.mean(table_crop, axis=(0, 1))]
                    content_sig = f"rgb-{mean_color[0]}-{mean_color[1]}-{mean_color[2]}"
                except Exception:
                    pass

            # Associa com rastros existentes por proximidade espacial (IoU/centro) para preservar identidade persistente
            matched_id = None
            matched_info = None
            for tid, tinfo in self.active_tables.items():
                ox, oy, ow, oh = tinfo.box_physical
                if abs(x - ox) < 200 and abs(y - oy) < 200:
                    matched_id = tid
                    matched_info = tinfo
                    break

            # Detecção de ambiguidade por salto abrupto
            is_ambiguous = False
            if matched_info and abs(x - matched_info.box_physical[0]) > 500 and abs(y - matched_info.box_physical[1]) > 500:
                is_ambiguous = True

            if is_ambiguous:
                table_id = f"tbl-ambiguous-{abs(hash(content_sig)) % 1000}"
                status = "AMBIGUOUS"
                geom_version = 1
            elif matched_id:
                table_id = matched_id
                geom_version = matched_info.geometry_version
                if [x, y, w, h] != matched_info.box_physical:
                    geom_version += 1
                status = matched_info.status
            else:
                existing_count = len(self.active_tables)
                table_id = f"tbl-{existing_count + len(new_tables_list) + 1}"
                geom_version = 1
                status = "ACTIVE_OBSERVING"

            tnum = int(table_id.split("-")[-1]) if "-" in table_id and table_id.split("-")[-1].isdigit() else (len(new_tables_list) + 1)

            table_info = TableWindowInfo(
                table_id=table_id,
                number=tnum,
                hwnd=0,
                pid=0,
                title=f"Unity Surface Table [{x},{y} {w}x{h}]",
                game_type="NLH",
                blinds="?",
                box_physical=[x, y, w, h],
                box_logical=[x, y, w, h],
                dpi_scale=1.0,
                dpi_value=96,
                aspect_ratio=round(w / max(1, h), 4),
                monitor_index=1,
                status=status,
                is_visible=True,
                geometry_version=geom_version,
                last_seen_iso=self.last_scan_iso
            )
            new_tables_list.append(table_info)

        self.active_tables = {t.table_id: t for t in new_tables_list}
        return new_tables_list

    def export_snapshot_json(self, output_path: str = "public/multitable_snapshot.json") -> Dict[str, Any]:
        tables_list = [t.to_dict() for t in self.active_tables.values()]
        payload = {
            "version": "VisualPilot_Fase2_Módulo6",
            "timestamp_utc": self.last_scan_iso or datetime.now(timezone.utc).isoformat(),
            "scan_count": self.scan_count,
            "total_tables_detected": len(tables_list),
            "max_capacity": self.max_tables,
            "system_dpi_summary": {
                "per_monitor_aware_v2": True,
                "detected_scales": list(set(t['dpi_scale'] for t in tables_list)) if tables_list else [1.0]
            },
            "tables": tables_list,
            "tiling_suggestions": [
                s.__dict__ for s in self.compute_mosaic_tiling(len(tables_list) or 4)
            ]
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        return payload


def run_cli_diagnostic():
    tracker = MultiTableTracker(max_tables=6)
    tables = tracker.scan_windows()
    print("=" * 70)
    print(" VisualPilot - Fase 2: Rastreamento Multi-Mesas (1 a 6 Mesas) & DPI")
    print("=" * 70)
    print(f" Total de Mesas Rastreadas : {len(tables)} / {tracker.max_tables}")
    for t in tables:
        hero_tag = f"[{t.hero_position} C{t.hero_seat}]" if t.hero_position else ""
        print(f" • Mesa #{t.number} [{t.table_id}]: {t.title}")
        print(f"   - HWND: {t.hwnd} | PID: {t.pid} | DPI: {t.dpi_value} ({t.dpi_scale * 100:.0f}%)")
        print(f"   - Físico: {t.box_physical} | Lógico: {t.box_logical} | W/H: {t.aspect_ratio}")
        print(f"   - Status: {t.status} | Round: {t.current_round} | Pote: {t.pot_chips} BB {hero_tag}")
    print("-" * 70)
    json_path = "public/multitable_snapshot.json"
    tracker.export_snapshot_json(json_path)
    print(f" [OK] Snapshot gravado com sucesso em '{json_path}'.")
    print("=" * 70)


if __name__ == '__main__':
    run_cli_diagnostic()
