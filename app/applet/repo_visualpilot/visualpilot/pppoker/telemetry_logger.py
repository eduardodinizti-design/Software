"""VisualPilot - Módulo de Telemetria e Hand History (TelemetryLogger)"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

class TelemetryLogger:
    def __init__(self, log_dir: str = "logs/sessions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{self.session_id}.jsonl"
        self.events_buffer: List[Dict[str, Any]] = []

    def log_event(self, event_type: str, table_id: str, data: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "table_id": table_id,
            "data": data
        }
        self.events_buffer.append(record)
        try:
            with open(self.session_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "
")
        except Exception:
            pass

    def export_summary(self) -> Dict[str, Any]:
        event_types = {}
        tables_seen = set()
        for ev in self.events_buffer:
            et = ev["event_type"]
            event_types[et] = event_types.get(et, 0) + 1
            tables_seen.add(ev["table_id"])
        return {
            "session_id": self.session_id,
            "total_events": len(self.events_buffer),
            "unique_tables": list(tables_seen),
            "event_breakdown": event_types,
            "log_path": str(self.session_file)
        }
