"""Confirmed reference-hand integration and portable-bank transfer contracts."""
from contextlib import ExitStack
import io
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from strategy.batch_jobs import atomic_json
from strategy.policy_store import CompiledPolicy
from strategy.reference_download import download_reference,safe_extract
from strategy.reference_validation import verify_reference_hand
from strategy.state_contract import StrategyError
from strategy.texassolver_backend import file_hash
from strategy.action_tree import BetMenu,legal_actions
from strategy.ev_evaluator import exact_hu_gap,evaluate_profile
from strategy.range_catalog import ComboRange
from strategy.river_validation import exact_river_review
from strategy.state_contract import BettingState
from test_hu_batches import disk_copy,TURN_POLICY
from test_hu_operational import make_test_policy


class ReferenceHandTests(unittest.TestCase):
    def test_actual_observer_selects_three_streets_and_journal_confirms_showdown(self):
        policy=make_test_policy()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'verification';r=verify_reference_hand(policy,out)
            self.assertEqual(r['event_counts'],dict(action=9,board=2))
            self.assertTrue(r['hero_selected_actions_match_lab_actions'])
            self.assertEqual(r['preflop_witness']['kind'],'OBSERVED_SRP_BASELINE_OPEN_AND_FLOP_CONSERVATION')
            self.assertFalse(r['input_devices_used']);self.assertFalse(r['pppoker_windows_validated'])
            hand=json.loads((out/'hand.json').read_text());self.assertTrue(hand['chain_valid'])
            advice=json.loads((out/'decisions.json').read_text())
            self.assertEqual({a['street'] for a in advice},{'FLOP','TURN','RIVER'})
            self.assertTrue(all(a['recommended']=='bet' for a in advice))

    def test_altered_observer_frequency_cannot_be_reported_as_query_equivalent(self):
        from strategy.policy_observer import PolicyObserver
        original=PolicyObserver.advise
        def wrong(observer,**kwargs):
            result=original(observer,**kwargs)
            if result['status']=='ADVICE':result['candidates'][0]['frequency']+=.01
            return result
        with tempfile.TemporaryDirectory() as tmp,patch.object(PolicyObserver,'advise',wrong):
            out=Path(tmp)/'verification'
            with self.assertRaisesRegex(StrategyError,'FREQUENCY_OR_SIZE_CHANGED'):
                verify_reference_hand(make_test_policy(),out)
            self.assertFalse((out/'result.json').exists())

    def test_existing_local_work_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'keep.txt').write_text('keep')
            with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):
                verify_reference_hand(make_test_policy(),tmp)
            self.assertEqual((Path(tmp)/'keep.txt').read_text(),'keep')


class ReferenceTransferTests(unittest.TestCase):
    def setUp(self):
        self.resources=ExitStack();self.addCleanup(self.resources.close)
        self.root=Path(self.resources.enter_context(tempfile.TemporaryDirectory()))

    def test_zip_parent_traversal_is_rejected_before_extraction(self):
        z=self.root/'bad.zip'
        with zipfile.ZipFile(z,'w') as out:out.writestr('../escaped.txt','invalid')
        with self.assertRaisesRegex(StrategyError,'UNSAFE'):
            safe_extract(z,self.root/'bank')
        self.assertFalse((self.root/'escaped.txt').exists());self.assertFalse((self.root/'bank').exists())

    def test_zip_symlink_is_rejected_before_extraction(self):
        z=self.root/'bad.zip';entry=zipfile.ZipInfo('policies/link')
        entry.create_system=3;entry.external_attr=(stat.S_IFLNK|0o777)<<16
        with zipfile.ZipFile(z,'w') as out:out.writestr(entry,'../../external')
        with self.assertRaisesRegex(StrategyError,'UNSAFE'):
            safe_extract(z,self.root/'bank')
        self.assertFalse((self.root/'bank').exists())

    def test_full_download_checks_archive_and_policy_then_removes_only_its_archive(self):
        source=CompiledPolicy.load(TURN_POLICY);db=self.root/'source.sqlite';result=disk_copy(source,db)
        index=dict(schema='software.hu-policy-library.v1',entries=[dict(board=list(source.root.board[:3]),
            path='policies/model.sqlite',file_sha256=file_hash(db),policy_sha256=result['policy_sha256'])])
        z=self.root/'source.zip'
        with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED) as out:
            out.write(db,'policies/model.sqlite');out.writestr('library.json',json.dumps(index))
        manifest=dict(schema='software.hu-reference-asset.v1',asset='reference.zip',bytes=z.stat().st_size,
            sha256=file_hash(z),file_sha256=file_hash(db),policy_sha256=result['policy_sha256'])
        with patch('strategy.reference_download.fetch',side_effect=lambda url:io.BytesIO(json.dumps(manifest).encode() if url.endswith('.json') else z.read_bytes())):
            receipt=download_reference(self.root/'download')
        self.assertEqual(receipt['status'],'PASS');self.assertTrue(receipt['download_archive_removed'])
        self.assertTrue((self.root/'download/bank/policies/model.sqlite').is_file())
        self.assertFalse((self.root/'download/reference.zip').exists())
        self.assertEqual(file_hash(db),manifest['file_sha256'])

    def test_corrupt_download_is_retained_for_diagnosis_and_never_published(self):
        content=b'corrupt';manifest=dict(schema='software.hu-reference-asset.v1',asset='reference.zip',
            bytes=len(content),sha256='0'*64)
        with patch('strategy.reference_download.fetch',side_effect=lambda url:io.BytesIO(json.dumps(manifest).encode() if url.endswith('.json') else content)):
            with self.assertRaisesRegex(StrategyError,'CHECKSUM'):
                download_reference(self.root/'download')
        self.assertTrue((self.root/'download/reference.zip.part').exists())
        self.assertFalse((self.root/'download/bank').exists())

    def test_existing_user_bank_is_not_overwritten_or_downloaded_again(self):
        with patch('strategy.reference_download.fetch',side_effect=AssertionError('must not download')):
            with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):
                download_reference(self.root)


class IndependentRiverTests(unittest.TestCase):
    def test_best_response_cannot_see_whether_opponent_has_value_or_a_bluff(self):
        root=BettingState(('Kc','8s','3d','Ts','2h'),30,(50,30),committed=(0,20),oop=1,
            acted=(False,True),last_full_raise_bb=20)
        ranges=(ComboRange((('As5s',1),),'hero'),ComboRange((('AhKd',1),('QsJs',1)),'villain'))
        menu=BetMenu((1,),0,False)
        r=exact_river_review(root,ranges,lambda s,h:[.5,.5],lambda s:legal_actions(s,menu))
        # One decision against the whole hidden belief: call EV is 5, not oracle EV 15.
        self.assertAlmostEqual(r['best_response_centered_bb'][0]+15,5)
        row=r['combos']['5sAs']
        self.assertAlmostEqual(row['action_ev_bb_from_current_node']['call:20'],5)
        self.assertAlmostEqual(row['action_ev_bb_from_current_node']['fold:0'],0)

    def test_vectorized_full_tree_matches_independent_scalar_enumeration_with_weighted_blockers(self):
        source=CompiledPolicy.load(Path(__file__).parent/'docs/software-hu-engine-20261115/policy-river-native.json.gz')
        ranges=tuple(ComboRange(tuple((k,w*(i+1)) for i,(k,w) in enumerate(r.weights)),'weighted-test-'+str(n)) for n,r in enumerate(source.ranges))
        r=exact_river_review(source.root,ranges,source.probabilities,source.actions)
        scalar=exact_hu_gap(source.root,ranges,source.menu,source.probabilities,actions_fn=source.actions)
        ev=evaluate_profile(source.root,ranges,source.menu,source.probabilities,actions_fn=source.actions,exact_river=True)
        self.assertAlmostEqual(r['nash_conv_bb'],scalar['nash_conv_bb'],places=10)
        self.assertEqual(r['joint_private_deals'],scalar['joint_private_deals'])
        self.assertAlmostEqual(r['frozen_profile_centered_ev_player0_bb']+source.root.pot_bb/2,ev['root_ev_player0_bb'],places=10)
        for combo,row in r['combos'].items():
            expected=ev['rows'][(source.root.key(),combo)]['action_ev_bb']
            for got,want in zip(row['action_ev_bb_from_current_node'].values(),expected):self.assertAlmostEqual(got,want,places=10)

    def test_invalid_strategy_is_not_silently_normalized_for_validation(self):
        source=CompiledPolicy.load(Path(__file__).parent/'docs/software-hu-engine-20261115/policy-river-native.json.gz')
        with self.assertRaisesRegex(StrategyError,'INVALID_BEHAVIORAL'):
            exact_river_review(source.root,source.ranges,lambda s,h:[float('nan')]*len(source.actions(s)),source.actions)

    def test_budget_exhaustion_does_not_return_a_partial_exact_result(self):
        source=CompiledPolicy.load(Path(__file__).parent/'docs/software-hu-engine-20261115/policy-river-native.json.gz')
        with self.assertRaisesRegex(StrategyError,'NO_PARTIAL_EV'):
            exact_river_review(source.root,source.ranges,source.probabilities,source.actions,max_grid=1)


if __name__=='__main__':unittest.main()
