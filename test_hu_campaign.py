"""Count only complete distinct models; preserve family and old sixteen contracts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from strategy.batch_jobs import atomic_json,canonical_flop,make_plan
from strategy.campaign import close32_plan,checked_campaign_plan,model_identity
from strategy.batch_archive import make_catalog
from strategy.state_contract import StrategyError

HERE=Path(__file__).parent


class CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game=json.loads((HERE/'docs/software-hu-engine-20261115/game-flop-btn-bb.json').read_text())
        cls.catalog=json.loads((HERE/'docs/software-hu-next16-20261115/published/batch-catalog-43764947533.json').read_text())
        cls.pilot=json.loads((HERE/'docs/software-hu-convergence-20261115/published/result.json').read_text())
        cls.plan=close32_plan(cls.game,cls.catalog,cls.pilot)

    def test_actual_inventory_is_seventeen_and_fifteen_new_models_close_thirty_two(self):
        p=self.plan
        self.assertEqual((len(p['preexisting_models']),len(p['cases']),p['target_total_models']),(17,15,32))
        old={canonical_flop(r['board']) for r in p['preexisting_models']}
        new={canonical_flop(r['board']) for r in p['cases']}
        self.assertEqual(len(old|new),32);self.assertFalse(old&new)
        self.assertFalse(new&{canonical_flop(b) for b in p['preserved_holdout_flops']})
        self.assertEqual(p['game'],self.game)

    def test_nonconverged_pilot_cannot_count_toward_thirty_two(self):
        bad=dict(self.pilot,native_target_met=False)
        with self.assertRaisesRegex(StrategyError,'ONLY_COMPLETE'):close32_plan(self.game,self.catalog,bad)

    def test_changed_campaign_cannot_reuse_the_frozen_plan_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'p.json';atomic_json(path,self.plan);self.assertEqual(checked_campaign_plan(path),self.plan)
            bad=copy.deepcopy(self.plan);bad['cases'][0]['board']=['As','7d','2c'];atomic_json(path,bad)
            with self.assertRaisesRegex(StrategyError,'HASH_MISMATCH'):checked_campaign_plan(path)

    def test_catalog_completion_uses_actual_campaign_length(self):
        rows=[]
        for c in self.plan['cases']:
            rows.append(dict(schema='software.hu-batch-case.v1',plan_sha256=self.plan['plan_sha256'],
                case_id=c['case_id'],board=c['board'],native_target_met=True,global_gap_bb=.04,
                archive_sha256='a'*64,coverage=dict(structurally_complete=True),lookup_streets=['flop','turn','river']))
        c=make_catalog(self.plan,rows)
        self.assertEqual((c['status'],c['planned_new_flops'],c['native_target_met_flops']),('COMPLETE',15,15))
        self.assertEqual(make_catalog(self.plan,rows[:-1])['status'],'PARTIAL')

    def test_family_fingerprint_does_not_change_for_another_flop_but_does_for_a_stack(self):
        game=copy.deepcopy(self.game);game['root']['board']=['Kd','8h','3c']
        self.assertEqual(model_identity(game),model_identity(self.game))
        game['root']['stacks']=[37.5,37.5]
        self.assertNotEqual(model_identity(game),model_identity(self.game))

    def test_real_blind_war_has_small_blind_out_of_position(self):
        g=copy.deepcopy(self.game);g['context']['positions']=['SB','BB'];g['context']['arrival_id']='SB40-control'
        g['root'].update(oop=0,actor=0,pot_bb=5.,stacks=[37.5,37.5])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sb.json';atomic_json(path,g)
            p=make_plan(path,boards=[g['root']['board']])
        self.assertEqual((p['game']['root']['oop'],p['game']['context']['dealt_players']),(0,9))

    def test_progress_tolerates_the_export_removed_during_successful_cleanup(self):
        from tools.run_hu_reference_pilot import progress
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);export=root/'temporary/attempt/native/strategy.jsonl.gz'
            export.parent.mkdir(parents=True);export.write_bytes(b'owned native temporary')
            original=Path.stat;calls=0
            def disappearing(path,*args,**kwargs):
                nonlocal calls
                if path==export:
                    calls+=1
                    if calls==2:export.unlink()
                return original(path,*args,**kwargs)
            with patch.object(Path,'stat',disappearing):progress(root)

    def test_progress_ignores_only_missing_files_and_preserves_other_io_errors(self):
        from tools.run_hu_reference_pilot import progress
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);export=root/'temporary/attempt/native/strategy.jsonl.gz';export.parent.mkdir(parents=True)
            original=Path.stat
            def failed(path,*args,**kwargs):
                if path==export:raise PermissionError('diagnostic permission failure must remain visible')
                return original(path,*args,**kwargs)
            progress(root)  # an already removed export is a normal end-of-worker state
            with patch.object(Path,'stat',failed):
                with self.assertRaises(PermissionError):progress(root)


if __name__=='__main__':unittest.main()
