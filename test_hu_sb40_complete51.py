"""Conditional third batch: synthetic metadata fixtures are never solved models."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from strategy.batch_jobs import canonical_flop
from strategy.blind_war import SB40_TAG,SB40_COMPLETE34_TAG,SB40_COMPLETE51_TAG
from strategy.campaign import model_identity
from strategy.batch_archive import make_catalog
from strategy.batch_download import ASSET_BASE
from strategy.campaign_download import load_campaign
from strategy.campaign_download import combine_sb40_fifty_one
from strategy.sb40_progression import (PARENT_CATALOG,PARENT_WINDOWS,PrerequisitePending,
    checkpoint34,load_parent34,make_intent,make_plan51,read_intent,validate_derived_plan51)
from strategy.state_contract import StrategyError,digest
from tools.prepare_hu_sb40_complete51 import initialize
from tools.finalize_hu_sb40_complete51 import main as finalize51
from tools.verify_hu_sb40_complete51_publication import main as verify51

ROOT=Path(__file__).parent


def synthetic_parent():
    """Real old receipt shapes with clearly synthetic new IDs; no policy or EV claims."""
    d=ROOT/'docs/software-hu-sb40-next16-20261116'
    old=json.loads((d/'published/entrega-sb40-next16-43796410882-a1.json').read_text())
    parent=json.loads((ROOT/'docs/software-hu-sb40-complete34-20261116/sb40-complete34-plan.json').read_text())
    first=json.loads((ROOT/'docs/software-hu-sb40-complete34-20261116/checkpoint-primeiros17.json').read_text())
    cases=copy.deepcopy(old['inventory']);rows=[]
    for i,planned in enumerate(parent['cases']):
        case=copy.deepcopy(old['inventory'][1+i%16]);row=copy.deepcopy(old['windows_cases'][i%16])
        policy=digest(['SYNTHETIC_METADATA_NOT_A_SOLVED_POLICY',i]);file=digest(['SYNTHETIC_FILE_NOT_DOWNLOADED',i])
        case.update(ordinal=18+i,source_ordinal=i+1,board=planned['board'],tag=SB40_COMPLETE34_TAG,policy_sha256=policy,file_sha256=file)
        for j,part in enumerate(case['parts']):part['name']=f'SYNTHETIC-parent-{i:02d}-{j:02d}.part'
        row.update(ordinal=i+1,board=planned['board'],policy_sha256=policy,file_sha256=file)
        row['confirmed_hand']['policy_sha256']=policy
        cases.append(case);rows.append(row)
    full=dict(tag=SB40_COMPLETE34_TAG,status='COMPLETE',plan_sha256=parent['plan_sha256'],
        cases=cases,_original_plan=parent,profile_settings=parent['profile_settings'],context=parent['game']['context'],
        source_catalogs=[dict(tag=c['tag']) for c in cases[:1]+cases[1:2]+cases[17:18]])
    delivery=dict(status='PASS',complete_distinct_flop_models=34,new_complete_flop_models=17,new_windows_policy_pass=17,
        new_confirmed_synthetic_hands=17,new_json_street_queries=51,new_exact_suit_street_queries=51,
        all_new_workers_exited=True,all_new_native_temporaries_removed=True,pppoker_windows_validated=False,
        context=parent['game']['context'],profile_settings=parent['profile_settings'],inventory=cases,windows_cases=rows,
        total_policy_file_bytes=sum(c['policy_file_bytes'] for c in cases),
        total_public_nodes=sum(c['coverage']['public_nodes'] for c in cases),prerequisite_checkpoint=first)
    proof=dict(schema='software.hu-sb40-34-publication-check.v1',status='PASS',complete_models=34,
        new_confirmed_json_histories=17,zip_crc_all_entries_valid=True,windows_run=PARENT_WINDOWS,
        native_catalog_asset=PARENT_CATALOG,published_histories_checked=[dict(status='PASS',json_streets=3,policy_sha256=c['policy_sha256']) for c in cases[17:]],
        metadata_hashes=[dict(name='SYNTHETIC-evidence.json',tag=SB40_COMPLETE34_TAG,bytes=20,sha256='e'*64)],
        source_asset='SYNTHETIC-source.zip',source_bytes=30,source_sha256='f'*64)
    proof_ref=dict(name='publicacao-final-verificada-sb40-34-'+PARENT_WINDOWS+'-a1.json',bytes=40,sha256='a'*64)
    releases={tag:dict(assets=[]) for tag in {c['tag'] for c in cases}}
    for case in cases:
        releases[case['tag']]['assets'] += [dict(name=p['name'],size=p['bytes'],digest='sha256:'+p['sha256'],state='uploaded') for p in case['parts']]
    for p in proof['metadata_hashes']+[dict(name=proof['source_asset'],bytes=proof['source_bytes'],sha256=proof['source_sha256']),proof_ref]:
        releases[SB40_COMPLETE34_TAG]['assets'].append(dict(name=p['name'],size=p['bytes'],digest='sha256:'+p['sha256'],state='uploaded'))
    return full,delivery,proof,proof_ref,releases,dict(status='completed',conclusion='success')


class SB40Complete51Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=synthetic_parent();cls.intent=read_intent()

    def values(self):return copy.deepcopy(self.fixture)

    def plan(self):
        values=self.values();checkpoint=checkpoint34(*values)
        return values[0],checkpoint,make_plan51(values[0],checkpoint,self.intent)

    def test_reserved_seventeen_reproduce_without_claiming_unfinished_models(self):
        parent=self.fixture[0]['_original_plan'];self.assertEqual(make_intent(parent),self.intent)
        previous={canonical_flop(b) for b in self.intent['previous_and_in_progress_boards']}
        new={canonical_flop(c['board']) for c in self.intent['cases']}
        self.assertEqual(len(previous),34);self.assertEqual(len(previous|new),51)
        self.assertFalse(new&{canonical_flop(b) for b in self.intent['preserved_holdout_flops']})
        self.assertNotIn('policy_sha256',self.intent['cases'][0])
        self.assertTrue(self.intent['policy_ids_created_only_after_actual_parent_completion'])

    def test_complete_parent_metadata_and_previous_full_windows_receipts_unlock_the_plan(self):
        previous,checkpoint,plan=self.plan()
        self.assertEqual(checkpoint['complete_saved_models'],34)
        self.assertEqual(plan['target_total_models'],51);self.assertEqual(len(plan['cases']),17)
        self.assertEqual(plan['game'],previous['_original_plan']['game'])
        self.assertEqual(plan['settings'],self.intent['settings'])
        self.assertEqual(plan['pilot_tag'],SB40_TAG)

    def test_running_or_failed_parent_never_unlocks_the_third_batch(self):
        for status,conclusion in (('in_progress',None),('completed','failure'),('completed','cancelled')):
            v=self.values();v[-1].update(status=status,conclusion=conclusion)
            with self.subTest(status=status,conclusion=conclusion),self.assertRaises(StrategyError):checkpoint34(*v)

    def test_only_seventeen_saved_models_cannot_be_promoted_to_thirty_four(self):
        v=self.values();v[0]['cases']=v[0]['cases'][:17]
        with self.assertRaisesRegex(StrategyError,'THIRTY_FOUR'):checkpoint34(*v)

    def test_loss_of_any_old_or_new_parent_part_blocks_the_next_seventeen(self):
        for index in (0,16,17,33):
            v=self.values();case=v[0]['cases'][index];name=case['parts'][0]['name']
            v[4][case['tag']]['assets']=[a for a in v[4][case['tag']]['assets'] if a['name']!=name]
            with self.subTest(index=index),self.assertRaisesRegex(StrategyError,'REMOTE_REFERENCE_PART'):checkpoint34(*v)

    def test_wrong_hash_or_size_of_a_parent_part_blocks_progress(self):
        for field,value in (('size',1),('digest','sha256:'+'0'*64)):
            v=self.values();v[4][SB40_COMPLETE34_TAG]['assets'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'REMOTE_REFERENCE_PART'):checkpoint34(*v)

    def test_partial_native_or_unclosed_worker_is_not_a_saved_complete_model(self):
        for field,value in (('native_target_met',False),('worker_exited',False),('temporary_cleanup_verified',False)):
            v=self.values();v[0]['cases'][-1][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'PARTIAL_OR_NOT_CLOSED'):checkpoint34(*v)

    def test_missing_windows_hand_or_missing_crc_receipt_blocks_progress(self):
        for mode in ('hand','crc','windows-case'):
            v=self.values()
            if mode=='hand':v[2]['published_histories_checked'].pop()
            elif mode=='crc':v[2]['zip_crc_all_entries_valid']=False
            else:v[1]['windows_cases'].pop()
            with self.subTest(mode=mode),self.assertRaises(StrategyError):checkpoint34(*v)

    def test_source_zip_and_evidence_must_still_be_durable(self):
        for name in ('SYNTHETIC-source.zip','SYNTHETIC-evidence.json',self.fixture[3]['name']):
            v=self.values();v[4][SB40_COMPLETE34_TAG]['assets']=[a for a in v[4][SB40_COMPLETE34_TAG]['assets'] if a['name']!=name]
            with self.subTest(name=name),self.assertRaisesRegex(StrategyError,'ARTIFACT_MISSING'):checkpoint34(*v)

    def test_checkpoint_hash_and_preserved_file_ids_are_not_advisory(self):
        previous,checkpoint,plan=self.plan()
        for mode in ('hash','file'):
            bad=copy.deepcopy(checkpoint)
            if mode=='hash':bad['checkpoint_sha256']='0'*64
            else:
                bad['preserved_models'][-1]['file_sha256']='0'*64;bad.pop('checkpoint_sha256');bad['checkpoint_sha256']=digest(bad)
            with self.subTest(mode=mode),self.assertRaisesRegex(StrategyError,'NO_NEW_SOLVE'):make_plan51(previous,bad,self.intent)

    def test_exact_parent_receipt_is_pinned_in_the_runtime_plan(self):
        previous,checkpoint,plan=self.plan()
        with patch('strategy.sb40_progression.load_parent34',return_value=(previous,checkpoint)) as load:
            validate_derived_plan51(plan,plan['plan_sha256']);load.assert_called_once_with(plan['parent_delivery_proof'])

    def test_self_rehashed_runtime_strategy_changes_are_rejected(self):
        previous,checkpoint,plan=self.plan()
        for mode in ('range','stack','size','accuracy','iterations'):
            bad=copy.deepcopy(plan)
            if mode=='range':
                w=bad['game']['ranges'][0]['weights'];w[next(iter(w))]=.123;bad['model_sha256']=model_identity(bad['game'])
            elif mode=='stack':
                bad['game']['root']['stacks'][0]-=1;bad['model_sha256']=model_identity(bad['game'])
            elif mode=='size':
                bad['game']['menu']['fractions']=[.5];bad['model_sha256']=model_identity(bad['game'])
            else:bad['settings']['accuracy_pct' if mode=='accuracy' else 'iterations']=1
            bad.pop('plan_sha256');bad['plan_sha256']=digest(bad)
            with self.subTest(mode=mode),patch('strategy.sb40_progression.load_parent34',return_value=(previous,checkpoint)),self.assertRaisesRegex(StrategyError,'EXACT_DERIVATION'):
                validate_derived_plan51(bad)

    def test_a_missing_publication_receipt_is_pending_before_loading_any_policy(self):
        with patch('strategy.sb40_progression.read_json',return_value=dict(assets=[])),self.assertRaises(PrerequisitePending):load_parent34()

    def test_timeout_before_parent_completion_creates_no_inputs_or_release(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'must-not-exist'
            with patch('tools.prepare_hu_sb40_complete51.read_json',side_effect=HTTPError('https://api.github.com',404,'not yet',None,None)),\
                 patch('tools.prepare_hu_sb40_complete51.load_parent34',side_effect=PrerequisitePending('not yet')),\
                 patch('tools.prepare_hu_sb40_complete51.time.monotonic',side_effect=[0.,2.]),\
                 patch('tools.prepare_hu_sb40_complete51.subprocess.run') as command,\
                 self.assertRaisesRegex(StrategyError,'NO_NEW_CFR_STARTED'):
                initialize(output,1,publish=True)
            command.assert_not_called();self.assertFalse(output.exists())

    def test_merge_preserves_all_previous_tags_hashes_and_ordinals(self):
        previous,checkpoint,plan=self.plan()
        cases=[dict(c,tag=SB40_COMPLETE51_TAG,policy_sha256=digest(['SYNTHETIC_CHILD',c['ordinal']]),file_sha256='a'*64) for c in plan['cases']]
        catalog=dict(tag=SB40_COMPLETE51_TAG,status='COMPLETE',cases=cases,_original_plan=plan,profile_settings=plan['profile_settings'])
        full=combine_sb40_fifty_one(catalog,previous)
        self.assertEqual([c['ordinal'] for c in full['cases']],list(range(1,52)))
        for old,new in zip(previous['cases'],full['cases'][:34]):
            self.assertEqual({k:old[k] for k in ('board','tag','file_sha256','policy_sha256','source_ordinal')},
                             {k:new[k] for k in ('board','tag','file_sha256','policy_sha256','source_ordinal')})
        self.assertEqual(full['cases'][34]['source_ordinal'],1)
        self.assertFalse(full['suit_aliases_counted_as_models'])

    def test_loader_rebuilds_the_unpinned_child_hash_from_the_specific_verified_parent(self):
        previous,checkpoint,plan=self.plan();manifests=[];assets=[]
        for c in plan['cases']:
            value=copy.deepcopy(previous['cases'][0]);value.update(c,tag=SB40_COMPLETE51_TAG,
                plan_sha256=plan['plan_sha256'],lookup_streets=['flop','turn','river'])
            for j,part in enumerate(value['parts']):
                part['name']=f'SYNTHETIC-child-{c["ordinal"]:02d}-{j:02d}.part'
                assets.append(dict(name=part['name'],state='uploaded',size=part['bytes'],digest='sha256:'+part['sha256']))
            manifests.append(value)
        catalog=make_catalog(plan,manifests);name='batch-catalog-999.json'
        assets.append(dict(name=name,id=1,state='uploaded'))
        def receive(url):
            if url==ASSET_BASE+SB40_COMPLETE51_TAG+'/sb40-complete51-plan.json':return plan
            if url.endswith('/releases/tags/'+SB40_COMPLETE51_TAG):return dict(assets=assets)
            if url==ASSET_BASE+SB40_COMPLETE51_TAG+'/'+name:return catalog
            raise AssertionError('Unexpected synthetic-fixture metadata request: '+url)
        with patch('strategy.campaign_download.read_json',side_effect=receive),patch('strategy.sb40_progression.load_parent34',return_value=(previous,checkpoint)):
            got,asset=load_campaign(SB40_COMPLETE51_TAG,name)
        self.assertEqual(asset,name);self.assertEqual(got['plan_sha256'],plan['plan_sha256'])
        self.assertEqual(got['status'],'COMPLETE');self.assertEqual(len(got['cases']),17)
        self.assertEqual(got['pilot_tag'],SB40_TAG)

    def test_retry_catalog_is_new_attempt_evidence_and_preserves_the_previous_receipt(self):
        from tools import hu_batch16
        previous,checkpoint,plan=self.plan();manifests=[]
        for c in plan['cases']:
            value=copy.deepcopy(previous['cases'][0]);value.update(c,tag=SB40_COMPLETE51_TAG,
                plan_sha256=plan['plan_sha256'],lookup_streets=['flop','turn','river'])
            manifests.append(value)
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);old=folder/'batch-catalog-999-a1.json';old.write_text('preserve the failed attempt')
            output=folder/'outputs.txt'
            with patch.dict('os.environ',{'GITHUB_RUN_ID':'999','GITHUB_RUN_ATTEMPT':'2','GITHUB_OUTPUT':str(output)}),\
                    patch.object(hu_batch16,'remote_manifests',return_value=manifests),\
                    patch.object(hu_batch16,'BATCH_TAG',SB40_COMPLETE51_TAG),\
                    patch.object(hu_batch16.subprocess,'run') as upload:
                self.assertEqual(hu_batch16.catalog(plan,folder),0)
            self.assertEqual(old.read_text(),'preserve the failed attempt')
            self.assertTrue((folder/'batch-catalog-999-a2.json').exists())
            self.assertIn('catalog_asset=batch-catalog-999-a2.json',output.read_text())
            self.assertTrue(any(str(call.args[0][-1]).endswith('batch-catalog-999-a2.json') for call in upload.call_args_list))

    def test_finalizer_accepts_attempt_catalogs_but_refuses_another_native_run(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'new'
            with self.assertRaisesRegex(StrategyError,'ACTUAL_NATIVE_WORKFLOW'):
                finalize51(['--catalog-asset','batch-catalog-998-a2.json','--native-run','999','--output',str(output)])
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                finalize51(['--catalog-asset','batch-catalog-999-a2.json','--native-run','999','--output',temp])

    def test_publication_verifier_preserves_existing_work_before_network_access(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel=Path(temp)/'existing.txt';sentinel.write_text('preserve')
            with self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                verify51(['--run','999','--catalog-asset','batch-catalog-999-a2.json','--output',temp])
            self.assertEqual(sentinel.read_text(),'preserve')

    def test_loader_rejects_a_self_rehashed_strategy_change_before_requesting_the_child_catalog(self):
        previous,checkpoint,plan=self.plan();plan['settings']['accuracy_pct']=1
        plan.pop('plan_sha256');plan['plan_sha256']=digest(plan)
        with patch('strategy.campaign_download.read_json',return_value=plan) as receive,patch('strategy.sb40_progression.load_parent34',return_value=(previous,checkpoint)),self.assertRaisesRegex(StrategyError,'EXACT_DERIVATION'):
            load_campaign(SB40_COMPLETE51_TAG,'batch-catalog-999.json')
        self.assertEqual(receive.call_count,1)


if __name__=='__main__':unittest.main()
