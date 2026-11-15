"""New-board identity, lossless delivery and honest precision labels for a batch."""
import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from strategy.batch_archive import (BATCH_TAG,checked_batch_plan,make_batch_plan,make_catalog,
                                    split_archive,verify_remote_parts)
from strategy.batch_jobs import canonical_flop
from strategy.state_contract import StrategyError,digest
from tools.run_hu_reference_pilot import post_progress_status
from strategy.batch_download import check_bundle,receive_archive,load_catalog,download_batch,PLAN_SHA256
from strategy.range_catalog import ComboRange
from strategy.batch_jobs import atomic_json,case_id
from strategy.texassolver_backend import file_hash

HERE=Path(__file__).parent
PLAN=HERE/'docs/software-hu-next16-20261115/plan.json'
GAME=HERE/'docs/software-hu-engine-20261115/game-flop-btn-bb.json'


def example_manifest(plan,case):
    return dict(schema='software.hu-batch-case.v1',plan_sha256=plan['plan_sha256'],
        case_id=case['case_id'],ordinal=case['ordinal'],board=case['board'],native_target_met=True,
        global_gap_bb=.04,archive_sha256='a'*64,lookup_streets=['flop','turn','river'],
        coverage=dict(structurally_complete=True))


class WindowsEvidenceTests(unittest.TestCase):
    def setUp(self):
        from tools.finalize_hu_next16 import checked_windows_results
        self.check=checked_windows_results;self.plan=checked_batch_plan(PLAN);self.native=[];self.rows=[]
        for case in self.plan['cases']:
            c=example_manifest(self.plan,case)
            c.update(file_sha256='1'*64,policy_sha256='2'*64,
                independent_river=dict(runout=['Ts','2h'],joint_private_deals=4,nash_conv_bb=.03))
            self.native.append(c)
            self.rows.append(dict(ordinal=c['ordinal'],status='PASS',platform='Windows-SYNTHETIC-UNIT-CONTROL',
                board=c['board'],file_sha256=c['file_sha256'],policy_sha256=c['policy_sha256'],archive_sha256=c['archive_sha256'],
                native_target_met=True,global_native_gap_bb=c['global_gap_bb'],coverage=c['coverage'],
                source_lookup=dict(probes=dict(flop={},turn={},river={})),exact_suit_alias=dict(probes=dict(flop={},turn={},river={})),
                independent_river=dict(c['independent_river'],exact_enumeration=True),pppoker_windows_validated=False,input_devices_used=False))
        self.catalog=dict(cases=self.native)

    def test_every_windows_proof_must_match_the_published_policy(self):
        self.assertEqual(len(self.check(self.catalog,self.rows)),16)
        self.rows[0]['file_sha256']='0'*64
        with self.assertRaisesRegex(StrategyError,'DOES_NOT_MATCH'):self.check(self.catalog,self.rows)

    def test_missing_duplicate_and_linux_proofs_cannot_be_counted_as_sixteen_windows_models(self):
        with self.assertRaisesRegex(StrategyError,'SIXTEEN_DISTINCT'):self.check(self.catalog,self.rows[:-1])
        with self.assertRaisesRegex(StrategyError,'SIXTEEN_DISTINCT'):self.check(self.catalog,self.rows[:-1]+[self.rows[0]])
        self.rows[0]['platform']='Linux'
        with self.assertRaisesRegex(StrategyError,'DOES_NOT_MATCH'):self.check(self.catalog,self.rows)

    def test_windows_river_must_reproduce_the_independent_linux_calculation(self):
        self.rows[0]['independent_river']['nash_conv_bb']+=.001
        with self.assertRaisesRegex(StrategyError,'RIVER_DIFFERS'):self.check(self.catalog,self.rows)

    def test_lab_evidence_cannot_claim_a_real_pppoker_session(self):
        self.rows[0]['pppoker_windows_validated']=True
        with self.assertRaisesRegex(StrategyError,'DOES_NOT_MATCH'):self.check(self.catalog,self.rows)


class CatalogReadinessTests(unittest.TestCase):
    def test_missing_asset_waits_then_checks_the_full_published_catalog(self):
        from tools.wait_hu_next16_catalog import wait_catalog
        ready=dict(schema='software.hu-batch-catalog.v1',status='COMPLETE',native_target_met_flops=16)
        complete=dict(ready,plan_sha256='control-only',published_new_flops=16)
        missing=HTTPError('https://example.invalid/catalog',404,'Not Found',{},None)
        with (patch('tools.wait_hu_next16_catalog.read_json',side_effect=[missing,ready]),
                patch('tools.wait_hu_next16_catalog.load_catalog',return_value=(complete,'batch-catalog-123.json')) as verify,
                patch('tools.wait_hu_next16_catalog.time.sleep')):
            result=wait_catalog('batch-catalog-123.json',30)
        self.assertEqual(result['status'],'PASS');verify.assert_called_once_with('batch-catalog-123.json')

    def test_a_published_partial_catalog_is_not_mistaken_for_learning_sixteen_models(self):
        from tools.wait_hu_next16_catalog import wait_catalog
        with patch('tools.wait_hu_next16_catalog.read_json',return_value=dict(status='PARTIAL')):
            with self.assertRaisesRegex(StrategyError,'CATALOG_IS_PARTIAL'):wait_catalog('batch-catalog-123.json',30)

    def test_timeout_cannot_report_success(self):
        from tools.wait_hu_next16_catalog import wait_catalog
        with self.assertRaisesRegex(StrategyError,'WAIT_TIMEOUT'):wait_catalog('batch-catalog-123.json',0)


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


class BatchDownloadTests(unittest.TestCase):
    def setUp(self):
        self.plan=checked_batch_plan(PLAN)
        self.manifest=dict(tag=self.plan['tag'],archive_bytes=6,archive_sha256=hashlib.sha256(b'abcdef').hexdigest(),
            parts=[dict(name='p1.zip.part001',bytes=2,sha256=hashlib.sha256(b'ab').hexdigest()),
                   dict(name='p1.zip.part002',bytes=4,sha256=hashlib.sha256(b'cdef').hexdigest())])

    def metadata(self):
        rows=[]
        for c in self.plan['cases']:
            m=example_manifest(self.plan,c)
            m.update(copy.deepcopy(self.manifest),file_sha256='1'*64,policy_sha256='2'*64,policy_file_bytes=100)
            rows.append(m)
        return make_catalog(self.plan,rows)

    def test_consumer_reassembles_the_exact_zip_without_duplicate_part_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('strategy.batch_download.fetch',side_effect=[io.BytesIO(b'ab'),io.BytesIO(b'cdef')]):
                r=receive_archive(self.manifest,Path(tmp)/'model.zip')
            self.assertEqual((Path(tmp)/'model.zip').read_bytes(),b'abcdef')
            self.assertEqual(r['sha256'],self.manifest['archive_sha256'])
            self.assertEqual(len(list(Path(tmp).iterdir())),1)

    def test_corrupt_part_is_retained_for_diagnosis_and_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('strategy.batch_download.fetch',return_value=io.BytesIO(b'xy')):
                with self.assertRaisesRegex(StrategyError,'PART_CHECKSUM'):receive_archive(self.manifest,Path(tmp)/'model.zip')
            self.assertEqual((Path(tmp)/'model.zip').read_bytes(),b'xy')

    def test_whole_archive_checksum_is_checked_in_addition_to_parts(self):
        m=copy.deepcopy(self.manifest);m['archive_sha256']='0'*64
        with tempfile.TemporaryDirectory() as tmp,patch('strategy.batch_download.fetch',side_effect=[io.BytesIO(b'ab'),io.BytesIO(b'cdef')]):
            with self.assertRaisesRegex(StrategyError,'FULL_ARCHIVE_CHECKSUM'):receive_archive(m,Path(tmp)/'model.zip')

    def test_malformed_or_duplicate_part_names_are_rejected(self):
        for name in ('../escape','a\\b','https://example/a'):
            m=copy.deepcopy(self.manifest);m['parts'][0]['name']=name
            with self.assertRaisesRegex(StrategyError,'PART_MANIFEST'):check_bundle(m)
        m=copy.deepcopy(self.manifest);m['parts'][1]['name']=m['parts'][0]['name']
        with self.assertRaisesRegex(StrategyError,'PART_MANIFEST'):check_bundle(m)

    def test_catalog_is_bound_to_the_published_plan_and_all_sixteen_precision_checks(self):
        self.assertEqual(self.plan['plan_sha256'],PLAN_SHA256)
        release=dict(assets=[dict(name='batch-catalog-123.json',state='uploaded',id=10)])
        with patch('strategy.batch_download.read_json',side_effect=[release,self.metadata(),self.plan]):
            c,name=load_catalog();self.assertEqual((len(c['cases']),name),(16,'batch-catalog-123.json'))
        changed=self.metadata();changed['cases'][0]['board']=changed['cases'][1]['board']
        with patch('strategy.batch_download.read_json',side_effect=[release,changed,self.plan]):
            with self.assertRaises(StrategyError):load_catalog()
        changed=self.metadata();changed['cases'][0]['global_gap_bb']=99
        with patch('strategy.batch_download.read_json',side_effect=[release,changed,self.plan]):
            with self.assertRaisesRegex(StrategyError,'TARGET_LABEL'):load_catalog()

    def test_existing_local_folder_is_preserved_before_any_network_request(self):
        with tempfile.TemporaryDirectory() as tmp,patch('strategy.batch_download.load_catalog',side_effect=AssertionError('no network')):
            p=Path(tmp)/'keep.txt';p.write_text('keep')
            with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):download_batch(tmp)
            self.assertEqual(p.read_text(),'keep')

    def test_resume_cannot_claim_an_existing_unmanaged_folder(self):
        with tempfile.TemporaryDirectory() as tmp,patch('strategy.batch_download.load_catalog',return_value=(self.metadata(),'batch-catalog-123.json')):
            p=Path(tmp)/'keep.txt';p.write_text('keep')
            with self.assertRaisesRegex(StrategyError,'MANAGED_BATCH'):download_batch(tmp,include_pilot=False,resume=True)
            self.assertEqual(p.read_text(),'keep')


@unittest.skipUnless(os.environ.get('HU_STREAM_TEST_BINARY') and os.environ.get('HU_STREAM_TEST_RESOURCES'),
                     'Optional separately built native backend required')
class NativeBatchTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);cls.root=Path(cls.temp.name)
        g=json.loads(GAME.read_text());g['root']['stacks']=[1,1]  # Int inputs must survive normalized float state.
        g['ranges']=[ComboRange.from_classes({'QQ':1},'native-transfer-control-only').to_dict(),
                     ComboRange.from_classes({'JJ':1},'native-transfer-control-only').to_dict()]
        atomic_json(cls.root/'game.json',g)
        from tools.run_hu_reference_pilot import main as pilot
        with redirect_stdout(io.StringIO()):
            pilot(['--game',str(cls.root/'game.json'),'--output',str(cls.root/'study'),
                '--binary',os.environ['HU_STREAM_TEST_BINARY'],'--resources',os.environ['HU_STREAM_TEST_RESOURCES'],
                '--iterations','51','--threads','2','--memory-mb','2048'])
        r=json.loads((cls.root/'study/delivery/result.json').read_text())
        archive=cls.root/'study/delivery/btn-bb-As7d2c-nvt-reference.zip'
        bundle=split_archive(archive,cls.root/'parts','control-only',part_bytes=1024**2)
        m=dict(ordinal=1,case_id=case_id(r['board']),board=r['board'],tag=BATCH_TAG,
            policy_sha256=r['policy_sha256'],file_sha256=r['file_sha256'],policy_file_bytes=r['policy_file_bytes'],
            native_target_met=r['native_target_met'],**bundle)
        if not m['native_target_met']:raise AssertionError('Small transfer control did not converge')
        cls.catalog=dict(plan_sha256='NATIVE_CONTROL_ONLY_NOT_A_REAL_NVT_STUDY',cases=[m],context=g['context'],
            root_template=g['root'],_original_plan=dict(game=g))

    def install(self,dest,*,resume=False):
        def fetch_part(url):return (self.root/'parts'/url.rsplit('/',1)[-1]).open('rb')
        with (patch('strategy.batch_download.load_catalog',return_value=(self.catalog,'control-only.json')),
                patch('strategy.batch_download.fetch',side_effect=fetch_part),redirect_stdout(io.StringIO())):
            return download_batch(dest,ordinals=[1],include_pilot=False,resume=resume)

    def test_complete_native_model_is_transferred_queried_and_reused_without_redownload(self):
        dest=self.root/'fresh';receipt=self.install(dest)
        self.assertEqual((receipt['status'],receipt['total_models']),('PASS',1))
        self.assertEqual(set(receipt['policies'][0]['lookup_validation']['probes']),{'flop','turn','river'})
        self.assertTrue(receipt['temporary_transfers_removed']);self.assertFalse(receipt['pppoker_windows_validated'])
        from tools.verify_hu_next16_download import verify_suit_queries
        from strategy.policy_library import PolicyLibrary
        library=PolicyLibrary(receipt['library']);source=library.open(receipt['policies'][0]['board'])
        try:verified=verify_suit_queries(library,source,receipt['policies'][0])
        finally:source.close()
        self.assertEqual(set(verified['probes']),{'flop','turn','river'})
        self.assertFalse(verified['new_solve'])
        with (patch('strategy.batch_download.load_catalog',return_value=(self.catalog,'control-only.json')),
                patch('strategy.batch_download.fetch',side_effect=AssertionError('must reuse existing policy')),
                redirect_stdout(io.StringIO())):
            resumed=download_batch(dest,ordinals=[1],include_pilot=False,resume=True)
        self.assertEqual(resumed['policies'][0]['file_sha256'],receipt['policies'][0]['file_sha256'])

    def test_resume_recovers_a_policy_promoted_before_index_publication(self):
        dest=self.root/'interrupted';receipt=self.install(dest)
        index=dest/'bank/library.json';old=json.loads(index.read_text());path=dest/'bank'/old['entries'][0]['path']
        before=file_hash(path);old['entries']=[];atomic_json(index,old)
        resumed=self.install(dest,resume=True)
        self.assertEqual(resumed['status'],'PASS');self.assertEqual(file_hash(path),before)
        self.assertEqual(resumed['total_models'],receipt['total_models'])

    def test_native_export_closes_monotone_paired_and_two_tone_control_trees(self):
        from strategy.batch_jobs import make_plan,run_queue
        from strategy.native_stream import query_probe
        plan=make_plan(self.root/'game.json',boards=['Qs 7s 2s','Kc Kd 5s','9s 8s 7d'],
            iterations=51,threads=2,memory_mb=2048)
        atomic_json(self.root/'textures-plan.json',plan)
        bank=self.root/'textures-bank'
        with redirect_stdout(io.StringIO()):
            result=run_queue(self.root/'textures-plan.json',bank,os.environ['HU_STREAM_TEST_BINARY'],os.environ['HU_STREAM_TEST_RESOURCES'])
        self.assertEqual(result,dict(COMPLETE=3));self.assertEqual(list((bank/'temporary').iterdir()),[])
        for entry in json.loads((bank/'library.json').read_text())['entries']:
            self.assertTrue(entry['quality']['structurally_complete'])
            self.assertEqual(set(query_probe(bank/entry['path'])['probes']),{'flop','turn','river'})


if __name__=='__main__':unittest.main()
