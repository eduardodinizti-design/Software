"""Consolidação concorrente por mesa e geração de mudança relevante."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from threading import Lock
from time import monotonic


class GenerationBatchConsolidator:
    """Publica cartas primeiro e rejeita qualquer resultado de geração antiga."""
    def __init__(self, max_generation_age_sec=20.0, clock=monotonic):
        if max_generation_age_sec <= 0:
            raise ValueError("A validade da geração deve ser positiva.")
        self.max_generation_age_sec = float(max_generation_age_sec)
        self.clock = clock
        self.pending = defaultdict(dict)
        self.latest = {}
        self.lock = Lock()
        self.metrics = dict(registered=0, partial=0, consolidated=0,
                            stale_results=0, duplicate_results=0, expired=0)

    def register_capture(self, table_key, generation, card_regions=(), expect_text=True):
        if not isinstance(table_key, str) or not table_key:
            raise ValueError("table_key obrigatório")
        if not isinstance(generation, int) or generation < 0:
            raise ValueError("generation deve ser inteiro não negativo")
        expected = frozenset(card_regions)
        if not expected and not expect_text:
            raise ValueError("A geração deve possuir pelo menos um trabalho.")
        with self.lock:
            previous = self.latest.get(table_key, -1)
            if generation <= previous:
                raise ValueError("A geração deve crescer monotonicamente por mesa.")
            self.latest[table_key] = generation
            # Uma captura relevante mais nova invalida todas as anteriores.
            self.pending[table_key].clear()
            self.pending[table_key][generation] = dict(
                created_at=self.clock(), expected_cards=expected, cards={},
                text=None, expect_text=bool(expect_text), partial_published=False)
            self.metrics["registered"] += 1

    def _batch(self, table_key, generation):
        if self.latest.get(table_key) != generation:
            self.metrics["stale_results"] += 1
            return None
        batch = self.pending.get(table_key, {}).get(generation)
        if batch is not None and self.clock() - batch['created_at'] > self.max_generation_age_sec:
            del self.pending[table_key][generation]
            self.metrics['expired'] += 1
            return None
        return batch

    def inject_card_result(self, result):
        """Aceita o envelope devolvido por OCRService.read_cards."""
        table_key = result.get("table_key") if isinstance(result, dict) else None
        generation = result.get("generation") if isinstance(result, dict) else None
        region = result.get("region") if isinstance(result, dict) else None
        with self.lock:
            batch = self._batch(table_key, generation)
            if batch is None:
                return []
            if region not in batch["expected_cards"]:
                self.metrics["stale_results"] += 1
                return []
            if region in batch["cards"]:
                self.metrics["duplicate_results"] += 1
                return []
            batch["cards"][region] = deepcopy(result.get("reading"))
            return self._events(table_key, generation, batch)

    def inject_text_result(self, table_key, generation, reading):
        with self.lock:
            batch = self._batch(table_key, generation)
            if batch is None or not batch["expect_text"]:
                return []
            if batch["text"] is not None:
                self.metrics["duplicate_results"] += 1
                return []
            batch["text"] = deepcopy(reading)
            return self._events(table_key, generation, batch)

    def _events(self, table_key, generation, batch):
        events = []
        cards_ready = (batch["expected_cards"] and
                       set(batch["cards"]) == set(batch["expected_cards"]))
        if cards_ready and not batch["partial_published"]:
            batch["partial_published"] = True
            events.append(dict(table_key=table_key, generation=generation,
                               stage="PARTIAL_CARDS",
                               cards=deepcopy(batch["cards"])))
            self.metrics["partial"] += 1
        text_ready = batch["text"] is not None or not batch["expect_text"]
        if (cards_ready or not batch["expected_cards"]) and text_ready:
            events.append(dict(table_key=table_key, generation=generation,
                               stage="CONSOLIDATED", cards=deepcopy(batch["cards"]),
                               text=deepcopy(batch["text"])))
            del self.pending[table_key][generation]
            self.metrics["consolidated"] += 1
        return events

    def cleanup_stale_generations(self, table_key=None):
        now = self.clock()
        expired = []
        with self.lock:
            tables = [table_key] if table_key is not None else list(self.pending)
            for key in tables:
                for generation, batch in list(self.pending.get(key, {}).items()):
                    if now - batch["created_at"] > self.max_generation_age_sec:
                        del self.pending[key][generation]
                        expired.append((key, generation))
            self.metrics["expired"] += len(expired)
        return expired

    def remove_table(self, table_key):
        with self.lock:
            self.pending.pop(table_key, None)
            self.latest.pop(table_key, None)
