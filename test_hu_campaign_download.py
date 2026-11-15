"""Pin native models, reject changed inventories and transfer exact contexts."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from strategy.batch_archive import make_catalog
from strategy.batch_jobs import case_id
from strategy.campaign_download import CLOSE32_TAG,PLANS,combine_thirty_two,load_campaign
from strategy.state_contract import StrategyError

HERE=Path(__file__).parent


class CampaignDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads((HERE/'docs/software-hu-close32-sb40-20261115/close32-plan.json').read_text())
        cls.old=json.loads((HERE/'docs/software-hu-next16-20261115/published/batch-catalog-43764947533.json').read_text())

    def fixtures(self):
        rows=[];assets=[dict(id=1,state='uploaded',name='batch-catalog-123.json')]
        for case in self.plan['cases']:
            part=dict(name='case-'+str(case['ordinal'])+'.zip.part001',bytes=100,sha256='a'*64)
            rows.append(dict(case,schema='software.hu-batch-case.v1',plan_sha256=self.plan['plan_sha256'],
                native_target_met=True,global_gap_bb=.04,tag=CLOSE32_TAG,policy_sha256='b'*64,file_sha256='c'*64,
                policy_file_bytes=200,archive_bytes=100,archive_sha256='a'*64,parts=[part],
                coverage=dict(structurally_complete=True),lookup_streets=['flop','turn','river']))
            assets.append(dict(name=part['name'],size=100,state='uploaded',digest='sha256:'+'a'*64))
        catalog=make_catalog(self.plan,rows)
        def receive(url):
            if url.endswith(PLANS[CLOSE32_TAG][0]):return copy.deepcopy(self.plan)
            if url.endswith('/batch-catalog-123.json'):return copy.deepcopy(catalog)
            return dict(assets=copy.deepcopy(assets))
        return catalog,assets,receive

    def test_download_catalog_is_bound_to_pinned_plan_and_actual_remote_parts(self):
        _,_,receive=self.fixtures()
        with patch('strategy.campaign_download.read_json',side_effect=receive):
            c,name=load_campaign(CLOSE32_TAG,'batch-catalog-123.json')
        self.assertEqual((len(c['cases']),name),(15,'batch-catalog-123.json'))

    def test_complete_label_does_not_hide_changed_position_or_missing_data(self):
        catalog,assets,receive=self.fixtures();original=receive
        def wrong(url):
            result=original(url)
            if url.endswith('/batch-catalog-123.json'):result['context']['positions']=['SB','BB']
            return result
        with patch('strategy.campaign_download.read_json',side_effect=wrong):
            with self.assertRaisesRegex(StrategyError,'GEOMETRY_DIFFER'):load_campaign(CLOSE32_TAG)

    def test_32_merge_requires_exact_previous_policy_and_file_identities(self):
        c,_,_=self.fixtures();c['_original_plan']=self.plan
        pilot=dict(self.plan['preexisting_models'][0],ordinal=0)
        pilot['case_id']=case_id(pilot['board'])
        merged=combine_thirty_two(c,self.old,pilot)
        self.assertEqual(len(merged['cases']),32)
        self.assertEqual([r['ordinal'] for r in merged['cases']],list(range(1,33)))
        changed=copy.deepcopy(self.old);changed['cases'][0]['policy_sha256']='0'*64
        with self.assertRaisesRegex(StrategyError,'SEVENTEEN_MODELS_CHANGED'):combine_thirty_two(c,changed,pilot)

    def test_changed_remote_part_is_rejected_before_any_gigabyte_download(self):
        _,_,receive=self.fixtures();original=receive
        def wrong(url):
            value=original(url)
            if '/api.' in url:value['assets'][-1]['digest']='sha256:'+'0'*64
            return value
        with patch('strategy.campaign_download.read_json',side_effect=wrong):
            with self.assertRaisesRegex(StrategyError,'REMOTE_REFERENCE_PART_NOT_VERIFIED'):load_campaign(CLOSE32_TAG)


if __name__=='__main__':unittest.main()
