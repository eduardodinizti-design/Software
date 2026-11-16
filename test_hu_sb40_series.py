"""Continuation gates using synthetic metadata; these are not solved poker models."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from urllib.error import HTTPError

from strategy.batch_archive import make_catalog
from strategy.batch_download import ASSET_BASE,metadata_snapshot,read_json
from strategy.batch_jobs import canonical_flop,catalogue_flops
from strategy.campaign_download import load_family
from strategy.sb40_progression import checkpoint34,make_plan51,read_intent,PrerequisitePending
from strategy.sb40_series import (CONTROLLER_BRANCH,CONTROLLER_PATH,DOC,FIRST_PARENT_RUN,
    family_tag,make_series_intents,read_series_intent,checked_parent_milestone,
    checkpoint_parent,make_series_plan,validate_series_plan,combine_series)
from strategy.state_contract import StrategyError,digest
from test_hu_sb40_complete51 import synthetic_parent
from tools.prepare_hu_sb40_series import initialize
from tools.finalize_hu_sb40_series import main as finalize
from tools.verify_hu_sb40_series_publication import main as verify


def synthetic_generation(previous,checkpoint,plan,target):
    """Extend fixture shapes; IDs/part names explicitly identify synthetic metadata."""
    tag=family_tag(target);cases=copy.deepcopy(previous['cases']);rows=[]
    old=json.loads((Path(__file__).parent/'docs/software-hu-sb40-next16-20261116/published/entrega-sb40-next16-43796410882-a1.json').read_text())
    for i,planned in enumerate(plan['cases']):
        c=copy.deepcopy(old['inventory'][1+i%16]);r=copy.deepcopy(old['windows_cases'][i%16])
        policy=digest(['SYNTHETIC_METADATA_NOT_SOLVED',target,i]);file=digest(['SYNTHETIC_NOT_DOWNLOADED',target,i])
        c.update(planned,tag=tag,policy_sha256=policy,file_sha256=file,plan_sha256=plan['plan_sha256'],
            ordinal=len(previous['cases'])+i+1,source_ordinal=i+1)
        c.pop('resource_profile',None)
        c.pop('resource_profile',None);c.pop('effective_execution_settings',None)
        for j,p in enumerate(c['parts']):p['name']=f'SYNTHETIC-{target}-{i:02d}-{j:02d}.part'
        r.update(ordinal=i+1,board=c['board'],policy_sha256=policy,file_sha256=file)
        r['confirmed_hand']['policy_sha256']=policy
        r['root_policy_review'].update(board=c['board'],source_policy_sha256=policy)
        cases.append(c);rows.append(r)
    full=dict(tag=tag,status='COMPLETE',plan_sha256=plan['plan_sha256'],cases=cases,_original_plan=plan,
        profile_settings=plan['profile_settings'],context=plan['game']['context'],root_template=plan['game']['root'],
        source_catalogs=previous['source_catalogs']+[dict(tag=tag,plan_sha256=plan['plan_sha256'])])
    run_id=FIRST_PARENT_RUN if target==51 else '99999999999'
    proof_name=f'publicacao-final-verificada-sb40-{target}-{run_id}-a1.json'
    proof_ref=dict(tag=tag,run_id=run_id,name=proof_name,bytes=40,sha256='a'*64)
    catalog=f'batch-catalog-{run_id}-a1.json';commit='c'*40
    delivery=dict(status='PASS',complete_distinct_flop_models=target,new_complete_flop_models=17,
        previous_saved_flop_models=target-17,new_windows_policy_pass=17,new_confirmed_synthetic_hands=17,
        new_json_street_queries=51,new_exact_suit_street_queries=51,all_new_workers_exited=True,
        all_new_native_temporaries_removed=True,pppoker_windows_validated=False,context=plan['game']['context'],
        profile_settings=plan['profile_settings'],inventory=cases,windows_cases=rows,
        total_policy_file_bytes=sum(c['policy_file_bytes'] for c in cases),total_public_nodes=sum(c['coverage']['public_nodes'] for c in cases),
        prerequisite_checkpoint=checkpoint,source_commit=commit,catalog_asset=catalog,plan_sha256=plan['plan_sha256'])
    names=[f'entrega-sb40-{target}-{run_id}-a1.json']+[f'SYNTHETIC-evidence-{target}-{i}.json' for i in range(4)]
    proof=dict(schema=('software.hu-sb40-51-publication-check.v1' if target==51 else 'software.hu-sb40-series-publication-check.v1'),
        status='PASS',complete_models=target,complete_prior_models_preserved=target-17,windows_run=run_id,
        new_confirmed_json_histories=17,new_json_street_queries=51,new_exact_suit_street_queries=51,
        zip_crc_all_entries_valid=True,pppoker_windows_validated=False,native_catalog_asset=catalog,
        published_histories_checked=[dict(status='PASS',json_streets=3,policy_sha256=c['policy_sha256']) for c in cases[-17:]],
        metadata_hashes=[dict(name=name,tag=tag,bytes=20,sha256='e'*64) for name in names],
        source_asset='SYNTHETIC-source.zip',source_bytes=30,source_sha256='f'*64)
    releases={t:dict(assets=[]) for t in {c['tag'] for c in cases}}
    for c in cases:
        releases[c['tag']]['assets'] += [dict(name=p['name'],size=p['bytes'],digest='sha256:'+p['sha256'],state='uploaded') for p in c['parts']]
    for a in proof['metadata_hashes']+[dict(name=proof['source_asset'],bytes=proof['source_bytes'],sha256=proof['source_sha256']),proof_ref]:
        releases[tag]['assets'].append(dict(name=a['name'],size=a['bytes'],digest='sha256:'+a['sha256'],state='uploaded'))
    run=dict(id=int(run_id),status='completed' if target==51 else 'in_progress',conclusion='success' if target==51 else None,
        head_sha=commit,head_branch='feat/hu-sb40-complete51-20261116' if target==51 else CONTROLLER_BRANCH,
        path='.github/workflows/hu-sb40-complete51.yml' if target==51 else CONTROLLER_PATH)
    jobs=[] if target==51 else [dict(id=123,run_attempt=1,name=f'Deliver SB40 {target} and verify publication',status='completed',conclusion='success')]
    return full,delivery,proof,proof_ref,releases,run,jobs


class SB40SeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old=synthetic_parent();cp=checkpoint34(*old);plan=make_plan51(old[0],cp,read_intent())
        cls.fixtures={};cls.plans={};current=synthetic_generation(old[0],cp,plan,51)
        for n in (68,85,102):
            cls.fixtures[n]=current;checkpoint=checkpoint_parent(n,*current)
            plan=make_series_plan(n,current[0],checkpoint,read_series_intent(n));cls.plans[n]=(current[0],checkpoint,plan)
            if n<102:current=synthetic_generation(current[0],checkpoint,plan,n)

    def fixture(self,n=68):return copy.deepcopy(self.fixtures[n])

    def test_reserved_102_are_distinct_preserve_the_first_51_and_exclude_holdouts(self):
        expected=make_series_intents();first=read_intent()
        before=first['previous_and_in_progress_boards']+[c['board'] for c in first['cases']]
        for n,value in expected.items():
            self.assertEqual(value,read_series_intent(n));self.assertEqual(len(value['cases']),17)
            self.assertEqual(value['previous_and_in_progress_boards'],before)
            self.assertNotIn('policy_sha256',value['cases'][0])
            before=before+[c['board'] for c in value['cases']]
        self.assertEqual(len({canonical_flop(b) for b in before}),102)
        self.assertFalse({canonical_flop(b) for b in before}&{canonical_flop(b) for b in first['preserved_holdout_flops']})
        self.assertEqual(catalogue_flops(100),catalogue_flops(256)[:100])

    def test_all_three_exact_recipes_preserve_the_same_game_settings_and_actual_parent_ids(self):
        for n,(previous,checkpoint,plan) in self.plans.items():
            self.assertEqual(plan['game'],previous['_original_plan']['game'])
            self.assertEqual(plan['settings'],read_intent()['settings'])
            self.assertEqual(plan['preexisting_models'],checkpoint['preserved_models'])
            self.assertEqual(len(plan['preexisting_models']),n-17)
            self.assertEqual(plan['target_total_models'],n)

    def test_external_51_workflow_must_finish_successfully(self):
        for status,conclusion in (('in_progress',None),('completed','failure'),('completed','cancelled')):
            v=self.fixture();v[5].update(status=status,conclusion=conclusion)
            with self.subTest(status=status,conclusion=conclusion),self.assertRaises(StrategyError):checkpoint_parent(68,*v)

    def test_later_stage_starts_after_delivery_job_success_while_controller_still_running(self):
        for n in (85,102):
            v=self.fixture(n);self.assertEqual(v[5]['status'],'in_progress')
            result=checkpoint_parent(n,*v)
            self.assertEqual(result['completed_delivery_milestone']['method'],'COMPLETE_PREVIOUS_DELIVERY_JOB_WITHIN_THE_SAME_CONTROLLER')
            self.assertEqual(result['complete_saved_models'],n-17)

    def test_another_job_or_another_attempt_cannot_unlock_the_next_stage(self):
        for mode in ('other-stage','wrong-attempt','running','failure','missing'):
            v=self.fixture(85)
            if mode=='other-stage':v[6][0]['name']='Deliver SB40 85 and verify publication'
            elif mode=='wrong-attempt':v[6][0]['run_attempt']=2
            elif mode=='running':v[6][0].update(status='in_progress',conclusion=None)
            elif mode=='failure':v[6][0]['conclusion']='failure'
            else:v[6].clear()
            with self.subTest(mode=mode),self.assertRaises(StrategyError):checkpoint_parent(85,*v)

    def test_wrong_parent_workflow_branch_run_or_source_is_rejected(self):
        for key in ('path','head_branch','head_sha','id'):
            v=self.fixture(85);v[5][key]='wrong'
            with self.subTest(key=key),self.assertRaisesRegex(StrategyError,'SOURCE_OR_BRANCH'):checkpoint_parent(85,*v)

    def test_any_lost_ancestor_part_or_changed_digest_prevents_the_next_batch(self):
        for n in (68,85,102):
            for index in (0,n-18):
                v=self.fixture(n);case=v[0]['cases'][index];name=case['parts'][0]['name']
                v[4][case['tag']]['assets']=[a for a in v[4][case['tag']]['assets'] if a['name']!=name]
                with self.subTest(n=n,index=index),self.assertRaisesRegex(StrategyError,'REMOTE_REFERENCE_PART'):checkpoint_parent(n,*v)

    def test_partial_policies_missing_windows_rows_histories_or_source_do_not_unlock(self):
        for mode in ('partial','worker','windows','history','crc','source','previous-id','metadata'):
            v=self.fixture()
            if mode=='partial':v[0]['cases'][-1]['coverage']['structurally_complete']=False
            elif mode=='worker':v[0]['cases'][-1]['worker_exited']=False
            elif mode=='windows':v[1]['windows_cases'].pop()
            elif mode=='history':v[2]['published_histories_checked'].pop()
            elif mode=='crc':v[2]['zip_crc_all_entries_valid']=False
            elif mode=='source':v[4][family_tag(51)]['assets']=[a for a in v[4][family_tag(51)]['assets'] if a['name']!=v[2]['source_asset']]
            elif mode=='previous-id':v[1]['prerequisite_checkpoint']['preserved_models'][0]['file_sha256']='0'*64
            else:v[2]['metadata_hashes'].pop()
            with self.subTest(mode=mode),self.assertRaises(StrategyError):checkpoint_parent(68,*v)

    def test_self_rehashed_changes_to_ranges_stacks_menu_or_calculation_are_rejected(self):
        from strategy.campaign import model_identity
        previous,checkpoint,plan=self.plans[68]
        for mode in ('range','stack','size','accuracy','iterations','board'):
            bad=copy.deepcopy(plan)
            if mode=='range':
                weights=bad['game']['ranges'][0]['weights'];weights[next(iter(weights))]=.123
            elif mode=='stack':bad['game']['root']['stacks'][0]-=1
            elif mode=='size':bad['game']['menu']['fractions']=[.5]
            elif mode=='board':bad['cases'][0],bad['cases'][1]=bad['cases'][1],bad['cases'][0]
            else:bad['settings']['accuracy_pct' if mode=='accuracy' else 'iterations']=1
            bad['model_sha256']=model_identity(bad['game']);bad.pop('plan_sha256');bad['plan_sha256']=digest(bad)
            with self.subTest(mode=mode),patch('strategy.sb40_series.load_series_parent',return_value=(previous,checkpoint)),self.assertRaises(StrategyError):
                validate_series_plan(bad)

    def test_merge_keeps_actual_ids_tags_and_original_ordinals_through_102(self):
        for n,(previous,checkpoint,plan) in self.plans.items():
            fixture=synthetic_generation(previous,checkpoint,plan,n);new=fixture[0]['cases'][-17:]
            catalog=dict(tag=family_tag(n),status='COMPLETE',cases=[dict(c,ordinal=c['source_ordinal']) for c in new],
                _original_plan=plan,profile_settings=plan['profile_settings'])
            full=combine_series(catalog,previous)
            self.assertEqual(full['cases'][:n-17],previous['cases'])
            self.assertEqual([c['ordinal'] for c in full['cases']],list(range(1,n+1)))
            self.assertFalse(full['suit_aliases_counted_as_models'])

    def test_family_loader_uses_the_already_validated_parent_once(self):
        previous,checkpoint,plan=self.plans[68];fixture=synthetic_generation(previous,checkpoint,plan,68)
        manifests=[dict(c,ordinal=c['source_ordinal']) for c in fixture[0]['cases'][-17:]]
        catalog=make_catalog(plan,manifests);name='batch-catalog-999-a1.json';tag=family_tag(68)
        remote=fixture[4][tag];remote['assets'].append(dict(name=name,id=1,state='uploaded'))
        def receive(url):
            if url==ASSET_BASE+tag+'/sb40-complete68-plan.json':return plan
            if url.endswith('/releases/tags/'+tag):return remote
            if url==ASSET_BASE+tag+'/'+name:return catalog
            raise AssertionError('Unexpected metadata request '+url)
        with patch('strategy.campaign_download.read_json',side_effect=receive),patch('strategy.sb40_series.load_series_parent',return_value=(previous,checkpoint)) as parent:
            full,_=load_family('sb40-68',name)
        self.assertEqual(len(full['cases']),68);parent.assert_called_once_with(68,plan['parent_delivery_proof'])

    def test_timeout_before_51_completion_creates_no_inputs_release_or_solver(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'must-not-exist'
            with patch('tools.prepare_hu_sb40_series.read_json',side_effect=HTTPError('https://api.github.com',404,'pending',None,None)),\
                patch('tools.prepare_hu_sb40_series.load_series_parent',side_effect=PrerequisitePending('pending')),\
                patch('tools.prepare_hu_sb40_series.time.monotonic',side_effect=[0.,2.]),\
                patch('tools.prepare_hu_sb40_series.subprocess.run') as command,self.assertRaisesRegex(StrategyError,'NO_NEW_CFR_STARTED'):
                initialize(68,output,1,publish=True)
            command.assert_not_called();self.assertFalse(output.exists())

    def test_publisher_and_verifier_preserve_existing_work_before_network_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel=Path(temp)/'preserve.txt';sentinel.write_text('preserve')
            with self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                finalize(['--target','102','--catalog-asset','batch-catalog-999-a1.json','--native-run','999','--output',temp])
            with self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                verify(['--target','102','--catalog-asset','batch-catalog-999-a1.json','--run','999','--output',temp])
            self.assertEqual(sentinel.read_text(),'preserve')

    def test_all_three_delivery_source_zip_roundtrips_preserve_target_names_and_frozen_inputs(self):
        """Synthetic transfer integration, no solver/Windows claim; real ZIP/SHA checks."""
        import tools.finalize_hu_sb40_series as finalizer
        import tools.verify_hu_sb40_series_publication as verifier
        for count,(previous,checkpoint,plan) in self.plans.items():
            fixture=synthetic_generation(previous,checkpoint,plan,count);full=fixture[0]
            catalog=dict(full,cases=[dict(c,ordinal=c['source_ordinal']) for c in full['cases'][-17:]])
            run='99999999999';asset_name=f'batch-catalog-{run}-a1.json';tag=family_tag(count)
            with self.subTest(target=count),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);store=root/'published';store.mkdir();remote=dict(assets=[])
                def publish(name,raw):
                    (store/name).write_bytes(raw)
                    remote['assets'].append(dict(id=len(remote['assets'])+1,name=name,state='uploaded',size=len(raw),digest='sha256:'+hashlib.sha256(raw).hexdigest()))
                for row in fixture[1]['windows_cases']:
                    name=f'windows-sb40-{count}-case-{row["ordinal"]:02d}-{run}-a1.json'
                    publish(name,json.dumps(row).encode());history=io.BytesIO()
                    with zipfile.ZipFile(history,'w') as z:z.writestr('SYNTHETIC.txt','synthetic transfer only')
                    publish(name[:-5]+'-json-history.zip',history.getvalue())
                publish(f'windows-contracts-sb40-{count}-{run}-a1.txt',b'Ran 10 tests in 1.0s\n\nOK\n')
                def receive(asset,release,destination):
                    raw=(store/asset['name']).read_bytes();self.assertEqual(len(raw),asset['size'])
                    sha=hashlib.sha256(raw).hexdigest();self.assertEqual('sha256:'+sha,asset['digest'])
                    destination.write_bytes(raw)
                    return dict(tag=release,name=asset['name'],bytes=len(raw),sha256=sha)
                def command(args,**kwargs):
                    if args[:2]==['git','archive']:
                        with zipfile.ZipFile(args[-1],'w') as z:
                            for name in (f'BAIXAR_BLIND_WAR_40BB_{count}.bat','strategy/campaign_download.py',
                                    'strategy/sb40_series.py','tools/prepare_hu_sb40_series.py','docs/GUIA_SB40_102_FLOPS_20261116.txt'):
                                z.writestr('Software/'+name,'SYNTHETIC SOURCE TRANSFER TEST')
                    elif args[:3]==['gh','release','upload']:
                        path=Path(args[-1]);publish(path.name,path.read_bytes())
                def history(path,row):return dict(status='PASS',policy_sha256=row['policy_sha256'],json_streets=3)
                folder=root/'docs/software-hu-sb40-to102-20261116';folder.mkdir(parents=True)
                (folder/'regressao-linux.json').write_text(json.dumps(dict(status='PASS',passed=1,tests_run=1,
                    native_stream_tests_enabled=True,errors=0,failures=0,skipped=[])))
                before=Path.cwd()
                try:
                    os.chdir(root)
                    with patch.dict(os.environ,dict(GITHUB_RUN_ID=run,GITHUB_RUN_ATTEMPT='1',GITHUB_SHA='c'*40)),\
                        patch.object(finalizer,'load_family',side_effect=lambda *a,**k:(catalog if k.get('new_only') else full,asset_name)),\
                        patch.object(finalizer,'validate_series_plan',return_value=(previous,checkpoint)),\
                        patch.object(finalizer,'release',return_value=remote),patch.object(finalizer,'receive',side_effect=receive),\
                        patch.object(finalizer,'check_history',side_effect=history),patch.object(finalizer.subprocess,'run',side_effect=command):
                        self.assertEqual(finalizer.main(['--target',str(count),'--catalog-asset',asset_name,'--native-run',run,'--output',str(root/'final')]),0)
                    with patch.object(verifier,'load_family',side_effect=lambda *a,**k:(catalog if k.get('new_only') else full,asset_name)),\
                        patch.object(verifier,'validate_series_plan',return_value=(previous,checkpoint)),\
                        patch.object(verifier,'release',return_value=remote),patch.object(verifier,'receive',side_effect=receive),\
                        patch.object(verifier,'check_history',side_effect=history),\
                        patch.object(verifier,'fetch',side_effect=lambda url:io.BytesIO((store/url.rsplit('/',1)[-1]).read_bytes())):
                        self.assertEqual(verifier.main(['--target',str(count),'--catalog-asset',asset_name,'--run',run,'--output',str(root/'verified')]),0)
                    proof=json.loads((root/'verified/publicacao-final-verificada.json').read_text())
                    self.assertEqual(proof['complete_models'],count);self.assertEqual(proof['complete_prior_models_preserved'],count-17)
                    self.assertTrue(proof['zip_crc_all_entries_valid']);self.assertFalse(proof['pppoker_windows_validated'])
                finally:os.chdir(before)


class ScopedMetadataTests(unittest.TestCase):
    def test_one_ancestry_read_reuses_metadata_without_mutation_and_refreshes_next_operation(self):
        with patch('strategy.batch_download._read_json_uncached',side_effect=[dict(value=[1]),dict(value=[2])]) as network:
            with metadata_snapshot():
                value=read_json('https://example.test/metadata');value['value'].append(99)
                with metadata_snapshot():self.assertEqual(read_json('https://example.test/metadata'),dict(value=[1]))
            with metadata_snapshot():self.assertEqual(read_json('https://example.test/metadata'),dict(value=[2]))
            self.assertEqual(network.call_count,2)

    def test_bounded_scope_does_not_bypass_another_size_limit(self):
        with patch('strategy.batch_download._read_json_uncached',return_value={}) as network,metadata_snapshot():
            read_json('https://example.test/a',100);read_json('https://example.test/a',200)
            for i in range(130):read_json('https://example.test/'+str(i))
            read_json('https://example.test/129')
        self.assertEqual(network.call_count,133)


if __name__=='__main__':unittest.main()
