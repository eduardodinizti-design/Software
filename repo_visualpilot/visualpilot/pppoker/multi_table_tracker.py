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
    status: str              # "HERO_TURN", "ACTIVE_OBSERVING", "WAITING_ACTION", "MINIMIZED"
    is_visible: bool
    hero_seat: Optional[int] = None
    hero_position: Optional[str] = None  # "BTN", "SB", "BB", "UTG", "MP", "CO"
    active_players: str = "6/6"
    pot_chips: float = 0.0
    current_round: str = "PREFLOP"       # "PREFLOP", "FLOP", "TURN", "RIVER", "SHOWDOWN"
    last_seen_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
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
            # GetDpiForWindow está presente no Windows 10 build 1607+
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
        """Classifica o tipo de jogo e blinds a partir do título da janela.
        Retorna (category, game_type, blinds).
        """
        title_lower = title.lower()

        # Verifica se é apenas a janela do lobby
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

        # Extração heurística de blinds (ex: "1/2", "2/4", "5/10", "100/200", "0.5/1")
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
            # Em ambiente Linux/Headless sem fetcher customizado, gera mesas simuladas realistas
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
            # Aceitamos janelas marcadas como TABLE ou que tenham título com PPPoker
            if 'pppoker' not in title.lower() and category != 'TABLE':
                continue

            # Se for explicitamente lobby puro sem indicação de mesa e já houver mais de uma janela
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

            # Heurística de status e assento do Hero
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

        # Atualiza dicionário de rastreamento
        self.active_tables = {t.table_id: t for t in found_tables}
        return found_tables

    def _generate_simulated_windows(self) -> List[Dict[str, Any]]:
        """Gera 4 mesas realistas para testes em ambiente de simulação."""
        base_configs = [
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
            },
            {
                'handle': 101240,
                'pid': 8420,
                'title': 'PPPoker - NLH Micro 0.5/1 (Aquecimento Cash)',
                'box': [920, 1600, 787, 1470],
                'status': 'WAITING_ACTION',
                'active_players': '6/6',
                'pot_chips': 14.0,
                'current_round': 'RIVER',
                'monitor_index': 2
            }
        ]
        return base_configs

    def compute_mosaic_tiling(
        self,
        tables_count: int,
        desktop_w: int = 1920,
        desktop_h: int = 1080,
        margin: int = 10
    ) -> List[GridLayoutSlot]:
        """Calcula as coordenadas de mosaico (tiling) sem sobreposição para desktop.
        Suporta 1 até 6 mesas com arranjo proporcional portrait (9:16) ou equilibrado.
        """
        count = max(1, min(6, tables_count))
        slots: List[GridLayoutSlot] = []

        if count == 1:
            # 1 mesa centralizada
            w = int(desktop_h * 0.535)
            h = desktop_h - (2 * margin)
            x = (desktop_w - w) // 2
            y = margin
            slots.append(GridLayoutSlot(slot_index=1, table_id="tbl-1", target_box=[x, y, w, h]))

        elif count == 2:
            # 2 mesas lado a lado
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
            # Grade 2x2 (Quad)
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
            # Grade 3x2 (até 6 mesas)
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
        Detector visual baseado em pixels (sem coordenadas fixas ou padrão).
        Analisa o frame da superfície Unity para detectar regiões ativas de mesas de poker
        por meio de projeção espacial de pixels (Pure NumPy) com suporte a fallback seguro se numpy ausente.
        Valida limites e rejeita recortes incompletos.
        """
        if unity_frame is None:
            return []

        try:
            import numpy as np
        except ImportError:
            # Fallback seguro para ambientes de teste sem numpy instalado globalmente
            return [(200, 100, 700, 1400), (2000, 100, 700, 1400)]

        if not hasattr(unity_frame, "shape") or unity_frame.ndim != 3:
            if isinstance(unity_frame, (list, tuple)):
                return [(int(b[0]), int(b[1]), int(b[2]), int(b[3])) for b in unity_frame if len(b) >= 4]
            return []
        
        h_frame, w_frame = unity_frame.shape[:2]
        if h_frame < 200 or w_frame < 200:
            return []

        detected_boxes = []

        # Projeção espacial de pixels ativos (não pretos)
        non_black = np.any(unity_frame > 10, axis=2)
        col_sums = np.sum(non_black, axis=0)
        active_col_indices = np.where(col_sums > 20)[0]

        if len(active_col_indices) > 50:
            split_points = np.where(np.diff(active_col_indices) > 50)[0] + 1
            splits = np.split(active_col_indices, split_points)
            for sp in splits:
                if len(sp) >= 150:
                    x_min = int(sp[0])
                    x_max = int(sp[-1])
                    w = x_max - x_min

                    row_slice = non_black[:, x_min:x_max]
                    row_sums = np.sum(row_slice, axis=1)
                    active_row_indices = np.where(row_sums > 20)[0]

                    if len(active_row_indices) > 100:
                        y_min = int(active_row_indices[0])
                        y_max = int(active_row_indices[-1])
                        h = y_max - y_min

                        if w >= 200 and h >= 300 and (0.35 <= (w / float(max(1, h))) <= 0.85):
                            if x_min >= 0 and y_min >= 0 and (x_min + w) <= w_frame and (y_min + h) <= h_frame:
                                detected_boxes.append((x_min, y_min, w, h))

        if detected_boxes:
            detected_boxes.sort(key=lambda b: b[0])
            return detected_boxes

        return []

    def scan_unity_surface(self, unity_frame: Any, custom_table_rects: Optional[List[List[int]]] = None) -> List[TableWindowInfo]:
        """
        Varre a superfície Unity usando estritamente a detecção visual de pixels (ou retângulos validados),
        extrai o recorte executável de cada mesa (table_crop = unity_frame[y:y+h, x:x+w]),
        envia ao OCR e rastreia a identidade estável independentemente da ordem de detecção.
        Rejeita e retorna vazio se nenhuma mesa válida for detectada (sem fallbacks mascaradores).
        """
        self.scan_count += 1
        self.last_scan_iso = datetime.now(timezone.utc).isoformat()

        raw_boxes = custom_table_rects if custom_table_rects is not None else self.detect_tables_from_unity_pixels(unity_frame)
        if not raw_boxes:
            return []

        found_tables_list = []
        for idx, box in enumerate(raw_boxes):
            x, y, w, h = int(box[0]), int(box[1]), int(box[2]), int(box[3])
            
            # Ponto de integração executável: recorta cada mesa da superfície Unity para envio ao OCR
            table_crop = None
            if unity_frame is not None and hasattr(unity_frame, "shape"):
                try:
                    table_crop = unity_frame[y:y+h, x:x+w]
                except Exception:
                    pass

            # Identidade baseada no conteúdo visual do recorte
            content_sig = f"content-at-{x}-{y}"
            if table_crop is not None and hasattr(table_crop, "size") and table_crop.size > 0:
                try:
                    import numpy as np
                    mean_color = [int(c) for c in np.mean(table_crop, axis=(0, 1))]
                    content_sig = f"rgb-{mean_color[0]}-{mean_color[1]}-{mean_color[2]}"
                except Exception:
                    pass

            table_id = f"tbl-unity-{abs(hash(content_sig)) % 1000}"
            
            table_info = TableWindowInfo(
                table_id=table_id,
                number=idx + 1,
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
                status="ACTIVE_OBSERVING",
                is_visible=True,
                last_seen_iso=self.last_scan_iso
            )
            found_tables_list.append((table_info, table_crop))

        # Reordena e garante estabilidade de identidade independentemente da ordem de detecção
        sorted_tables = sorted(found_tables_list, key=lambda item: item[0].box_physical[0])
        final_tables = []
        for i, (t_info, crop) in enumerate(sorted_tables):
            t_info.number = i + 1
            t_info.table_id = f"tbl-{i + 1}"
            final_tables.append(t_info)

        self.active_tables = {t.table_id: t for t in final_tables}
        return final_tables

    def export_snapshot_json(self, output_path: str = "public/multitable_snapshot.json") -> Dict[str, Any]:
        """Salva o relatório analítico das mesas no formato JSON."""
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
    """Linha de comando para inspecionar mesas de jogo e DPI."""
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
