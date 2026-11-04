"""Conector configurável para ranges e telemetria do Range Coach Pro."""
from __future__ import annotations

from configparser import ConfigParser
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, build_opener


def _secret(value: str) -> str:
    value = value.strip()
    if value.startswith("${") and value.endswith("}"):
        return os.environ.get(value[2:-1], "")
    return value


@dataclass(frozen=True)
class CloudConfig:
    url: str
    api_key: str
    range_table: str = "range_matrices"
    audit_table: str = "visualpilot_audit"
    hand_key_column: str = "hand_key"
    max_buyin_chips: float = 10.0
    timeout_seconds: float = 3.0

    @classmethod
    def from_ini(cls, path="nvt_config.ini"):
        parser = ConfigParser()
        if not parser.read(path, encoding="utf-8"):
            raise FileNotFoundError(path)
        if not parser.has_section("supabase"):
            raise ValueError("Seção [supabase] ausente.")
        return cls(
            url=parser.get("supabase", "url", fallback="").rstrip("/"),
            api_key=_secret(parser.get("supabase", "api_key", fallback="")),
            range_table=parser.get("tables", "ranges", fallback="range_matrices"),
            audit_table=parser.get("tables", "audit", fallback="visualpilot_audit"),
            hand_key_column=parser.get("tables", "hand_key_column", fallback="hand_key"),
            max_buyin_chips=parser.getfloat("pilot", "max_buyin_chips", fallback=10.0),
            timeout_seconds=parser.getfloat("supabase", "timeout_seconds", fallback=3.0),
        )

    def validate(self):
        if not self.url.startswith("https://"):
            raise ValueError("A URL do Supabase deve usar HTTPS.")
        if not self.api_key:
            raise ValueError("Chave do Supabase ausente.")
        for value in (self.range_table, self.audit_table, self.hand_key_column):
            if not value.replace("_", "").isalnum():
                raise ValueError("Nome de tabela ou coluna inválido.")
        if self.timeout_seconds <= 0 or self.max_buyin_chips < 0:
            raise ValueError("Limites de configuração inválidos.")


def canonical_hand(cards):
    if not isinstance(cards, (list, tuple)) or len(cards) != 2:
        raise ValueError("São necessárias exatamente duas cartas.")
    ranks = "23456789TJQKA"
    parsed = []
    for card in cards:
        if not isinstance(card, str) or len(card) != 2 or card[0] not in ranks or card[1] not in "shdc":
            raise ValueError("Carta inválida.")
        parsed.append(card)
    parsed.sort(key=lambda card: ranks.index(card[0]), reverse=True)
    if parsed[0] == parsed[1]:
        raise ValueError("Cartas duplicadas.")
    if parsed[0][0] == parsed[1][0]:
        return parsed[0][0] * 2
    return parsed[0][0] + parsed[1][0] + ("s" if parsed[0][1] == parsed[1][1] else "o")


class RangeCoachConnector:
    """Consulta e audita via PostgREST, sem expor a chave em logs."""
    def __init__(self, config: CloudConfig, opener=None, clock=monotonic):
        config.validate()
        self.config = config
        self.opener = opener or build_opener()
        self.clock = clock
        self.metrics = dict(queries=0, uploads=0, errors=0, last_latency_ms=None)

    @classmethod
    def from_ini(cls, path="nvt_config.ini", **kwargs):
        return cls(CloudConfig.from_ini(path), **kwargs)

    def _request(self, method, table, query=None, payload=None):
        url = f"{self.config.url}/rest/v1/{table}"
        if query:
            url += "?" + urlencode(query, safe="(),.*")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"apikey": self.config.api_key,
                   "Authorization": f"Bearer {self.config.api_key}",
                   "Accept": "application/json"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "Prefer": "return=minimal"})
        request = Request(url, data=body, headers=headers, method=method)
        began = self.clock()
        try:
            response = self.opener.open(request, timeout=self.config.timeout_seconds)
            raw = response.read()
            self.metrics["last_latency_ms"] = round((self.clock()-began)*1000, 3)
            return json.loads(raw.decode("utf-8")) if raw else None
        except Exception:
            self.metrics["errors"] += 1
            raise

    def lookup_range(self, hero_cards, position, tournament_type="freezeout"):
        if not position or str(position).upper() == "UNKNOWN":
            return {"status": "pending", "reason": "Posição do Hero não reconhecida."}
        hand_key = canonical_hand(hero_cards)
        rows = self._request("GET", self.config.range_table, {
            self.config.hand_key_column: f"eq.{hand_key}",
            "position": f"eq.{str(position).upper()}",
            "tournament_type": f"eq.{tournament_type}",
            "select": "action,sizing,strategy_version,confidence",
            "limit": "1",
        }) or []
        self.metrics["queries"] += 1
        if not rows:
            return {"status": "pending", "reason": "Range não encontrado.",
                    "hand_key": hand_key}
        row = rows[0]
        return {"status": "found", "hand_key": hand_key,
                "action": row.get("action"), "sizing": row.get("sizing"),
                "strategy_version": row.get("strategy_version"),
                "confidence": row.get("confidence")}

    def upload_audit(self, snapshot, tournament):
        buyin = float(tournament.get("buyin_chips", -1))
        if not tournament.get("fictional", False):
            return {"status": "rejected", "reason": "Torneio não marcado como fictício."}
        if buyin < 0 or buyin > self.config.max_buyin_chips:
            return {"status": "rejected", "reason": "Buy-in fora do limite do piloto."}
        payload = {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "tournament_id": tournament.get("tournament_id"),
            "buyin_chips": buyin,
            "fictional": True,
            "hand_id": snapshot.get("hand_id"),
            "hero_cards": snapshot.get("hero_cards", []),
            "board_cards": snapshot.get("board_cards", []),
            "theoretical_action": snapshot.get("theoretical_action"),
            "theoretical_sizing": snapshot.get("theoretical_sizing"),
            "observed_profit_chips": snapshot.get("observed_profit_chips"),
            "villain_profile": snapshot.get("villain_profile"),
            "source": "visualpilot_observation_only",
        }
        self._request("POST", self.config.audit_table, payload=payload)
        self.metrics["uploads"] += 1
        return {"status": "uploaded", "payload": payload}

    def diagnose(self):
        try:
            self._request("GET", self.config.range_table,
                          {"select": self.config.hand_key_column, "limit": "1"})
            return {"connected": True, "label": "🟢 Conectado à Nuvem do Time",
                    "latency_ms": self.metrics["last_latency_ms"]}
        except Exception as exc:
            return {"connected": False, "label": "🔴 Nuvem indisponível",
                    "error": type(exc).__name__}
