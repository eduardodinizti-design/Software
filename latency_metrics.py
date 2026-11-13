"""A0 — instrumentação de latência local do OPERADOR (ponta a ponta).

Mede o tempo real de cada estágio do ciclo de decisão — captura, leitura/
percepção, consulta/cérebro, revalidação, clique — além de IDADE DO SNAPSHOT
(instante da captura -> instante da ação) e LATÊNCIA DE RESPOSTA (vez do hero
detectada -> clique). Agrega p50/p95/p99 por série, em janela rolante limitada.

Serve para MEDIR antes de otimizar (A0 do adendo de antecipação/presets): sem
números reais da máquina, não se afirma ganho de agilidade. PURO: não captura
nem clica; só cronometra o que o chamador reporta. Prazo/relógio ausente =
desconhecido (None), nunca inventado. Dependências: só stdlib.
"""
import math
import time
from collections import deque


def percentiles(values, ps=(50, 95, 99)):
    """p50/p95/p99 por nearest-rank. Lista vazia -> {p: None}."""
    s = sorted(v for v in values if isinstance(v, (int, float)) and math.isfinite(v))
    if not s:
        return {p: None for p in ps}
    out = {}
    for p in ps:
        # multiplica ANTES de dividir p/ evitar drift de FP (0.99*100 -> 99.0000001).
        k = min(len(s), max(1, math.ceil(p * len(s) / 100.0)))
        out[p] = s[k - 1]
    return out


class _SpanCtx:
    __slots__ = ('_m', '_name', '_clock', '_t0')

    def __init__(self, metrics, name, clock):
        self._m, self._name, self._clock = metrics, name, clock

    def __enter__(self):
        self._t0 = self._clock()
        return self

    def __exit__(self, *exc):
        self._m.record(self._name, (self._clock() - self._t0) * 1000.0)
        return False


class LatencyMetrics:
    """Coletor de latências por série (estágio/medida). `span(name)` cronometra um
    bloco; `record(name, ms)` grava direto; `note(name, value)` grava uma medida
    qualquer (ex.: idade do snapshot). `report()`/`format_report()` resumem."""

    def __init__(self, limit=300, clock=time.perf_counter):
        self._clock = clock
        self._limit = int(limit)
        self._series = {}                       # name -> deque[float]
        self._counters = {}                     # name -> int (ex.: missed_deadline)

    def _bucket(self, name):
        d = self._series.get(name)
        if d is None:
            d = self._series[name] = deque(maxlen=self._limit)
        return d

    def record(self, name, ms):
        if isinstance(ms, (int, float)) and math.isfinite(ms) and ms >= 0:
            self._bucket(name).append(float(ms))

    def note(self, name, value):
        """Medida não-duração (idade do snapshot, latência de resposta) em ms."""
        self.record(name, value)

    def span(self, name):
        return _SpanCtx(self, name, self._clock)

    def incr(self, name, by=1):
        self._counters[name] = self._counters.get(name, 0) + int(by)

    def report(self, ps=(50, 95, 99)):
        """{series: {name: {n, p50, p95, p99, max}}, counters: {...}}."""
        series = {}
        for name, values in self._series.items():
            pc = percentiles(values, ps)
            series[name] = dict(n=len(values),
                                **{'p%d_ms' % p: (None if pc[p] is None else round(pc[p], 1)) for p in ps},
                                max_ms=round(max(values), 1) if values else None)
        return dict(series=series, counters=dict(self._counters))

    def format_report(self, title='LATENCIA (A0)'):
        rep = self.report()
        lines = ['== %s ==' % title]
        order = ('captura', 'percepcao', 'cerebro', 'percepcao_cerebro', 'revalidacao',
                 'execucao', 'ciclo', 'idade_snapshot', 'latencia_resposta')
        names = [n for n in order if n in rep['series']] + \
                [n for n in rep['series'] if n not in order]
        for name in names:
            s = rep['series'][name]
            lines.append('  %-20s n=%-4d p50=%-7s p95=%-7s p99=%-7s max=%s'
                         % (name, s['n'], s['p50_ms'], s['p95_ms'], s['p99_ms'], s['max_ms']))
        for name, c in rep['counters'].items():
            lines.append('  [%s] %d' % (name, c))
        if len(lines) == 1:
            lines.append('  (sem amostras)')
        return '\n'.join(lines)
