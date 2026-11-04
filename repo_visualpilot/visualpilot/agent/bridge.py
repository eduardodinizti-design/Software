"""Ponte assíncrona entre eventos de percepção e o Range Coach Pro."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, Future
from copy import deepcopy
from threading import RLock
from time import monotonic


class RangeCoachEventBridge:
    """Executa I/O de estratégia fora das threads críticas de OCR."""

    def __init__(self, strategy, result_sink=lambda event: None, workers=2, clock=monotonic):
        self.clock = clock
        self.lock = RLock()
        self.latest = {}
        self.closed = False
        self.strategy = strategy
        self.result_sink = result_sink
        self.executor = ThreadPoolExecutor(max_workers=workers,
                                           thread_name_prefix="range-coach")

    def advance(self, table, generation, epoch=0):
        with self.lock:
            revision=(epoch,generation)
            if not self.closed and revision>=self.latest.get(table,(-1,-1)):
                self.latest[table] = revision

    def retire_table(self, table):
        with self.lock:
            self.latest.pop(table,None)

    def _done(self, source, identity, future, public_future):
        try:
            result = future.result()
        except Exception as exc:
            result = {"status": "error", "error": type(exc).__name__}
        observation = identity.get('observation') or {}
        with self.lock:
            fresh = False
            if observation:
                revision=(observation.get('epoch'),observation.get('generation'))
                stamp=observation.get('source_observed')
                fresh=(not self.closed and observation.get('transport_verified') is not False and self.latest.get(identity.get('table'))==revision
                       and isinstance(stamp,(int,float)) and 0<=self.clock()-stamp<=5.)
            if not fresh:
                result=dict(status='pending',reason='Resultado descartado: observação ausente, expirada ou substituída.')
            safe_result=dict(result,observation_current=fresh,action_authorized=False)
            try:
                self.result_sink(dict(kind="range_coach_result", source=source,
                                      **identity, result=deepcopy(safe_result), observation_current=fresh,
                                      action_authorized=False))
            finally:
                if not public_future.done():public_future.set_result(safe_result)

    def partial_cards_ready(self, event, context=None):
        context = deepcopy(context or {})
        reading = deepcopy(event.get("reading") or {})
        identity = deepcopy({key: event.get(key) for key in ("table", "generation", "observation")})
        future = self.executor.submit(self.strategy.theoretical_action,
                                      reading, context)
        public_future=Future()
        future.add_done_callback(
            lambda completed: self._done("PARTIAL_CARDS_READY", identity, completed,public_future))
        return public_future

    def snapshot_consolidated(self, snapshot, context=None):
        context = deepcopy(context or {})
        tournament = context.get("tournament") or {}
        identity = deepcopy({key: snapshot.get(key) for key in ("table", "hand_id", "observation")})
        future = self.executor.submit(self.strategy.audit_consolidated,
                                      deepcopy(snapshot), tournament)
        public_future=Future()
        future.add_done_callback(
            lambda completed: self._done("SNAPSHOT_CONSOLIDATED", identity, completed,public_future))
        return public_future

    def close(self):
        with self.lock:self.closed=True
        self.executor.shutdown(wait=True, cancel_futures=True)
