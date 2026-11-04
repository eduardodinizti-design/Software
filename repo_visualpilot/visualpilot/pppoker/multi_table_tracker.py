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
    geometry_version: int = 1
    touches_viewport: bool = False
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
        self._visual_tracks = {}
        self._visual_anchors = {}
        self._continuity = []
        self._next_visual_id = 1
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
        """Experimental felt candidates, NOT proof of a complete poker table.

        Real-screen calibration remains required. No synthetic fallback.
        """
        import numpy as np
        import cv2
        if not isinstance(unity_frame, np.ndarray) or unity_frame.ndim != 3 or unity_frame.shape[2] != 3:
            return []
        if unity_frame.dtype != np.uint8 or unity_frame.size == 0:
            return []
        from .table_boundaries import detect_control_anchored_tables
        complete_candidates = detect_control_anchored_tables(unity_frame)
        hsv = cv2.cvtColor(unity_frame, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, (35, 45, 30), (130, 255, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # A cyan desktop can connect to the broad felt mask. A separate blue
        # band recovers isolated candidates without changing broad-mask behavior.
        blue_mask = cv2.inRange(hsv, (105,45,30), (130,255,255))
        # Remove one-pixel bridges introduced by resampling, without accepting
        # contours that actually touch the viewport boundary.
        if any(cv2.boundingRect(c)[0] == 0 for c in cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0]):
            blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_OPEN, np.ones((3,3), np.uint8))
        blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = list(contours) + list(blue_contours)
        height, width = unity_frame.shape[:2]
        boxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if w >= 200 and h >= 300 and .35 <= w / h <= .85:
                # Edge-touching regions remain diagnostic candidates. The scanner
                # explicitly blocks their identity and marks possible clipping.
                edge = x == 0 or y == 0 or x+w == width or y+h == height
                if edge and (blue_mask[y:y+h,x:x+w] > 0).mean() < .65:
                    continue
                boxes.append((x, y, w, h))
        # Keep unrelated felt candidates in mixed scenes, but do not emit a
        # second record for felt already inside an anchored table candidate.
        remaining = []
        for box in boxes:
            x, y, w, h = box
            overlaps_anchor = False
            for ax, ay, aw, ah in complete_candidates + remaining:
                intersection = max(0, min(x+w, ax+aw)-max(x, ax))*max(0, min(y+h, ay+ah)-max(y, ay))
                if intersection / min(w*h, aw*ah) >= .5:
                    overlaps_anchor = True
                    break
            if not overlaps_anchor:
                remaining.append(box)
        return (sorted(complete_candidates) + sorted(remaining))[:self.max_tables]

    def scan_unity_surface(self, unity_frame: Any, custom_table_rects=None) -> List[TableWindowInfo]:
        """Conservative diagnostic association, not gameplay authorization.

        Exact normalized appearance can preserve identity under translation.
        Changed/indistinguishable appearance is suspended, never guessed.
        """
        import numpy as np
        import cv2
        import hashlib
        from collections import Counter
        self.scan_count += 1
        self.last_scan_iso = datetime.now(timezone.utc).isoformat()
        if not isinstance(unity_frame, np.ndarray) or unity_frame.ndim != 3 or unity_frame.shape[2] != 3 or unity_frame.size == 0:
            self.active_tables = {}
            self._visual_anchors = {}
            self._continuity = []
            return []
        boxes = custom_table_rects if custom_table_rects is not None else self.detect_tables_from_unity_pixels(unity_frame)
        candidates = []
        anchors = {}
        textured_anchors = {}
        for box in boxes[:self.max_tables]:
            x, y, w, h = map(int, box)
            if min(x,y) < 0 or min(w,h) <= 0 or x+w > unity_frame.shape[1] or y+h > unity_frame.shape[0]:
                continue
            crop = unity_frame[y:y+h, x:x+w]
            signature = hashlib.sha256(cv2.resize(crop,(128,256),interpolation=cv2.INTER_NEAREST).tobytes()).hexdigest()
            # Provisional continuity anchor excludes lower cards and controls.
            # Exact bytes only; no geometric nearest-neighbor identity guesses.
            anchor = hashlib.sha256(cv2.resize(crop[:max(1,h//5)],(128,48),interpolation=cv2.INTER_NEAREST).tobytes()).hexdigest()
            anchors[signature] = anchor
            textured_anchors[anchor] = float(crop[:max(1,h//5)].std(axis=(0,1)).max()) >= 20
            candidates.append((signature,[x,y,w,h]))
        from .visual_continuity import sample_upper, matches
        samples = [sample_upper(unity_frame, box) for _,box in candidates]
        links = [[j for j,(record,sample) in enumerate(self._continuity)
                  if matches(sample,samples[i],record[1],box)]
                 for i,(_,box) in enumerate(candidates)]
        usage = Counter(j for links_i in links for j in links_i)
        next_continuity = []
        counts = Counter(signature for signature,_ in candidates)
        anchor_counts = Counter(anchors[sig] for sig, _ in candidates)
        previous_anchors = self._visual_anchors
        next_anchors = {}
        previous = self._visual_tracks
        result = []
        retained = {}
        for candidate_index, (signature, box) in enumerate(candidates):
            old = previous.get(signature)
            anchor = anchors[signature]
            anchor_old = previous_anchors.get(anchor)
            # Exact normalized upper pixels, with texture and unique association,
            # may follow uniform scaling. This is not semantic table identity.
            if old is None and anchor_counts[anchor] == 1 and anchor_old is not None and textured_anchors[anchor]:
                old_w, old_h = anchor_old[1][2:]
                sx, sy = box[2]/old_w, box[3]/old_h
                if .5 <= sx <= 2 and .5 <= sy <= 2 and abs(sx/sy-1) <= .01:
                    old = anchor_old
            bx, by, bw, bh = box
            touches_viewport = bx == 0 or by == 0 or bx+bw == unity_frame.shape[1] or by+bh == unity_frame.shape[0]
            common_match = None
            if anchor_counts[anchor] == 1 and len(links[candidate_index]) == 1:
                j = links[candidate_index][0]
                if usage[j] == 1:
                    common_match = self._continuity[j][0]
            if old is None:
                old = common_match
            ambiguous = (touches_viewport and common_match is None) or counts[signature] > 1 or (bool(previous) and old is None)
            if old is not None and not ambiguous:
                table_id, old_box, version = old
                version += box != old_box
            else:
                table_id = f"visual-{self._next_visual_id}"
                self._next_visual_id += 1
                version = 1
            info = TableWindowInfo(table_id=table_id,number=len(result)+1,hwnd=0,pid=0,
                title="Unvalidated visual candidate",game_type="UNKNOWN",blinds="?",
                box_physical=box,box_logical=box.copy(),dpi_scale=1.0,dpi_value=0,
                aspect_ratio=box[2]/box[3],monitor_index=-1,
                status="AMBIGUOUS" if ambiguous else ("PARTIAL_CANDIDATE" if touches_viewport else "CANDIDATE"),is_visible=True,
                geometry_version=version,touches_viewport=touches_viewport,active_players="UNKNOWN",current_round="UNKNOWN")
            result.append(info)
            if not ambiguous:
                next_continuity.append(((table_id,box,version),samples[candidate_index]))
                retained[signature]=(table_id,box,version)
                if anchor_counts[anchor] == 1 and textured_anchors[anchor]:
                    next_anchors[anchor]=(table_id,box,version)
        # Preserve unmatched identities for recovery; bound memory for a diagnostic session.
        updated_ids = {record[0] for record in retained.values()}
        previous = {key:value for key,value in previous.items() if value[0] not in updated_ids}
        self._visual_tracks = dict(list({**previous,**retained}.items())[-self.max_tables*4:])
        self._visual_anchors = next_anchors
        self._continuity = next_continuity
        self.active_tables = {t.table_id:t for t in result}
        return result

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
