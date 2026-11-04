"""Fault injection at the final simulated-action boundary, without OS input."""
from copy import deepcopy
import json
import hashlib
import tempfile
import threading
from time import monotonic, sleep
import unittest

from visualpilot.lab.server import LaboratorySession


class Engine:
    def observe(self, index, obscure=False):
        observation = dict(table='laboratory-table', generation=index+1, frame_sha256=hashlib.sha256(b'fixture').hexdigest())
        return dict(index=index, observation=observation,
            reading=dict(hero_buttons=[dict(action='call', amount=2.5, unit='BB')]),
            decision=dict(status='found', observation=deepcopy(observation),
                          options=[dict(action='call', frequency=1, sizing_bb=2.5)])), b'fixture'


class FailureBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.engine = Engine()
        self.session = LaboratorySession(self.temp.name, self.engine)
        self.now = 10.
        self.session.clock = lambda: self.now

    def test_expired_automatic_and_manual_actions_require_new_capture(self):
        for mode, actor in [('automatic', 'engine'), ('manual', 'human')]:
            with self.subTest(mode=mode):
                self.session.control(mode, reset=True)
                event = self.session.observe(0, False)
                self.now += 5.01
                outcome = self.session.apply(event['token'], actor, 'call')
                self.assertEqual(outcome['status'], 'blocked')
                self.assertFalse(self.session.resolved)
                fresh = self.session.observe(0, False)
                self.assertEqual(self.session.apply(fresh['token'], actor, 'call')['status'], 'applied')

    def test_ocr_finishing_after_deadline_never_creates_action_token(self):
        original = self.engine.observe
        def delayed(*args):
            result = original(*args)
            self.now += 6
            return result
        self.engine.observe = delayed
        result = self.session.observe(0, False)
        self.assertEqual(result['status'], 'cancelled')
        self.assertNotIn('token', result)
        self.assertIsNone(self.session.current)

    def test_decision_for_another_frame_is_blocked_at_send_boundary(self):
        original = self.engine.observe
        def conflicting(*args):
            event, image = original(*args)
            event['decision']['observation']['frame_sha256'] = 'b'*64
            return event, image
        self.engine.observe = conflicting
        event = self.session.observe(0, False)
        result = self.session.apply(event['token'])
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(self.session.current[2].actions)

    def test_metadata_cannot_replace_the_actual_evidence_image(self):
        original = self.engine.observe
        def wrong_image(*args):
            event, image = original(*args)
            return event, b'different pixels'
        self.engine.observe = wrong_image
        result = self.session.observe(0, False)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('token', result)
        self.assertIsNone(self.session.current)

    def test_ocr_exception_invalidates_old_token_and_is_recorded_then_recovers(self):
        old = self.session.observe(0, False)
        original = self.engine.observe
        def failed(*args):
            raise RuntimeError('OCR injected failure')
        self.engine.observe = failed
        result = self.session.observe(1, False)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.session.apply(old['token'])['status'], 'blocked')
        self.engine.observe = original
        fresh = self.session.observe(1, False)
        self.assertEqual(self.session.apply(fresh['token'])['status'], 'applied')
        records = [json.loads(line) for line in (self.session.folder/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        errors = [row for row in records if row['kind'] == 'capture_failed']
        self.assertEqual(errors[0]['error_type'], 'RuntimeError')

    def test_concurrent_duplicate_requests_apply_once(self):
        event = self.session.observe(0, False)
        barrier = threading.Barrier(8)
        results = []
        def apply():
            barrier.wait(timeout=3)
            results.append(self.session.apply(event['token']))
        threads = [threading.Thread(target=apply) for _ in range(8)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(row['status'] == 'applied' for row in results), 1)

    def test_pause_before_send_blocks_old_token_and_resume_requires_observation(self):
        event = self.session.observe(0, False)
        self.session.control('paused')
        self.assertEqual(self.session.apply(event['token'])['status'], 'blocked')
        self.session.control('automatic')
        self.assertEqual(self.session.apply(event['token'])['status'], 'blocked')
        fresh = self.session.observe(0, False)
        self.assertEqual(self.session.apply(fresh['token'])['status'], 'applied')

    def test_pause_cancels_queued_ocr_before_it_starts(self):
        entered, release = threading.Event(), threading.Event()
        original = self.engine.observe
        calls = []; results = []
        def slow(*args):
            calls.append(args[0]); entered.set(); release.wait(3)
            return original(*args)
        self.engine.observe = slow
        first = threading.Thread(target=lambda: results.append(self.session.observe(0, False)))
        second = threading.Thread(target=lambda: results.append(self.session.observe(1, False)))
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            second.start()
            deadline = monotonic()+2
            while self.session.capture_revision < 2 and monotonic() < deadline:
                sleep(.01)
            self.assertEqual(self.session.capture_revision, 2)
            self.session.control('paused')
        finally:
            release.set(); first.join(4)
            if second.ident: second.join(4)
        self.assertEqual(calls, [0])
        self.assertEqual([row['status'] for row in results], ['cancelled', 'cancelled'])
        self.assertIsNone(self.session.current)
