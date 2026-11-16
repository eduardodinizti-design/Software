"""Publication counterexamples use the previous actual Windows receipts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from strategy.state_contract import StrategyError
from tools.finalize_hu_sb40_complete34 import checked_root_review,main as finalize
from tools.verify_hu_sb40_complete34_publication import main as verify_publication


class SB40Delivery34Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=Path(__file__).parent/'docs/software-hu-sb40-next16-20261116/published/entrega-sb40-next16-43796410882-a1.json'
        cls.rows=json.loads(p.read_text())['windows_cases']

    def test_actual_previous_windows_root_receipts_pass_the_same_numeric_contract(self):
        for row in self.rows:
            with self.subTest(board=row['board']):checked_root_review(row)

    def test_different_board_policy_position_or_modified_policy_cannot_be_relabelled_as_verified(self):
        for field,value in (('source_policy_sha256','f'*64),('board',['2c','2d','2h']),
                ('actor_position','BB'),('policy_modified',True),('method','NAIVE_UNWEIGHTED_AVERAGE')):
            row=copy.deepcopy(self.rows[0]);row['root_policy_review'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'ROOT_REVIEW'):
                checked_root_review(row)

    def test_nonfinite_negative_and_unnormalized_mix_is_never_a_publication_pass(self):
        for value in (float('nan'),float('inf'),-.01,1.2,.12345):
            row=copy.deepcopy(self.rows[0]);row['root_policy_review']['actions'][0]['frequency']=value
            with self.subTest(value=value),self.assertRaisesRegex(StrategyError,'ROOT_REVIEW'):
                checked_root_review(row)

    def test_catalog_from_another_run_is_refused_before_creating_any_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'must-not-be-created'
            with self.assertRaisesRegex(StrategyError,'ACTUAL_NATIVE_WORKFLOW'):
                finalize(['--catalog-asset','batch-catalog-111.json','--native-run','222','--output',str(output)])
            self.assertFalse(output.exists())

    def test_existing_publication_folder_is_preserved_before_network_or_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            sentinel=Path(temp)/'existing.txt';sentinel.write_text('preserve local work')
            with self.assertRaisesRegex(StrategyError,'OUTPUT_MUST_BE_NEW'):
                verify_publication(['--run','111','--catalog-asset','batch-catalog-111.json','--output',temp])
            self.assertEqual(sentinel.read_text(),'preserve local work')


if __name__=='__main__':unittest.main()
