import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from visualpilot.lab.overnight import atomic_json,manifest,run_process,supervise


class OvernightTests(unittest.TestCase):
    def test_plan_is_bounded_prioritizes_fragile_boards_and_varies_hands(self):
        cases=manifest()
        self.assertEqual(len(cases),10140)
        self.assertEqual(cases[0]['texture'],'paired')
        self.assertEqual(len({tuple(c['hero']) for c in cases}),338)
        self.assertEqual(len(manifest(True)),1)

    def test_expanded_plan_has_unique_cases_and_all_classes(self):
        from collections import Counter
        from visualpilot.agent.connector import canonical_hand
        from visualpilot.lab.overnight import hero_combinations
        hands=hero_combinations()
        counts=Counter(canonical_hand(h) for h in hands)
        self.assertEqual(len(counts),169)
        self.assertEqual(set(counts.values()),{2})
        cases=manifest()
        self.assertEqual(len({(tuple(c['hero']),c['texture'],c['context']) for c in cases}),len(cases))
        self.assertEqual(len({c['texture'] for c in cases[:30]}),6)
        self.assertEqual(len({c['context'] for c in cases[:30]}),5)
        self.assertEqual(manifest(),cases)

    def test_timeout_and_stop_terminate_subprocess(self):
        with tempfile.TemporaryDirectory() as d:
            log=Path(d)/'log';stop=Path(d)/'STOP'
            result=run_process([sys.executable,'-c','import time; time.sleep(5)'],log,.2)
            self.assertEqual(result['status'],'timeout')
            stop.touch()
            result=run_process([sys.executable,'-c','import time; time.sleep(5)'],log,5,stop)
            self.assertEqual(result['status'],'stopped')

    def test_checkpoint_resume_does_not_repeat_completed_case(self):
        with tempfile.TemporaryDirectory() as d:
            def fake(command,log,timeout,stop):
                if '--result' in command:
                    path=Path(command[command.index('--result')+1])
                    atomic_json(path,dict(status='experimental',exact_under_model=True,chosen='check',comparisons={'check':1,'bet:1':.99}))
                return {'status':'ok'}
            with patch('visualpilot.lab.overnight.run_process',side_effect=fake) as mocked:
                result=supervise(d,smoke=True)
                self.assertEqual(result['status'],'completed')
                self.assertEqual(mocked.call_count,5) # baseline + reference + three seeds
            with patch('visualpilot.lab.overnight.run_process',side_effect=AssertionError('must not rerun')):
                self.assertEqual(supervise(d,smoke=True)['status'],'completed')

    def test_source_change_rejected_and_failed_baseline_blocks_work(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('visualpilot.lab.overnight.run_process',return_value={'status':'failed'}):
                result=supervise(d,smoke=True)
                self.assertEqual(result['status'],'baseline_failed_or_stopped');self.assertFalse(result['results'])
            with patch('visualpilot.lab.overnight.fingerprint',return_value='changed'):
                with self.assertRaises(ValueError):supervise(d,smoke=True)

    def test_refines_when_seeds_agree_but_reference_disagrees(self):
        with tempfile.TemporaryDirectory() as d:
            def fake(command,log,timeout,stop):
                if '--result' in command:
                    spec=json.loads(Path(command[command.index('--worker')+1]).read_text())
                    chosen='check' if spec['exact'] or spec['samples']>=12 else 'bet:1'
                    atomic_json(command[command.index('--result')+1],dict(status='experimental',exact_under_model=spec['exact'],chosen=chosen,comparisons={'check':1,'bet:1':0}))
                return {'status':'ok'}
            with patch('visualpilot.lab.overnight.manifest',return_value=manifest(True)),patch('visualpilot.lab.overnight.run_process',side_effect=fake):
                result=supervise(d)
                attempts=result['results']['case-000']['attempts']
                self.assertEqual([a['samples'] for a in attempts],[6,12])
                self.assertTrue(result['results']['case-000']['numerically_accepted'])

    def test_new_hero_respects_cards_and_nvt_context(self):
        from visualpilot.agent.nvt_ranges import NvtRangeBook
        from visualpilot.lab.scenario_matrix import make_case
        book=NvtRangeBook('tests/fixtures/nvt_position_excerpt.json')
        valid=make_case(book,'BTN_vs_BB','paired',hero=['Ah','Qh'])
        self.assertEqual(valid['hero'],['Ah','Qh'])
        with self.assertRaises(ValueError):make_case(book,'BTN_vs_BB','paired',hero=['9h','8h'])

    def test_second_runner_cannot_use_same_checkpoint_folder(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            lock=sqlite3.connect(Path(d)/'runner.lock.sqlite',isolation_level=None)
            lock.execute('BEGIN EXCLUSIVE')
            try:
                with self.assertRaises(RuntimeError):supervise(d,smoke=True)
            finally:lock.rollback();lock.close()
