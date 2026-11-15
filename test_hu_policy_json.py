"""JSON is lossless at the decision boundary and throughout every exported node."""
from dataclasses import asdict
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from strategy.action_tree import Action,apply_action
from strategy.batch_jobs import atomic_json
from strategy.policy_disk import DiskPolicy
from strategy.policy_json import export_complete,query,verify_export
from strategy.state_contract import BettingState,StrategyError
from strategy.texassolver_backend import file_hash
from test_hu_batches import disk_copy
from test_hu_operational import make_test_policy,RIVER,HERO


class PolicyJSONTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        source=make_test_policy(BettingState(RIVER,5.5,(22.5,22.5),actor=1,oop=1))
        result=disk_copy(source,self.root/'model.sqlite',native_matrix=True)
        self.policy=DiskPolicy(self.root/'model.sqlite',cache_nodes=1);self.addCleanup(self.policy.close)
        self.index=self.root/'library.json';atomic_json(self.index,dict(schema='software.hu-policy-library.v1',
            entries=[dict(board=list(RIVER[:3]),path='model.sqlite',file_sha256=file_hash(self.root/'model.sqlite'),
                policy_sha256=result['policy_sha256'])]))

    def test_json_decision_uses_the_same_stored_frequencies_and_sizes(self):
        state=apply_action(self.policy.root,Action('check'))
        request=dict(context=asdict(self.policy.context),state=state.to_dict(),hero_cards=HERO,table_id='t',hand_id='h')
        response=query(self.index,json.loads(json.dumps(request)));decision=response['decision']
        self.assertEqual([a['frequency'] for a in decision['candidates']],self.policy.probabilities(state,HERO))
        self.assertEqual([a['additional_bb'] for a in decision['candidates']],[a.amount_bb for a in self.policy.actions(state)])
        self.assertFalse(response['input_devices_used'])

    def test_wrong_context_is_not_silently_assumed_from_the_policy(self):
        state=apply_action(self.policy.root,Action('check'))
        context=asdict(self.policy.context);context['positions']=['SB','BB']
        with self.assertRaisesRegex(StrategyError,'CONTEXT_DIFFERS'):
            query(self.index,dict(context=context,state=state.to_dict(),hero_cards=HERO,table_id='t',hand_id='h'))

    def test_full_export_preserves_all_private_combo_frequencies_at_every_node(self):
        path=self.root/'full.jsonl.gz';report=export_complete(self.policy,path)
        self.assertEqual(report['public_nodes'],self.policy.node_count)
        self.assertTrue(verify_export(path,self.policy)['exactly_matches_stored_policy'])
        self.assertLessEqual(len(self.policy._cache),1)

    def test_repeated_node_cannot_hide_an_omitted_continuation(self):
        path=self.root/'full.jsonl.gz';export_complete(self.policy,path)
        with gzip.open(path,'rt') as f:rows=[json.loads(r) for r in f]
        rows[2]=rows[1]
        bad=self.root/'bad.jsonl.gz'
        with gzip.open(bad,'wt') as f:
            for r in rows:f.write(json.dumps(r)+'\n')
        with self.assertRaisesRegex(StrategyError,'NODE_FREQUENCIES_OR_SIZES_CHANGED'):verify_export(bad,self.policy)

    def test_existing_export_is_preserved(self):
        path=self.root/'already.jsonl.gz';path.write_bytes(b'existing-work')
        with self.assertRaisesRegex(StrategyError,'MUST_BE_NEW'):export_complete(self.policy,path)
        self.assertEqual(path.read_bytes(),b'existing-work')


if __name__=='__main__':unittest.main()
