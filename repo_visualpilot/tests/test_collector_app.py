import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from visualpilot.pppoker.collector_app import Collector, read_settings, save_settings, settings


class CollectorAppTests(unittest.TestCase):
    def test_missing_and_example_config_require_setup_and_save_preserves_other_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'stream_config.ini'
            with self.assertRaisesRegex(ValueError, 'notebook'):
                settings(**read_settings(path))
            path.write_text('[central]\nhost=192.168.0.10\nport=48735\n[member]\nid=INFORME_O_ID_DO_MEMBRO\n[capture]\nmax_tables=6\n')
            with self.assertRaisesRegex(ValueError, 'ID'):
                settings(**read_settings(path))
            saved = save_settings(path, dict(host='192.168.1.50', port='48735', member='PC principal'))
            self.assertEqual(settings(**read_settings(path)), saved)
            self.assertIn('max_tables = 6', path.read_text(encoding='utf-8'))
            self.assertEqual(saved['host'], '192.168.1.50')

    def test_capture_error_reaches_status_file_and_failed_result(self):
        def broken_capture(root, stop, output, **kwargs):
            output.put_nowait(dict(finished=True, error='monitor indisponível'))
        with tempfile.TemporaryDirectory() as folder:
            sender = Mock(session='test', last_error=None)
            sender.membership_snapshot.return_value=(None,0)
            control=Mock();control.exchange.return_value={}
            collector = Collector(folder, observe=broken_capture, sender_factory=Mock(return_value=sender),
                                  control_factory=Mock(return_value=control))
            try:
                collector.start(dict(host='127.0.0.1', port=48735, member='lab'))
                collector.thread.join(3)
                self.assertFalse(collector.thread.is_alive())
                self.assertTrue(collector.failed)
                state = json.loads((Path(folder)/'collector_status.json').read_text(encoding='utf-8'))
                self.assertEqual(state['phase'], 'error')
                self.assertIn('monitor indisponível', state['message'])
            finally:
                collector.close()

    def test_connection_failure_is_reported_before_table_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            sender = Mock(session='test', last_error='Connection refused')
            sender.before_capture.return_value = False
            sender.membership_snapshot.return_value=(None,0)
            control=Mock();control.exchange.return_value={}
            observe = Mock()
            collector = Collector(folder, observe=observe, sender_factory=Mock(return_value=sender),
                                  control_factory=Mock(return_value=control))
            original = collector.update
            def update(**changes):
                original(**changes)
                if changes.get('phase') == 'connection_error':
                    collector.stop.set()
            collector.update = update
            try:
                collector.start(dict(host='127.0.0.1', port=48735, member='lab'))
                collector.thread.join(3)
                observe.assert_not_called()
                self.assertIn('Connection refused', (Path(folder)/'collector.log').read_text(encoding='utf-8'))
                sender.close.assert_called()
            finally:
                collector.close()

    def test_no_table_and_monitor_error_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            collector = Collector(folder)
            collector.sender = Mock(last_error=None)
            try:
                collector.put_nowait(dict(tables=[], reports=[dict(state='captured')]))
                self.assertEqual(collector.snapshot()['phase'], 'no_tables')
                collector.put_nowait(dict(tables=[], reports=[dict(state='error', error='grab failed')]))
                self.assertEqual(collector.snapshot()['phase'], 'capture_error')
                self.assertIn('grab failed', collector.snapshot()['message'])
                collector.put_nowait(dict(tables=[], reports=[], discovery_complete=True))
                self.assertEqual(collector.snapshot()['phase'], 'capture_error')
            finally:
                collector.close()
