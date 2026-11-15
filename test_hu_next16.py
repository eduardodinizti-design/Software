"""New-board identity, lossless delivery and honest precision labels for a batch."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from strategy.batch_archive import (checked_batch_plan,make_batch_plan,make_catalog,
                                    split_archive,verify_remote_parts)
from strategy.batch_jobs import canonical_flop
from strategy.state_contract import StrategyError,digest
from tools.run_hu_reference_pilot import post_progress_status

HERE=Path(__file__).parent
PLAN=HERE/'docs/software-hu-next16-20261115/plan.json'
GAME=HERE/'docs/software-hu-engine-20261115/game-flop-btn-bb.json'


def example_manifest(plan,case):
    return dict(schema='software.hu-batch-case.v1',plan_sha256=plan['plan_sha256'],
        case_id=case['case_id'],ordinal=case['ordinal'],board=case['board'],native_target_met=True,
        global_gap_bb=.04,archive_sha256='a'*64,lookup_streets=['flop','turn','river'],
        coverage=dict(structurally_complete=True))


class Next16PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.plan=checked_batch_plan(PLAN)

    def test_frozen_plan_contains_sixteen_new_models_and_preserves_the_game(self):
        p=self.plan
        self.assertEqual(p,make_batch_plan(GAME))
        self.assertEqual(p['game'],json.loads(GAME.read_text()))
        self.assertEqual(len({canonical_flop(c['board']) for c in p['cases']}),16)
        forbidden={canonical_flop(p['already_solved_board'])}|{canonical_flop(b) for b in p['preserved_holdout_flops']}
        self.assertFalse(forbidden&{canonical_flop(c['board']) for c in p['cases']})
        self.assertEqual((p['workers_per_host'],p['max_parallel_hosts']),(1,8))

    def test_changed_plan_requires_a_new_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'changed.json';p=copy.deepcopy(self.plan);p['settings']['accuracy_pct']=10
            path.write_text(json.dumps(p))
            with self.assertRaisesRegex(StrategyError,'HASH_MISMATCH'):checked_batch_plan(path)

    def test_duplicates_cannot_be_published_even_with_a_matching_plan_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=copy.deepcopy(self.plan);p['cases'][1]=dict(p['cases'][0],ordinal=2)
            p.pop('plan_sha256');p['plan_sha256']=digest(p)
            path=Path(tmp)/'duplicate.json';path.write_text(json.dumps(p))
            with self.assertRaisesRegex(StrategyError,'DISTINCT_FLOPS'):checked_batch_plan(path)

    def test_catalog_counts_actual_complete_and_converged_models(self):
        rows=[example_manifest(self.plan,c) for c in self.plan['cases']]
        r=make_catalog(self.plan,rows)
        self.assertEqual((r['status'],r['native_target_met_flops']),('COMPLETE',16))
        self.assertFalse(r['pppoker_windows_validated'])
        self.assertEqual(make_catalog(self.plan,rows[:-1])['status'],'PARTIAL')
        rows[-1]['native_target_met']=False;rows[-1]['global_gap_bb']=.6
        r=make_catalog(self.plan,rows)
        self.assertEqual((r['published_new_flops'],r['native_target_met_flops'],r['status']),(16,15,'PARTIAL'))

    def test_bad_precision_label_or_incomplete_lookup_cannot_pass_catalog(self):
        m=example_manifest(self.plan,self.plan['cases'][0]);m['global_gap_bb']=.8
        with self.assertRaisesRegex(StrategyError,'TARGET_LABEL'):make_catalog(self.plan,[m])
        m['global_gap_bb']=.04;m['lookup_streets']=['flop','turn']
        with self.assertRaisesRegex(StrategyError,'QUERY_VALIDATED'):make_catalog(self.plan,[m])
        m['lookup_streets']=['flop','turn','river'];m['board']=self.plan['cases'][1]['board']
        with self.assertRaisesRegex(StrategyError,'BOARD_CHANGED'):make_catalog(self.plan,[m])


class MultipartArchiveTests(unittest.TestCase):
    def test_lossless_order_and_hashes_across_part_boundaries(self):
        for size in (1,4,5,6,1024):
            with self.subTest(size=size),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);data=b'abcde'*5;source=root/'source.zip';source.write_bytes(data)
                manifest=split_archive(source,root/'parts','case-01',part_bytes=size)
                parts=manifest['parts'];assembled=b''.join((root/'parts'/p['name']).read_bytes() for p in parts)
                self.assertEqual(assembled,data);self.assertEqual(manifest['archive_bytes'],len(data))
                self.assertEqual(manifest['archive_sha256'],hashlib.sha256(data).hexdigest())
                assets=[]
                for p in parts:
                    self.assertLessEqual(p['bytes'],size)
                    self.assertEqual(p['sha256'],hashlib.sha256((root/'parts'/p['name']).read_bytes()).hexdigest())
                    assets.append(dict(name=p['name'],size=p['bytes'],digest='sha256:'+p['sha256'],state='uploaded'))
                self.assertTrue(verify_remote_parts(manifest,assets))
                assets[0]['digest']='sha256:'+'0'*64
                with self.assertRaisesRegex(StrategyError,'NOT_VERIFIED'):verify_remote_parts(manifest,assets)

    def test_existing_local_work_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'parts').mkdir();keep=root/'parts/keep';keep.write_bytes(b'keep')
            with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):
                split_archive(root/'source.zip',root/'parts','case')
            self.assertEqual(keep.read_bytes(),b'keep')

    def test_invalid_part_size_and_unsafe_path_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(StrategyError,'PART_SIZE'):
                split_archive('unused',Path(tmp)/'out','case',part_bytes=0)
            with self.assertRaisesRegex(StrategyError,'SAFE_ARCHIVE_PREFIX'):
                split_archive('unused',Path(tmp)/'out','../escape')


class ProgressTests(unittest.TestCase):
    def test_status_timeout_cannot_terminate_an_expensive_native_solve(self):
        env=dict(HU_GITHUB_STATUS_CONTEXT='hu-next16/01',GITHUB_REPOSITORY='owner/repo',GITHUB_SHA='abc')
        with patch.dict(os.environ,env),patch('tools.run_hu_reference_pilot.subprocess.run',
                side_effect=subprocess.TimeoutExpired('gh',30)):
            post_progress_status(dict(stage=dict(stage='SOLVING'),last_native_metric=dict(iteration=50)))


if __name__=='__main__':unittest.main()
