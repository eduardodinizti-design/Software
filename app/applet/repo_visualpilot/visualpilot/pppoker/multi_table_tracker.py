"""VisualPilot - Módulo 6: Rastreador Dinâmico Multi-Mesas (MultiTableTracker)
Rastreia dinamicamente mesas móveis, redimensionadas e reorganizadas dentro da
superfície visual principal do PPPoker (UnityWndClass, ex: 5760x2160 com coordenadas negativas e DPI 150%).
Mantém identidade estável (track_id, table_id, geometry_version) e estados de ciclo de vida.
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
import logging

logger = logging.getLogger("visualpilot.multitable_tracker")

@dataclass
class TrackedTable:
    track_id: str
    table_id: Optional[str]
    lifecycle_status: str  # "DETECTED", "TRACKING", "OCCLUDED", "LOST", "AMBIGUOUS", "CLOSED"
    bounding_box: List[int]  # [left, top, width, height] em coordenadas da tela/desktop
    client_box: List[int]    # [left, top, width, height] área cliente
    geometry_version: int
    confidence: float
    dpi_scale: float
    monitor_index: int
    game_type: str = "NLH"
    blinds: str = "1/2"
    status: str = "WAITING_ACTION"
    hero_position: str = "BTN"
    pot_chips: float = 0.0
    frame_sequence: int = 0
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen_iso: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    consecutive_misses: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiTableTracker:
    """Rastreador dinâmico multi-mesas para superfícies UnityWndClass de alta resolução."""
    def __init__(self, max_tables: int = 6):
        self.max_tables = max_tables
        self.tracks: Dict[str, TrackedTable] = {}
        self.next_track_seq: int = 1
        self.frame_counter: int = 0
        self.events_log: List[Dict[str, Any]] = []

    def _log_event(self, event_type: str, track_id: str, details: str):
        evt = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "track_id": track_id,
            "details": details
        }
        self.events_log.append(evt)
        if len(self.events_log) > 200:
            self.events_log.pop(0)
        logger.info("[MULTITABLE] [%s] Track %s: %s", event_type, track_id, details)

    def calculate_iou(self, boxA: List[int], boxB: List[int]) -> float:
        """Calcula a Intersection over Union (IoU) entre dois retângulos [x, y, w, h]."""
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
        yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])

        interWidth = max(0, xB - xA)
        interHeight = max(0, yB - yA)
        interArea = interWidth * interHeight

        if interArea == 0:
            return 0.0

        boxAArea = boxA[2] * boxA[3]
        boxBArea = boxB[2] * boxB[3]
        unionArea = float(boxAArea + boxBArea - interArea)
        return interArea / unionArea if unionArea > 0 else 0.0

    def process_frame_detections(self, detected_boxes: List[Dict[str, Any]], dpi_scale: float = 1.0, monitor_index: int = 1) -> List[TrackedTable]:
        """Processa as detecções visuais de um novo frame, atualizando o ciclo de vida e associando rastros."""
        self.frame_counter += 1
        now_iso = datetime.now(timezone.utc).isoformat()

        # Marca todos os rastros existentes como não vistos inicialmente neste frame
        seen_track_ids = set()
        matched_detections = set()

        # Associação IOU entre rastros existentes e novas detecções
        for track_id, track in self.tracks.items():
            best_iou = 0.0
            best_det_idx = -1
            for d_idx, det in enumerate(detected_boxes):
                if d_idx in matched_detections:
                    continue
                iou = self.calculate_iou(track.bounding_box, det["box"])
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = d_idx

            if best_iou >= 0.25 and best_det_idx >= 0:
                # Encontrou associação válida
                det = detected_boxes[best_det_idx]
                matched_detections.add(best_det_idx)
                seen_track_ids.add(track_id)

                old_box = track.bounding_box
                new_box = det["box"]
                moved = (old_box[0] != new_box[0] or old_box[1] != new_box[1])
                resized = (old_box[2] != new_box[2] or old_box[3] != new_box[3])

                track.bounding_box = new_box
                track.client_box = det.get("client_box", new_box)
                track.confidence = det.get("confidence", 0.95)
                track.frame_sequence = self.frame_counter
                track.captured_at = now_iso
                track.last_seen_iso = now_iso
                track.consecutive_misses = 0

                if moved or resized:
                    track.geometry_version += 1
                    if moved:
                        self._log_event("TABLE_MOVED", track_id, f"Mesa movida para {new_box}")
                    if resized:
                        self._log_event("TABLE_RESIZED", track_id, f"Mesa redimensionada para {new_box} (v{track.geometry_version})")

                if track.lifecycle_status in ("LOST", "OCCLUDED"):
                    track.lifecycle_status = "TRACKING"
                    self._log_event("TABLE_REACQUIRED", track_id, "Rastro recuperado com sucesso.")
                elif track.lifecycle_status == "DETECTED":
                    track.lifecycle_status = "TRACKING"

            else:
                # Não foi detectada neste frame
                track.consecutive_misses += 1
                if track.consecutive_misses >= 12:  # ~3 segundos sem ver
                    if track.lifecycle_status != "CLOSED":
                        track.lifecycle_status = "CLOSED"
                        self._log_event("TABLE_CLOSED", track_id, "Mesa fechada por ausência prolongada.")
                elif track.consecutive_misses >= 4:
                    if track.lifecycle_status == "TRACKING":
                        track.lifecycle_status = "LOST"
                        self._log_event("TABLE_LOST", track_id, "Mesa temporariamente perdida.")

        # Adiciona novas detecções que não se associaram a rastros existentes
        for d_idx, det in enumerate(detected_boxes):
            if d_idx in matched_detections:
                continue
            if len(self.tracks) >= self.max_tables:
                break
            
            new_track_id = f"track-{self.next_track_seq:02d}"
            self.next_track_seq += 1
            table_id = det.get("table_id", f"tbl-{self.next_track_seq}")

            new_track = TrackedTable(
                track_id=new_track_id,
                table_id=table_id,
                lifecycle_status="DETECTED",
                bounding_box=det["box"],
                client_box=det.get("client_box", det["box"]),
                geometry_version=1,
                confidence=det.get("confidence", 0.90),
                dpi_scale=dpi_scale,
                monitor_index=monitor_index,
                game_type=det.get("game_type", "NLH"),
                blinds=det.get("blinds", "1/2"),
                frame_sequence=self.frame_counter,
                captured_at=now_iso,
                last_seen_iso=now_iso
            )
            self.tracks[new_track_id] = new_track
            self._log_event("TABLE_DETECTED", new_track_id, f"Nova mesa detectada em {det['box']}")

        # Retorna apenas as mesas ativas / rastreáveis para o runner
        active_list = [t for t in self.tracks.values() if t.lifecycle_status not in ("CLOSED",)]
        return active_list

    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """Retorna sumário de diagnóstico para o painel."""
        return {
            "total_tracks": len(self.tracks),
            "active_tables": len([t for t in self.tracks.values() if t.lifecycle_status in ("TRACKING", "DETECTED")]),
            "tracks": [t.to_dict() for t in self.tracks.values()],
            "recent_events": self.events_log[-20:]
        }
