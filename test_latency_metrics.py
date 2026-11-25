"""A0 — instrumentação de latência do operador (percentis, janela, spans)."""
import unittest

from latency_metrics import LatencyMetrics, percentiles


class PercentileTests(unittest.TestCase):
    def test_nearest_rank(self):
        p = percentiles(list(range(1, 101)))      # 1..100 (nearest-rank)
        self.assertEqual((p[50], p[95], p[99]), (50, 95, 99))

    def test_empty_is_none(self):
        p = percentiles([])
        self.assertEqual((p[50], p[95], p[99]), (None, None, None))

    def test_ignores_nonfinite(self):
        # nan descartado -> série efetiva [1,3]; p99 (nearest-rank) = 3.0.
        self.assertEqual(percentiles([1.0, float('nan'), 3.0])[99], 3.0)


class LatencyMetricsTests(unittest.TestCase):
    def test_record_and_report(self):
        m = LatencyMetrics()
        for v in (10, 20, 30, 40, 50):
            m.record('captura', v)
        r = m.report()['series']['captura']
        self.assertEqual(r['n'], 5)
        self.assertEqual(r['p50_ms'], 30.0)
        self.assertEqual(r['max_ms'], 50.0)

    def test_negative_and_nan_ignored(self):
        m = LatencyMetrics()
        m.record('x', -5)
        m.record('x', float('inf'))
        m.record('x', 7)
        self.assertEqual(m.report()['series']['x']['n'], 1)

    def test_span_times_with_injected_clock(self):
        ticks = iter([100.0, 100.25])             # 0.25s = 250ms
        m = LatencyMetrics(clock=lambda: next(ticks))
        with m.span('cerebro'):
            pass
        self.assertEqual(m.report()['series']['cerebro']['p50_ms'], 250.0)

    def test_bounded_window(self):
        m = LatencyMetrics(limit=50)
        for v in range(200):
            m.record('ciclo', v)
        self.assertEqual(m.report()['series']['ciclo']['n'], 50)

    def test_counters_and_empty_report(self):
        m = LatencyMetrics()
        m.incr('prazo_perdido')
        m.incr('prazo_perdido')
        self.assertEqual(m.report()['counters']['prazo_perdido'], 2)
        self.assertIn('(sem amostras)', LatencyMetrics().format_report())

    def test_note_snapshot_age(self):
        m = LatencyMetrics()
        m.note('idade_snapshot', 120.0)
        self.assertEqual(m.report()['series']['idade_snapshot']['p95_ms'], 120.0)


if __name__ == '__main__':
    unittest.main()
