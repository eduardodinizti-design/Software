"""Verify automatic wait recovery without starting or retrying CFR in the tests."""
import copy
import os
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from strategy.batch_archive import REPOSITORY
from strategy.state_contract import StrategyError
from tools import supervise_hu_sb40 as supervisor


def failed_wait(key='series',target=68):
    name='checked-catalog' if key=='windows34' else ('initialize' if key=='seed51' else 'initialize'+str(target))
    step=supervisor.WAIT_JOBS[(key,name)][1];reason=supervisor.WAIT_JOBS[(key,name)][2]
    run=dict(id=int(supervisor.RUNS[key][0]),run_attempt=1,status='completed',conclusion='failure')
    job=dict(id=123,name=name,status='completed',conclusion='failure',
        steps=[dict(name=step,status='completed',conclusion='failure')])
    return run,[job],{123:'SYNTHETIC LOG: '+reason}


class SupervisorTests(unittest.TestCase):
    def test_known_expired_wait_is_retried_only_after_complete_parent_verification(self):
        for key,target in (('windows34',34),('seed51',51),('series',68),('series',85),('series',102)):
            run,jobs,logs=failed_wait(key,target)
            with self.subTest(key=key,target=target),patch.object(supervisor,'prerequisite_ready',return_value=False) as ready:
                self.assertIsNone(supervisor.choose_retry(key,run,jobs,logs));ready.assert_called_once_with(target)
            with patch.object(supervisor,'prerequisite_ready',return_value=True):
                result=supervisor.choose_retry(key,run,jobs,logs)
            self.assertEqual(result['job_id'],123);self.assertEqual(result['target'],target)

    def test_running_and_queued_work_never_triggers_a_retry(self):
        for status in ('queued','in_progress','waiting','requested','pending'):
            run,jobs,logs=failed_wait();run.update(status=status,conclusion=None)
            with self.subTest(status=status),patch.object(supervisor,'prerequisite_ready') as ready:
                self.assertIsNone(supervisor.choose_retry('series',run,jobs,logs));ready.assert_not_called()

    def test_explicit_user_cancellation_is_preserved(self):
        run,jobs,logs=failed_wait();run['conclusion']='cancelled'
        with self.assertRaisesRegex(StrategyError,'CANCELLATION_PRESERVED'):
            supervisor.choose_retry('series',run,jobs,logs)

    def test_solver_test_failure_partial_policy_or_wrong_step_never_becomes_a_generic_retry(self):
        for mode in ('solver','tests','wrong-step','wrong-error','several-failures'):
            run,jobs,logs=failed_wait()
            if mode=='solver':jobs[0]['name']='SB40 target 68 full-tree model 7 of seventeen'
            elif mode=='tests':jobs[0]['name']='contracts68'
            elif mode=='wrong-step':jobs[0]['steps'][0]['name']='Prepare modified ranges'
            elif mode=='wrong-error':logs[123]='IMMUTABLE_CAMPAIGN_CATALOG_IS_PARTIAL_INSPECT_FAILURES'
            else:jobs.append(dict(jobs[0],id=124))
            with self.subTest(mode=mode),patch.object(supervisor,'prerequisite_ready') as ready,self.assertRaisesRegex(StrategyError,'DIAGNOSIS'):
                supervisor.choose_retry('series',run,jobs,logs)
            ready.assert_not_called()

    def test_native_34_solver_failure_cannot_be_automatically_recomputed(self):
        run,jobs,logs=failed_wait();jobs[0]['name']='Complete SB40 new flop 3 of seventeen'
        with patch.object(supervisor,'prerequisite_ready') as ready,self.assertRaisesRegex(StrategyError,'DIAGNOSIS'):
            supervisor.choose_retry('native34',run,jobs,logs)
        ready.assert_not_called()

    def test_timed_out_known_wait_can_be_classified_without_losing_its_job_identity(self):
        run,jobs,logs=failed_wait();jobs[0]['conclusion']='timed_out'
        with patch.object(supervisor,'prerequisite_ready',return_value=True):
            self.assertEqual(supervisor.choose_retry('series',run,jobs,{})['job_id'],123)

    def test_wrong_workflow_source_branch_or_run_is_rejected(self):
        run_id,sha,path,branch=supervisor.RUNS['series']
        original=dict(id=int(run_id),head_sha=sha,path='.github/workflows/'+path,head_branch=branch)
        with patch.object(supervisor,'api',return_value=original):self.assertEqual(supervisor.read_run('series'),original)
        for key in ('id','head_sha','head_branch','path'):
            wrong=dict(original);wrong[key]='wrong'
            with self.subTest(field=key),patch.object(supervisor,'api',return_value=wrong),self.assertRaisesRegex(StrategyError,'UNEXPECTED_RUN_OR_SOURCE'):
                supervisor.read_run('series')

    def test_job_listing_covers_more_than_one_hundred_jobs_and_binds_the_attempt(self):
        run=dict(id=999,run_attempt=3)
        with patch.object(supervisor,'api',side_effect=[dict(jobs=[dict(id=i) for i in range(100)]),dict(jobs=[dict(id=100)])]) as api:
            result=supervisor.read_jobs(run)
        self.assertEqual(len(result),101)
        self.assertIn('attempts/3/jobs?per_page=100&page=2',api.call_args.args[0])

    def episode(self):
        runs={key:dict(id=int(value[0]),run_attempt=1,status='in_progress',conclusion=None) for key,value in supervisor.RUNS.items()}
        run,jobs,logs=failed_wait();runs['series']=run
        def read_jobs(value):return jobs if str(value['id'])==supervisor.RUNS['series'][0] else []
        return runs,read_jobs,logs

    def test_read_only_supervision_plans_a_verified_wait_retry_without_sending_it(self):
        runs,jobs,logs=self.episode()
        with patch.object(supervisor,'read_run',side_effect=lambda key:runs[key]),patch.object(supervisor,'read_jobs',side_effect=jobs),\
             patch.object(supervisor,'api',return_value=logs[123]) as api,patch.object(supervisor,'prerequisite_ready',return_value=True):
            result=supervisor.once({})
        self.assertEqual(len(result['retry_actions']),1);self.assertFalse(result['retry_actions'][0]['applied'])
        self.assertEqual(result['retries_requested'],[])
        self.assertTrue(all(call.kwargs.get('method') is None for call in api.call_args_list))

    def test_retry_posts_only_the_known_wait_job_and_is_idempotent_within_the_same_attempt(self):
        runs,jobs,logs=self.episode()
        with patch.dict(os.environ,dict(GITHUB_ACTIONS='true',GITHUB_REPOSITORY=REPOSITORY)),\
             patch.object(supervisor,'read_run',side_effect=lambda key:runs[key]),patch.object(supervisor,'read_jobs',side_effect=jobs),\
             patch.object(supervisor,'api',return_value=logs[123]) as api,patch.object(supervisor,'prerequisite_ready',return_value=True):
            result=supervisor.once({},apply=True);again=supervisor.once(result,apply=True)
        posts=[call for call in api.call_args_list if call.kwargs.get('method')=='POST']
        self.assertEqual(len(posts),1);self.assertEqual(posts[0].args[0],'actions/jobs/123/rerun')
        self.assertTrue(result['retry_actions'][0]['applied']);self.assertEqual(again['retry_actions'],[])

    def test_apply_requires_the_owned_actions_environment(self):
        with patch.dict(os.environ,dict(GITHUB_ACTIONS='false',GITHUB_REPOSITORY=REPOSITORY)),patch.object(supervisor,'api') as api,\
             self.assertRaisesRegex(StrategyError,'OWNED_GITHUB_ACTIONS'):
            supervisor.once({},apply=True)
        api.assert_not_called()

    def test_green_workflow_without_checked_final_receipt_is_not_102_complete(self):
        runs,_,_=self.episode()
        for value in runs.values():value.update(status='completed',conclusion='success')
        with patch.object(supervisor,'read_run',side_effect=lambda key:runs[key]),patch.object(supervisor,'read_jobs',return_value=[]),\
             patch.object(supervisor,'verify_final',side_effect=StrategyError('FINAL_RECEIPT_MISSING')),self.assertRaisesRegex(StrategyError,'FINAL_RECEIPT'):
            supervisor.once({})

    def test_complete_102_is_reported_only_with_the_verified_final_delivery(self):
        runs,_,_=self.episode()
        for value in runs.values():value.update(status='completed',conclusion='success')
        proof=dict(status='PASS',complete_models=102,pppoker_windows_validated=False)
        with patch.object(supervisor,'read_run',side_effect=lambda key:runs[key]),patch.object(supervisor,'read_jobs',return_value=[]),\
             patch.object(supervisor,'verify_final',return_value=proof) as verify:
            result=supervisor.once({})
        verify.assert_called_once();self.assertTrue(result['done']);self.assertEqual(result['status'],'COMPLETE_102')
        self.assertFalse(result['pppoker_windows_validated'])

    def test_network_retry_distinguishes_temporary_errors_from_permission_or_application_errors(self):
        self.assertTrue(supervisor.transient_api_error(subprocess.TimeoutExpired('gh',60)))
        for message in ('HTTP 429','HTTP 503','API rate limit exceeded (HTTP 403)'):
            self.assertTrue(supervisor.transient_api_error(subprocess.CalledProcessError(1,'gh',stderr=message)))
        for message in ('Resource not accessible by integration (HTTP 403)','HTTP 422','HTTP 404'):
            self.assertFalse(supervisor.transient_api_error(subprocess.CalledProcessError(1,'gh',stderr=message)))

    def test_existing_output_is_preserved_before_any_github_access(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel=Path(temp)/'preserve.txt';sentinel.write_text('preserve')
            with patch.object(supervisor,'once') as once,self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                supervisor.main(['--output',temp,'--once'])
            once.assert_not_called();self.assertEqual(sentinel.read_text(),'preserve')


if __name__=='__main__':unittest.main()
