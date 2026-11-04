import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from visualpilot.lab.tournament_purchases import Offer,Rules,PurchaseLedger,parse_addon_popup


class PurchaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'lab.sqlite'
        self.ledger=PurchaseLedger(self.path);self.ledger.register('T1','10',True)
        self.offer=Offer('T1','popup1','addon','5',10000,250,True)
        self.rules=Rules('20')

    def tearDown(self): self.ledger.close();self.temp.cleanup()

    def test_addon_has_separate_bb_policy(self):
        result=self.ledger.reserve(self.offer,self.rules)
        self.assertTrue(result['should_execute']);self.assertEqual(result['received_bb'],40)
        self.assertEqual(self.ledger.reserve(replace(self.offer,kind='rebuy',offer_id='r'),self.rules)['reason'],
                         'received_bb_below_minimum')

    def test_rebuy_boundary_and_limit_are_persistent(self):
        rebuy=replace(self.offer,kind='rebuy',big_blind=200)
        result=self.ledger.reserve(rebuy,self.rules)
        self.assertTrue(result['should_execute'])
        self.ledger.confirm(result['token'],'T1','rebuy','5',10000,True)
        self.ledger.close();self.ledger=PurchaseLedger(self.path)
        result=self.ledger.reserve(replace(rebuy,offer_id='another'),self.rules)
        self.assertEqual(result['reason'],'one_purchase_per_kind')

    def test_unknown_outcome_and_repeated_popup_do_not_retry(self):
        first=self.ledger.reserve(self.offer,self.rules)
        second=self.ledger.reserve(self.offer,self.rules)
        self.assertEqual(first['token'],second['token']);self.assertFalse(second['should_execute'])
        self.ledger.close();self.ledger=PurchaseLedger(self.path)
        self.assertFalse(self.ledger.reserve(self.offer,self.rules)['should_execute'])
        self.assertEqual(self.ledger.reserve(replace(self.offer,offer_id='new'),self.rules)['reason'],'one_purchase_per_kind')

    def test_budget_counts_entry_rebuy_and_addon(self):
        self.ledger.reserve(self.offer,self.rules)
        rebuy=replace(self.offer,kind='rebuy',offer_id='r',big_blind=200,price='6')
        self.assertEqual(self.ledger.reserve(rebuy,self.rules)['reason'],'budget_exceeded')
        self.assertTrue(self.ledger.reserve(replace(rebuy,price='5'),self.rules)['should_execute'])

    def test_concurrent_reservations_only_one_executes(self):
        def run(i):
            ledger=PurchaseLedger(self.path)
            try:return ledger.reserve(replace(self.offer,offer_id=str(i)),self.rules)
            finally:ledger.close()
        with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(run,range(2)))
        self.assertEqual(sum(r['should_execute'] for r in results),1)

    def test_receipt_mismatch_rejection_and_retry(self):
        result=self.ledger.reserve(self.offer,self.rules)
        with self.assertRaises(ValueError):self.ledger.confirm(result['token'],'WRONG','addon','5',10000,True)
        self.assertFalse(self.ledger.reserve(self.offer,self.rules)['should_execute'])
        self.ledger.confirm(result['token'],'T1','addon','5',10000,False)
        self.assertTrue(self.ledger.reserve(replace(self.offer,offer_id='fresh'),self.rules)['should_execute'])
        with self.assertRaises(ValueError):self.ledger.confirm(result['token'],'T1','addon','5',10000,True)

    def test_pause_closed_offer_non_lab_and_unreadable_data(self):
        self.assertFalse(self.ledger.reserve(self.offer,replace(self.rules,enabled=False))['should_execute'])
        self.assertFalse(self.ledger.reserve(replace(self.offer,open=False),self.rules)['should_execute'])
        for changed in (replace(self.offer,play_money_verified=False),replace(self.offer,source='live'),
                        replace(self.offer,big_blind=0),replace(self.offer,price='nan')):
            with self.assertRaises(ValueError):self.ledger.reserve(changed,self.rules)

    def test_strict_popup_detection(self):
        rows=[([],text,.99) for text in ('ADD-ON','Custo: 5 fichas ficticias','Receber: 10000 fichas','Comprar add-on')]
        self.assertEqual(parse_addon_popup(rows)['status'],'observed')
        self.assertFalse(parse_addon_popup(rows)['executable'])
        self.assertEqual(parse_addon_popup(rows[:-1])['status'],'pending')
        self.assertEqual(parse_addon_popup(rows+[rows[1]])['status'],'pending')
        rows[1]=([],rows[1][1],.3)
        self.assertEqual(parse_addon_popup(rows)['status'],'pending')
