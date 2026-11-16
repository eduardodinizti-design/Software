"""Only the exact existing SB40 family may expand to seventeen unique flops."""
import copy
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from strategy.batch_jobs import canonical_flop
from strategy.campaign import validate_campaign_plan
from strategy.campaign_download import PLANS,combine_sb40_seventeen,load_family
from strategy.blind_war import SB40_NEXT16_TAG
from strategy.state_contract import StrategyError
from strategy.campaign_resources import resource_profile,effective_settings,checked_resource_profile
from strategy.batch_archive import make_catalog
from strategy.root_policy_review import review_root_policy
from strategy.action_tree import Action
from strategy.range_catalog import ComboRange,combo_key
from strategy.state_contract import BettingState,GameContext
from tools.prepare_hu_sb40_next16 import prepare

ROOT=Path(__file__).parent


class SB40Next16Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d=ROOT/'docs/software-hu-close32-sb40-20261115'
        cls.pilot_plan=json.loads((d/'sb40-plan.json').read_text())
        cls.pilot=json.loads((d/'published/batch-catalog-43777381626.json').read_text())
        cls.plan=json.loads((ROOT/'docs/software-hu-sb40-next16-20261116/sb40-next16-plan.json').read_text())

    def catalogs(self):
        pilot=copy.deepcopy(self.pilot);pilot['_original_plan']=copy.deepcopy(self.pilot_plan)
        pilot['profile_settings']=self.pilot_plan['profile_settings']
        p=self.plan
        rows=[dict(c,tag=SB40_NEXT16_TAG,policy_sha256='a'*64,file_sha256='b'*64) for c in p['cases']]
        new=dict(tag=SB40_NEXT16_TAG,cases=rows,_original_plan=copy.deepcopy(p),
            profile_settings=copy.deepcopy(p['profile_settings']),status='COMPLETE')
        return new,pilot

    def test_frozen_plan_reproduces_sixteen_new_textures_without_touching_ranges(self):
        self.assertEqual(prepare(self.pilot_plan,self.pilot),self.plan)
        self.assertEqual(self.plan['plan_sha256'],PLANS[SB40_NEXT16_TAG][1])
        self.assertEqual(self.plan['game'],self.pilot_plan['game'])
        self.assertEqual(self.plan['profile_settings'],self.pilot_plan['profile_settings'])
        old={canonical_flop(c['board']) for c in self.pilot['cases']}
        new={canonical_flop(c['board']) for c in self.plan['cases']}
        self.assertEqual(len(new|old),17)
        self.assertFalse(new&{canonical_flop(b) for b in self.plan['preserved_holdout_flops']})

    def test_unfinished_pilot_and_changed_frozen_plan_are_rejected(self):
        bad=dict(self.pilot,status='PARTIAL')
        with self.assertRaisesRegex(StrategyError,'COMPLETE_SB40_PILOT_REQUIRED'):prepare(self.pilot_plan,bad)
        bad=copy.deepcopy(self.plan);bad['game']['root']['stacks']=[37.,37.]
        with self.assertRaisesRegex(StrategyError,'HASH_MISMATCH'):validate_campaign_plan(bad)

    def test_merge_preserves_actual_source_identity_and_reindexes_all_seventeen(self):
        new,pilot=self.catalogs();merged=combine_sb40_seventeen(new,pilot)
        self.assertEqual([c['ordinal'] for c in merged['cases']],list(range(1,18)))
        self.assertEqual(merged['cases'][0]['policy_sha256'],self.pilot['cases'][0]['policy_sha256'])
        self.assertEqual(merged['cases'][1]['source_ordinal'],1)
        self.assertEqual(merged['cases'][0]['tag'],self.pilot['tag'])
        self.assertEqual(merged['pilot_tag'],self.pilot['tag'])

    def test_merge_rejects_changed_priors_stack_menu_and_ante(self):
        for kind in ('stack','menu','range','ante'):
            new,pilot=self.catalogs()
            if kind=='stack':new['_original_plan']['game']['root']['stacks'][0]-=1
            elif kind=='menu':new['_original_plan']['game']['menu']['fractions']=[.5]
            elif kind=='range':
                weights=new['_original_plan']['game']['ranges'][0]['weights'];weights[next(iter(weights))]=.123
            else:new['profile_settings']['ante_pot_bb']=0
            with self.subTest(kind=kind),self.assertRaisesRegex(StrategyError,'SB40_PRIORS_MENU_GEOMETRY_OR_ANTE_CHANGED'):
                combine_sb40_seventeen(new,pilot)

    def test_merge_rejects_changed_pilot_and_duplicate_suit_equivalents(self):
        new,pilot=self.catalogs();pilot['cases'][0]['policy_sha256']='0'*64
        with self.assertRaisesRegex(StrategyError,'PILOT_IDENTITY_CHANGED'):combine_sb40_seventeen(new,pilot)
        new,pilot=self.catalogs();new['cases'][0]['board']=pilot['cases'][0]['board']
        with self.assertRaisesRegex(StrategyError,'SUIT_DISTINCT'):combine_sb40_seventeen(new,pilot)

    def test_new_family_installs_seventeen_by_default_but_new_only_selects_the_new_sixteen(self):
        new,pilot=self.catalogs()
        with patch('strategy.campaign_download.load_campaign',side_effect=[(new,'new.json'),(pilot,'old.json')]):
            combined,name=load_family('sb40-next16')
        self.assertEqual((len(combined['cases']),name),(17,'new.json'))
        with patch('strategy.campaign_download.load_campaign',return_value=(new,'new.json')) as load:
            only,_=load_family('sb40-next16',new_only=True)
        self.assertEqual(len(only['cases']),16);load.assert_called_once()

    def test_existing_single_pilot_family_remains_available_without_an_upgrade(self):
        _,pilot=self.catalogs()
        with patch('strategy.campaign_download.load_campaign',return_value=(pilot,'old.json')) as load:
            original,_=load_family('sb40')
        self.assertEqual(len(original['cases']),1);self.assertEqual(load.call_args.args[0],pilot['tag'])

    def test_resource_retry_increases_memory_without_mutating_the_study_or_accuracy(self):
        before=copy.deepcopy(self.plan)
        profile=resource_profile(self.plan,{'memory_mb':12288},'Observed native bad_alloc at 10 GiB')
        settings=effective_settings(self.plan,profile)
        self.assertEqual(settings['memory_mb'],12288)
        for key in ('accuracy_pct','iterations','threads'):self.assertEqual(settings[key],self.plan['settings'][key])
        self.assertEqual(self.plan,before)

    def test_resource_profile_cannot_relax_accuracy_change_iterations_or_claim_another_plan(self):
        for key,value in (('accuracy_pct',1),('iterations',9001),('threads',8),('memory_mb',8192)):
            with self.subTest(key=key),self.assertRaisesRegex(StrategyError,'NO_STRATEGY_OVERRIDES'):
                resource_profile(self.plan,{key:value},'invalid')
        p=resource_profile(self.plan,{'memory_mb':12288},'observed allocation failure')
        p['overrides']['memory_mb']=14336
        with self.assertRaisesRegex(StrategyError,'HASH_OR_CAMPAIGN'):checked_resource_profile(p,self.plan)

    def test_catalog_rejects_a_resource_profile_that_disagrees_with_the_actual_policy_budget(self):
        p=resource_profile(self.plan,{'memory_mb':12288},'observed allocation failure')
        case=copy.deepcopy(self.pilot['cases'][0]);case.update(self.plan['cases'][0])
        case.update(plan_sha256=self.plan['plan_sha256'],tag=SB40_NEXT16_TAG,resource_profile=p,
            effective_execution_settings=effective_settings(self.plan,p))
        case['quality']['settings']['memory_budget_mb']=12288
        self.assertEqual(make_catalog(self.plan,[case])['published_new_flops'],1)
        case['quality']['settings']['memory_budget_mb']=10240
        with self.assertRaisesRegex(StrategyError,'ACTUAL_POLICY_BUDGET'):make_catalog(self.plan,[case])

    def root_example(self):
        ranges=tuple(ComboRange(tuple(sorted((combo_key(k),1.) for k in keys)),source)
            for keys,source in ((('AsAh','KsKh'),'synthetic-sb'),(('AsAd','2c2d'),'synthetic-bb')))
        return SimpleNamespace(root=BettingState(('Kd','8h','3c'),5.,(38.,37.),actor=0,oop=0),
            context=GameContext(('SB','BB'),dealt_players=9,arrival_id='SYNTHETIC_BLOCKER_REVIEW'),ranges=ranges,fingerprint='a'*64,
            actions=lambda state:(Action('check'),Action('bet',1.667)),
            probabilities=lambda state,hand:[0.,1.] if set(hand)=={'As','Ah'} else [1.,0.])

    def test_root_summary_conditions_on_villain_blockers_instead_of_naively_averaging_hands(self):
        policy=self.root_example();before=[r.to_dict() for r in policy.ranges]
        result=review_root_policy(policy)
        self.assertEqual(result['compatible_joint_private_deals'],3)
        self.assertAlmostEqual(result['actions'][0]['frequency'],2/3)
        self.assertAlmostEqual(result['actions'][1]['frequency'],1/3)
        self.assertEqual(result['actor_position'],'SB');self.assertFalse(result['policy_modified'])
        self.assertEqual([r.to_dict() for r in policy.ranges],before)

    def test_root_summary_rejects_invalid_frequencies_instead_of_relabeling_them_as_an_average(self):
        policy=self.root_example();policy.probabilities=lambda state,hand:[-.1,1.1]
        with self.assertRaisesRegex(StrategyError,'INVALID_STORED'):review_root_policy(policy)


if __name__=='__main__':unittest.main()
