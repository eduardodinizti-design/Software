import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from visualpilot.agent.laboratory import LaboratoryRangeBook
from visualpilot.agent.strategy import RangeCoachStrategy
from visualpilot.agent.connector import canonical_hand

class LaboratoryRangeTests(unittest.TestCase):
    def test_versioned_ranges_for_each_street_and_exact_context(self):
        with tempfile.TemporaryDirectory() as folder:
            states=[]
            for street,board in [('preflop',[]),('flop',['2h','3d','4s']),('turn',['2h','3d','4s','5c']),('river',['2h','3d','4s','5c','9d'])]:
                states.append(dict(street=street,hero=['As','Ks'],board=board,position='BTN',effective_stack_bb=30,pot_bb=4,action_history=[]))
            data=dict(schema_version=1,source='fictitious-test-policy',version='test-1',entries=[dict(state=s,options=[dict(action='check',frequency=1)]) for s in states])
            path=Path(folder)/'policy.json';path.write_text(json.dumps(data))
            book=LaboratoryRangeBook(path);strategy=RangeCoachStrategy(None,book)
            for state in states:
                context=dict(state,laboratory=True,fictional=True,
                    observation=dict(table='test',generation=1,frame_sha256='a'*64))
                result=strategy.theoretical_action(state,context)
                self.assertEqual(result['status'],'found')
                self.assertEqual(result['provenance']['version'],'test-1')
                self.assertEqual(len(result['provenance']['sha256']),64)
                self.assertEqual(strategy.theoretical_action(state,dict(context,pot_bb=99))['status'],'pending')
                self.assertEqual(strategy.theoretical_action(state,dict(context,laboratory=False))['status'],'pending')
                self.assertEqual(strategy.theoretical_action(dict(state,hero=['As','As']),context)['status'],'pending')
            data['entries'][0]['options'][0]['frequency']=.8;path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):LaboratoryRangeBook(path)

    def test_unknown_and_postflop_never_query_preflop_backend(self):
        connector=Mock();strategy=RangeCoachStrategy(connector)
        for street,board in [(None,[]),('flop',['2h','3h','4h']),('turn',['2h','3h','4h','5h']),('river',['2h','3h','4h','5h','6h'])]:
            self.assertEqual(strategy.theoretical_action(dict(hero=['As','Ks'],street=street,board=board),dict(position='BTN'))['status'],'pending')
        connector.lookup_range.assert_not_called()
        with self.assertRaises(ValueError):canonical_hand(['As','As'])
