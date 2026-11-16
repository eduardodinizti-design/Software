"""Loss of any prior bank blocks the next 17; merging must preserve all identities."""
import copy
import json
from pathlib import Path
import unittest

from strategy.batch_jobs import canonical_flop
from strategy.blind_war import SB40_TAG,SB40_NEXT16_TAG,SB40_COMPLETE34_TAG
from strategy.campaign import model_identity
from strategy.campaign_download import PLANS,combine_sb40_thirty_four
from strategy.state_contract import StrategyError,digest
from tools.check_hu_sb40_checkpoint import saved_checkpoint
from tools.prepare_hu_sb40_complete34 import prepare

ROOT=Path(__file__).parent
PRIOR=ROOT/'docs/software-hu-sb40-next16-20261116'
HERE=ROOT/'docs/software-hu-sb40-complete34-20261116'


class SB40Complete34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.delivery=json.loads((PRIOR/'published/entrega-sb40-next16-43796410882-a1.json').read_text())
        cls.publication=json.loads((PRIOR/'publicacao-final-verificada.json').read_text())
        cls.checkpoint=json.loads((HERE/'checkpoint-primeiros17.json').read_text())
        cls.plan=json.loads((HERE/'sb40-complete34-plan.json').read_text())
        oldplan=json.loads((PRIOR/'sb40-next16-plan.json').read_text())
        cls.previous=dict(tag=SB40_NEXT16_TAG,status='COMPLETE',cases=cls.delivery['inventory'],
            _original_plan=oldplan,profile_settings=oldplan['profile_settings'],plan_sha256=oldplan['plan_sha256'],
            context=oldplan['game']['context'],source_catalogs=[dict(tag=SB40_TAG),dict(tag=SB40_NEXT16_TAG)])

    def releases(self):
        values={tag:dict(assets=[]) for tag in (SB40_TAG,SB40_NEXT16_TAG)}
        for case in self.previous['cases']:
            values[case['tag']]['assets'] += [dict(name=p['name'],size=p['bytes'],digest='sha256:'+p['sha256'],state='uploaded') for p in case['parts']]
        for item in self.publication['metadata_hashes']:
            values[item['tag']]['assets'].append(dict(name=item['name'],size=item['bytes'],digest='sha256:'+item['sha256'],state='uploaded'))
        p=self.publication
        values[SB40_NEXT16_TAG]['assets'].append(dict(name=p['source_asset'],size=p['source_bytes'],digest='sha256:'+p['source_sha256'],state='uploaded'))
        return values

    def test_actual_frozen_prior_snapshots_reproduce_the_saved_checkpoint(self):
        self.assertEqual(saved_checkpoint(self.previous,self.delivery,self.publication,self.releases()),self.checkpoint)

    def test_lost_or_changed_archive_part_blocks_the_next_batch(self):
        for mutation in ('delete','size','hash','not-uploaded'):
            releases=self.releases();part=releases[SB40_TAG]['assets'][0]
            if mutation=='delete':releases[SB40_TAG]['assets'].pop(0)
            elif mutation=='size':part['size']+=1
            elif mutation=='hash':part['digest']='sha256:'+'f'*64
            else:part['state']='starter'
            with self.subTest(mutation=mutation),self.assertRaisesRegex(StrategyError,'REMOTE_REFERENCE_PART'):
                saved_checkpoint(self.previous,self.delivery,self.publication,releases)

    def test_missing_evidence_or_source_is_not_a_saved_complete_bank(self):
        for name in (self.publication['source_asset'],self.publication['metadata_hashes'][0]['name']):
            releases=self.releases();releases[SB40_NEXT16_TAG]['assets']=[a for a in releases[SB40_NEXT16_TAG]['assets'] if a['name']!=name]
            with self.subTest(name=name),self.assertRaisesRegex(StrategyError,'DURABLE|EVIDENCE'):
                saved_checkpoint(self.previous,self.delivery,self.publication,releases)

    def test_partial_prior_or_unverified_code_never_authorizes_new_calculations(self):
        for field,value in (('status','FAIL'),('zip_crc_all_entries_valid',False),('complete_models',16)):
            proof=dict(self.publication,**{field:value})
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'SAVED_MODELS'):
                saved_checkpoint(self.previous,self.delivery,proof,self.releases())

    def test_new_plan_reproduces_seventeen_without_repeats_holdouts_or_changed_game(self):
        self.assertEqual(prepare(self.previous,self.checkpoint),self.plan)
        self.assertEqual(self.plan['plan_sha256'],PLANS[SB40_COMPLETE34_TAG][1])
        self.assertEqual(self.plan['model_sha256'],model_identity(self.previous['_original_plan']['game']))
        self.assertEqual(self.plan['game'],self.previous['_original_plan']['game'])
        self.assertEqual(self.plan['settings']['memory_mb'],12288)
        old={canonical_flop(c['board']) for c in self.previous['cases']}
        new={canonical_flop(c['board']) for c in self.plan['cases']}
        self.assertEqual(len(new),17);self.assertEqual(len(old|new),34)
        self.assertFalse(new&{canonical_flop(b) for b in self.plan['preserved_holdout_flops']})

    def test_a_forged_or_wrong_checkpoint_does_not_authorize_a_new_plan(self):
        broken=dict(self.checkpoint,status='FAIL')
        with self.assertRaisesRegex(StrategyError,'CHECKPOINT_REQUIRED'):prepare(self.previous,broken)
        broken=copy.deepcopy(self.checkpoint);broken['preserved_models'][0]['file_sha256']='f'*64
        broken.pop('checkpoint_sha256');broken['checkpoint_sha256']=digest(broken)
        with self.assertRaisesRegex(StrategyError,'MODELS_DIFFER'):prepare(self.previous,broken)

    def new_catalog(self):
        cases=[dict(c,tag=SB40_COMPLETE34_TAG,policy_sha256='c'*64,file_sha256='d'*64) for c in self.plan['cases']]
        return dict(tag=SB40_COMPLETE34_TAG,status='COMPLETE',cases=cases,_original_plan=copy.deepcopy(self.plan),
            profile_settings=copy.deepcopy(self.plan['profile_settings']))

    def test_merge_retains_tags_files_and_original_ordinals_and_appends_seventeen(self):
        result=combine_sb40_thirty_four(self.new_catalog(),self.previous)
        self.assertEqual([c['ordinal'] for c in result['cases']],list(range(1,35)))
        for old,new in zip(self.previous['cases'],result['cases'][:17]):
            self.assertEqual({k:old[k] for k in ('board','policy_sha256','file_sha256','tag','source_ordinal')},
                             {k:new[k] for k in ('board','policy_sha256','file_sha256','tag','source_ordinal')})
        self.assertEqual(result['cases'][17]['source_ordinal'],1)
        self.assertEqual(result['pilot_tag'],SB40_TAG);self.assertFalse(result['suit_aliases_counted_as_models'])

    def test_merge_rejects_changed_old_files_or_strategic_context(self):
        for mutation in ('old-file','stack','menu','range','ante'):
            new=self.new_catalog();old=copy.deepcopy(self.previous)
            if mutation=='old-file':old['cases'][0]['file_sha256']='f'*64
            elif mutation=='stack':new['_original_plan']['game']['root']['stacks'][0]-=1
            elif mutation=='menu':new['_original_plan']['game']['menu']['fractions']=[.5]
            elif mutation=='range':
                w=new['_original_plan']['game']['ranges'][0]['weights'];w[next(iter(w))]=.123
            else:new['profile_settings']['ante_pot_bb']=0
            with self.subTest(mutation=mutation),self.assertRaisesRegex(StrategyError,'IDENTITIES_CHANGED|GEOMETRY_OR_ANTE_CHANGED'):
                combine_sb40_thirty_four(new,old)

    def test_duplicate_suit_alias_is_never_counted_as_model_thirty_four(self):
        new=self.new_catalog();new['cases'][0]['board']=self.previous['cases'][0]['board']
        with self.assertRaisesRegex(StrategyError,'SUIT_DISTINCT'):combine_sb40_thirty_four(new,self.previous)


if __name__=='__main__':unittest.main()
