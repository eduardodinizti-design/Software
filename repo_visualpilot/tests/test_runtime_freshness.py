"""Deterministic fault injection at publication, not only helper-level tests."""
from concurrent.futures import Future
import json
from pathlib import Path
from queue import Queue
import tempfile
import unittest
from unittest.mock import patch
import numpy as np

from visualpilot.pppoker.observer.runtime import Mailbox, PerceptionSession
from visualpilot.pppoker.scheduler import GenerationBatchConsolidator
from visualpilot.viz.session import RemoteSession
from visualpilot.pppoker.observer.freshness import frame_sha256
from observation_assertions import assert_partial_trace


class ImmediateExecutor:
    def __init__(self, **kwargs): pass
    def submit(self, function, *args):
        future = Future()
        try: future.set_result(function(*args))
        except Exception as exc: future.set_exception(exc)
        return future
    def shutdown(self, **kwargs): pass


class RuntimeFreshnessTests(unittest.TestCase):
    def exercise(self, fault):
        now = [100.0]
        image = np.zeros((200,120,3), dtype=np.uint8)
        changed = image.copy(); changed[150:190,65:100] = 255
        output = Queue(200)
        def capture_item(sequence):
            item=dict(table_key='one',number=1,sequence=sequence,collector_session='session')
            if fault=='text_expired_after_partial':
                item['transport']=dict(protocol=2,verified=True,not_before_monotonic=now[0],
                                       age_upper_bound_at_receive=0.)
            return item
        class Stop:
            stopped = False
            loops = 0
            def is_set(self): return self.stopped
            def set(self): self.stopped = True
            def wait(self, seconds):
                self.loops += 1; now[0] += seconds
                if fault == 'cache_revalidation':
                    session.frames.put(dict(table_key='one',number=1),image)
                if self.loops > 45: self.set()
        stop = Stop()
        class Service:
            calls = 0
            def __init__(self, **kwargs): pass
            def start(self): pass
            def close(self): pass
            def read_cards(self, key, generation, region, rgb, stop):
                if generation == 1 and region == 'board_river':
                    if fault == 'pending_changed':
                        session.frames.put(dict(table_key='one',number=1), changed)
                    elif fault=='transport_plus_ocr':
                        now[0]+=1.2
                    elif fault in ('expired', 'identical_refresh'):
                        now[0] += 6
                        if fault == 'identical_refresh':
                            session.frames.put(dict(table_key='one',number=1),image)
                if fault=='wrong_identity' and region=='hero_cards':key='other-table'
                cards = ['As','Ks'] if region == 'hero_cards' else []
                return dict(table_key=key,generation=generation,region=region,
                            reading=dict(status='SUCCESS' if cards else 'PENDING',
                                         cards=[dict(card=c,confidence=.99) for c in cards]))
            def call(self, kind, rgb, stop):
                self.calls += 1
                if fault=='text_expired_after_partial' and self.calls==1:
                    now[0] += 6
                    session.frames.put(capture_item(2),image)
                if fault=='processing_time':now[0]+=.5
                return dict(status='read',hero=['As','Ks'],board=[],street='preflop',hand_id='hand-1')
        from visualpilot.pppoker.observer.validation import confirmations as real_confirmations
        injected=[False]
        def prepare_confirmations(reading, prior):
            if fault in ('remote_retired','remote_readded') and not injected[0]:
                injected[0]=True
                session.frames.set_remote_active(set())
                if fault=='remote_readded':session.frames.set_remote_active({'one'})
            if fault=='during_publication' and not injected[0]:
                injected[0]=True
                session.frames.put(dict(table_key='one',number=1),changed)
            return real_confirmations(reading,prior)
        with tempfile.TemporaryDirectory() as root, \
             patch('visualpilot.pppoker.observer.runtime.confirmations',side_effect=prepare_confirmations), \
             patch('visualpilot.pppoker.observer.runtime.OCRService',Service), \
             patch('visualpilot.pppoker.observer.runtime.ThreadPoolExecutor',ImmediateExecutor), \
             patch('visualpilot.pppoker.observer.runtime.monotonic',side_effect=lambda: now[0]):
            session = PerceptionSession(root,stop,output,workers=1)
            session.frames = Mailbox(clock=lambda:now[0])
            item=capture_item(1)
            if fault in ('remote_retired','remote_readded'):
                item['remote_epoch']=session.frames.set_remote_active({'one'})['one']
            if fault=='transport_plus_ocr':
                item['transport']=dict(protocol=2,verified=True,not_before_monotonic=96.,age_upper_bound_at_receive=4.)
            session.frames.put(item,image)
            session.run(capture=False)
            events = list(output.queue)
            journal = next(Path(root).rglob('percepcao.jsonl'))
            records = [json.loads(line) for line in journal.read_text().splitlines()]
            rejects = journal.with_name('rejeicoes.jsonl')
            rejected = [json.loads(line) for line in rejects.read_text().splitlines()] if rejects.exists() else []
        self.assertIsNone(events[-1].get('error'),events[-1])
        return events, records, rejected

    def test_remote_retirement_blocks_result_at_publication_boundary(self):
        for fault in ('remote_retired','remote_readded'):
            with self.subTest(fault=fault):
                events,records,rejected=self.exercise(fault)
                self.assertFalse(any(e['kind']=='reading' for e in events))
                self.assertTrue(any(r['reason']=='retired_remote_table' for r in rejected),rejected)

    def test_pending_new_frame_blocks_partial_before_generation_advances(self):
        events, _, _ = self.exercise('pending_changed')
        partials = [e for e in events if e['kind']=='partial_cards']
        self.assertTrue(any(e['generation']==2 for e in partials))
        self.assertFalse(any(e['generation']==1 for e in partials),partials)

    def test_expired_partial_never_reaches_consumers(self):
        events, _, _ = self.exercise('expired')
        self.assertFalse(any(e['kind']=='partial_cards' for e in events),events)

    def test_identical_new_frame_cannot_renew_inflight_ocr_age(self):
        events, _, _ = self.exercise('identical_refresh')
        self.assertFalse(any(e['kind']=='partial_cards' and e['generation']==1 for e in events),events)

    def test_source_and_processing_timing_are_traceable(self):
        events, records, _ = self.exercise('none')
        readings = [e for e in events if e['kind']=='reading']
        self.assertTrue(readings)
        for event in readings:
            self.assertEqual(event['observation']['table'],'one')
            self.assertEqual(event['observation']['generation'],1)
            self.assertEqual(len(event['observation']['frame_sha256']),64)
            self.assertEqual(event['observation']['source_observed'],100.)
            self.assertIn('processing_seconds',event['timing'])
            self.assertIn('queue_seconds',event['timing'])
            self.assertFalse(event['action_authorized'])
        self.assertTrue(all('observation' in row for row in records))

    def test_rejections_have_reason_and_frame_identity(self):
        _, _, rejected = self.exercise('expired')
        self.assertTrue(rejected)
        self.assertTrue(any(row['reason']=='expired_source' for row in rejected))
        self.assertTrue(all(len(row['observation']['frame_sha256'])==64 for row in rejected))

    def test_cache_limit_really_schedules_new_ocr(self):
        events, _, _ = self.exercise('cache_revalidation')
        self.assertGreaterEqual(events[-1]['metrics']['ocr'],2)
        self.assertGreaterEqual(events[-1]['metrics'].get('cache_revalidations',0),1)

    def test_wrong_worker_identity_is_rejected(self):
        events, _, rejected = self.exercise('wrong_identity')
        self.assertFalse(any(e['kind']=='partial_cards' for e in events))
        self.assertTrue(any(r['reason']=='mismatched_result_identity' for r in rejected))

    def test_actual_processing_time_is_separate_from_image_age(self):
        events, records, _ = self.exercise('processing_time')
        reading=next(e for e in events if e['kind']=='reading')
        self.assertAlmostEqual(reading['timing']['processing_seconds'],.5)
        self.assertGreater(reading['latency'],reading['timing']['processing_seconds'])
        entry=next(row for row in records if row.get('visual_evidence',{}).get('status')=='saved')
        self.assertEqual(entry['observation']['frame_sha256'],entry['visual_evidence']['sha256_pixels'])

    def test_ingress_during_publication_preparation_blocks_old_full_result(self):
        events, _, rejected=self.exercise('during_publication')
        self.assertFalse(any(e['kind']=='reading' and e['generation']==1 for e in events))
        self.assertTrue(any(e['kind']=='reading' and e['generation']==2 for e in events))
        self.assertTrue(any(r['reason']=='newer_frame_pending' for r in rejected))

    def test_transport_and_ocr_share_one_deadline(self):
        events,_,rejected=self.exercise('transport_plus_ocr')
        self.assertFalse(any(e['kind'] in ('reading','partial_cards') for e in events),events)
        self.assertTrue(any(r['reason']=='expired_source' for r in rejected))
        self.assertTrue(any(r['source_age_seconds']>5. for r in rejected))

    def test_slow_text_retries_from_new_capture_without_replaying_expired_result(self):
        events,records,rejected=self.exercise('text_expired_after_partial')
        partials=[e for e in events if e['kind']=='partial_cards']
        complete=[e for e in events if e['kind']=='reading']
        self.assertEqual([e['generation'] for e in partials],[1,2])
        self.assertEqual([e['observation']['transport_sequence'] for e in partials],[1,2])
        self.assertEqual([e['generation'] for e in complete],[2])
        first,second=[e['observation'] for e in partials]
        self.assertEqual(first['frame_sha256'],second['frame_sha256'])
        self.assertGreater(second['source_observed'],first['source_observed']+5.)
        for event in partials+complete:
            self.assertTrue(event['observation']['transport_verified'])
            self.assertLessEqual(event['latency'],5.)
            self.assertFalse(event['action_authorized'])
        self.assertTrue(any(r['job_kind']=='text' and r['reason']=='expired_source'
                            and r['observation']['generation']==1 for r in rejected))
        self.assertEqual([r['generation'] for r in records if r.get('event')=='PARTIAL_CARDS_READY'],[1,2])
        expected=dict(phase=0,hero=['As','Ks'],board=[],session='session',
                      frame_sha256=frame_sha256(np.zeros((200,120,3),dtype=np.uint8)))
        captures={('one',1):expected,('one',2):expected}
        assert_partial_trace(self,records,captures,1)
        from copy import deepcopy
        partial_records=[r for r in records if r.get('event')=='PARTIAL_CARDS_READY']
        with self.assertRaises(AssertionError):
            assert_partial_trace(self,partial_records+[partial_records[-1]],captures,1)
        for field,value in [('transport_sequence',1),('frame_sha256','wrong-frame'),
                            ('transport_verified',False),('collector_session','old-session')]:
            with self.subTest(invalid_trace=field),self.assertRaises(AssertionError):
                corrupted=deepcopy(partial_records)
                corrupted[-1]['observation'][field]=value
                assert_partial_trace(self,corrupted,captures,1)
        with self.assertRaises(AssertionError):
            expired=deepcopy(partial_records)
            expired[-1]['timing']['source_age_seconds']=5.01
            assert_partial_trace(self,expired,captures,1)


class PublicationBoundaryTests(unittest.TestCase):
    def test_scheduler_checks_expiry_when_result_arrives_without_cleanup(self):
        now = [0.]
        scheduler = GenerationBatchConsolidator(5,clock=lambda:now[0])
        scheduler.register_capture('one',1,['hero_cards'])
        now[0] = 6.
        self.assertEqual(scheduler.inject_card_result(dict(table_key='one',generation=1,
            region='hero_cards',reading=dict(status='SUCCESS',cards=['As','Ks']))),[])

    def test_panel_does_not_replace_new_reading_with_delayed_old_event(self):
        session = RemoteSession()
        for generation, observed, hero in [(2,20.,['Qs','Js']),(1,19.,['As','Ks'])]:
            session.output.put(dict(kind='reading',table='one',generation=generation,
                                   observed=observed,reading=dict(hero=hero)))
        with patch('visualpilot.viz.session.monotonic',return_value=21.): session.poll()
        self.assertEqual(session.tables['one']['reading']['hero'],['Qs','Js'])

    def test_new_image_invalidates_display_and_late_partial_cannot_restore_it(self):
        session=RemoteSession()
        for event in [
            dict(kind='reading',generation=1,observed=10.,reading=dict(hero=['As','Ks'])),
            dict(kind='reading_invalidated',generation=2,observed=11.,reading=dict(hero=[],status='pending')),
            dict(kind='partial_cards',generation=1,observed=12.,reading=dict(hero=['As','Ks']))]:
            session.output.put(dict(event,table='one'))
        with patch('visualpilot.viz.session.monotonic',return_value=12.):session.poll()
        self.assertEqual(session.tables['one']['reading']['hero'],[])
        self.assertEqual(session.tables['one']['generation'],2)

    def test_partial_cannot_downgrade_consolidated_same_source(self):
        session=RemoteSession()
        for kind, hero in [('reading',['Qs','Js']),('partial_cards',['As','Ks'])]:
            session.output.put(dict(kind=kind,table='one',generation=1,observed=10.,reading=dict(hero=hero)))
        with patch('visualpilot.viz.session.monotonic',return_value=11.):session.poll()
        self.assertEqual(session.tables['one']['reading']['hero'],['Qs','Js'])

    def test_monitor_cancels_old_button_interval_on_new_frame(self):
        from visualpilot.viz.monitor import LiveMonitor
        monitor=LiveMonitor(clock=lambda:11.)
        image=np.zeros((40,30,3),dtype=np.uint8)
        monitor.frame('one',1,image)
        monitor.observe(dict(table='one',observed=10.,reading=dict(status='read',hero=['As','Ks'],actions=['call'])),image)
        self.assertIsNotNone(monitor.snapshot()['one']['button_seconds'])
        monitor.invalidate('one','new_generation')
        state=monitor.snapshot()['one']
        self.assertIsNone(state['button_seconds'])
        self.assertEqual(state['reading']['hero'],[])


class StrategyFreshnessTests(unittest.TestCase):
    def test_delayed_strategy_cannot_restore_old_generation_or_expired_frame(self):
        import threading
        from visualpilot.agent.bridge import RangeCoachEventBridge
        for fault in ('generation','expiration','retired'):
            with self.subTest(fault=fault):
                release=threading.Event();entered=threading.Event();done=threading.Event()
                now=[100.];results=[]
                class Strategy:
                    def theoretical_action(self,reading,context):
                        entered.set();release.wait(2)
                        return dict(status='found',action='CALL')
                def sink(event):results.append(event);done.set()
                bridge=RangeCoachEventBridge(Strategy(),sink,workers=1,clock=lambda:now[0])
                try:
                    bridge.advance('one',1)
                    future=bridge.partial_cards_ready(dict(table='one',generation=1,
                        observation=dict(epoch=0,generation=1,source_observed=100.),reading={}))
                    self.assertTrue(entered.wait(1))
                    if fault=='generation':bridge.advance('one',2)
                    elif fault=='expiration':now[0]=106.
                    else:bridge.retire_table('one')
                    release.set();self.assertTrue(done.wait(1))
                    self.assertFalse(results[0]['observation_current'])
                    self.assertFalse(results[0]['action_authorized'])
                    self.assertNotIn('action',results[0]['result'])
                    self.assertNotIn('action',future.result(timeout=1))
                finally:release.set();bridge.close()

    def test_fresh_advisory_retains_source_but_never_authorizes_action(self):
        import threading
        from visualpilot.agent.bridge import RangeCoachEventBridge
        results=[];done=threading.Event()
        class Strategy:
            def theoretical_action(self,reading,context):return dict(status='found',action='CALL')
        def sink(event):results.append(event);done.set()
        bridge=RangeCoachEventBridge(Strategy(),sink,clock=lambda:101.)
        try:
            bridge.advance('one',2)
            bridge.partial_cards_ready(dict(table='one',generation=2,
                observation=dict(epoch=0,generation=2,source_observed=100.),reading={}))
            self.assertTrue(done.wait(1))
            self.assertTrue(results[0]['observation_current'])
            self.assertEqual(results[0]['result']['action'],'CALL')
            self.assertFalse(results[0]['action_authorized'])
        finally:bridge.close()

if __name__ == '__main__': unittest.main()
