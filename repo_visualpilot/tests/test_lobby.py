from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import tempfile
import threading
from time import monotonic
import unittest

import cv2
import numpy as np

from visualpilot.lab.lobby import (buyin_total, parse_card, segment_cards, filter_cards,
                                  LobbyRules, LobbyHistory, open_next_tournament,
                                  obter_torneios_validos, validar_detalhes, clicar_posicao)
from visualpilot.lab.registration import RegistrationLedger, LabControl


def rows(tournament='T1', price='10', status='ABERTO'):
    texts=[f'Torneio: {tournament}','Nome: DIAMANTE','Tipo: MTT',
           f'Buy-in: {price} fichas ficticias','Stack: 10000','Inicio: 20:30']
    if status is not None:texts.append('Registro: '+status)
    return [([],text,.99) for text in texts]


class LobbyParsingTests(unittest.TestCase):
    def test_all_fees_decimal_comma_and_boundary(self):
        self.assertEqual(buyin_total('28.34 + 14.16 + 7.5'),Decimal('50.00'))
        self.assertEqual(buyin_total('28,34+14,16+7,50'),Decimal('50.00'))
        parsed=parse_card(rows(price='50+0.01'))
        self.assertEqual(filter_cards([parsed],LobbyRules())['cards'][0]['rejection'],'buyin_limit')
        self.assertTrue(filter_cards([parse_card(rows(price='28,34+14,16+7,50'))],LobbyRules())['eligible'])

    def test_unknown_closed_and_scheduled_status_are_never_assumed_open(self):
        for status in (None,'ATIVOS','ENCERRADO','EM BREVE'):
            card=parse_card(rows(status=status))
            self.assertFalse(filter_cards([card],LobbyRules())['eligible'])
        self.assertEqual(parse_card(rows(status=None))['registration'],'unknown')

    def test_invalid_prices_and_other_currency_remain_unreadable(self):
        for price in ('5O','5 0','50+','50/100','1.000','-10','10+taxa','NaN'):
            self.assertFalse(parse_card(rows(price=price))['readable'],price)
        sample=rows();sample[3]=([], 'Buy-in: 10 reais',.99)
        self.assertFalse(parse_card(sample)['readable'])

    def test_wrapped_cost_only_joins_adjacent_price_continuations(self):
        sample=rows();sample[3:4]=[([], 'Buy-in: 28,34 +',.99),([], '14,16 + 7,50 fichas ficticias',.99)]
        self.assertEqual(parse_card(sample)['buyin'],'50.00')
        sample[3:5]=[([], 'Buy-in: 5',.99),([], '0 fichas ficticias',.99)]
        self.assertFalse(parse_card(sample)['readable'])
        sample=rows();sample[3:4]=[([], 'Buy-in: 10 +',.99),([], '20 fichas ficticias',float('nan'))]
        self.assertFalse(parse_card(sample)['readable'])
        sample=rows();sample.insert(4,([], 'Buy-in: 20 fichas ficticias',.99))
        self.assertFalse(parse_card(sample)['readable'])

    def test_confidence_duplicates_filters_and_four_candidates(self):
        sample=rows();sample[-1]=([],sample[-1][1],.94)
        self.assertFalse(parse_card(sample)['readable'])
        card=parse_card(rows())
        self.assertFalse(filter_cards([card,card],LobbyRules())['eligible'])
        for rules in (LobbyRules(targets=('T2',)),LobbyRules(allowed_types=('SNG',)),LobbyRules(minimum_stack=20000)):
            self.assertFalse(filter_cards([card],rules)['eligible'])
        result=filter_cards([parse_card(rows(tournament=f'T{i}')) for i in range(5)],LobbyRules())
        self.assertEqual(len(result['eligible']),4)
        self.assertEqual(result['cards'][-1]['rejection'],'candidate_limit')
        with self.assertRaises(ValueError):LobbyRules(max_buyin='100').validate()

    def test_variable_height_segmentation_origin_and_partial_card(self):
        image=np.full((900,700,3),255,np.uint8)
        cv2.rectangle(image,(20,30),(650,240),(170,123,66),2)
        cv2.rectangle(image,(40,270),(630,610),(170,123,66),2)
        cv2.rectangle(image,(20,650),(650,1000),(170,123,66),2)
        found=segment_cards(image,origin=(-700,100))
        self.assertEqual(len(found),2)
        self.assertNotEqual(found[0]['box'][3],found[1]['box'][3])
        for card in found:
            self.assertEqual(card['box'][0],card['local_box'][0]-700)
            self.assertEqual(card['box'][1],card['local_box'][1]+100)
        self.assertEqual(segment_cards(np.full_like(image,255)),[])


class Adapter:
    def __init__(self):
        self.actions=[];self.last_error=None;self.hook=lambda sample:None
        self.detail_rows=rows();self.fail=False

    def sync_control(self):pass

    def capture_lobby(self):
        sample=dict(source='laboratory',observed=monotonic(),image='lobby.png',revision=1,
                    cards=[dict(parse_card(rows()),point=[30,40],box=[10,20,40,40])])
        self.hook(sample);return sample

    def open_card(self,card,revision):
        if self.fail:self.last_error='lobby_changed_before_click';return False
        self.actions.append(card['tournament']);return True

    def capture_details(self):
        return dict(source='laboratory',observed=monotonic(),rows=self.detail_rows)


class LobbyFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'lab.sqlite'
        self.ledger=RegistrationLedger(self.path);self.history=LobbyHistory(self.ledger)
        self.control=LabControl();self.adapter=Adapter();self.rules=LobbyRules()

    def tearDown(self):self.ledger.close();self.temp.cleanup()

    def run_flow(self):return open_next_tournament(self.adapter,self.history,self.rules,self.control)

    def test_helpers_return_capture_and_scan_without_clicking(self):
        sample, scan=obter_torneios_validos(self.adapter,self.history,self.rules)
        self.assertEqual(scan['eligible'][0]['tournament'],'T1')
        self.assertEqual(sample['revision'],1)
        self.assertFalse(self.adapter.actions)
        self.assertEqual(self.ledger.db.execute("SELECT COUNT(*) FROM audit WHERE event='lobby_scan'").fetchone()[0],1)

    def test_helper_details_reject_name_substring_and_different_id(self):
        selected=parse_card(rows())
        sample=dict(source='laboratory',observed=monotonic(),rows=rows())
        self.assertEqual(validar_detalhes(selected,sample)['tournament'],'T1')
        for index,text in ((0,'Torneio: T2'),(1,'Nome: DIAMANTE ESPECIAL')):
            changed=rows();changed[index]=([],text,.99)
            with self.assertRaises(ValueError):validar_detalhes(selected,dict(sample,rows=changed))

    def test_helper_details_reject_expired_and_non_lab_capture(self):
        selected=parse_card(rows())
        sample=dict(source='laboratory',observed=monotonic(),rows=rows())
        for changes in (dict(observed=monotonic()-6),dict(source='desktop')):
            with self.assertRaises(ValueError):validar_detalhes(selected,dict(sample,**changes))

    def test_helper_click_reject_isolated_or_tampered_coordinates(self):
        sample,scan=obter_torneios_validos(self.adapter,self.history,self.rules)
        selected=scan['eligible'][0]
        for bad in ((30,40),dict(selected,point=[300,400]),dict(selected,tournament='T2')):
            with self.assertRaises(ValueError):
                clicar_posicao(self.adapter,bad,sample,self.control,self.control.revision)
        self.assertFalse(self.adapter.actions)
        self.assertTrue(clicar_posicao(self.adapter,selected,sample,self.control,self.control.revision))

    def test_helper_click_reject_pause_and_expiry(self):
        sample,scan=obter_torneios_validos(self.adapter,self.history,self.rules)
        selected=scan['eligible'][0];revision=self.control.revision
        self.control.set_mode('manual')
        with self.assertRaises(ValueError):clicar_posicao(self.adapter,selected,sample,self.control,revision)
        self.control.set_mode('automatic')
        with self.assertRaises(ValueError):
            clicar_posicao(self.adapter,selected,sample,self.control,self.control.revision,clock=lambda:sample['observed']+6)
        self.assertFalse(self.adapter.actions)

    def test_open_once_recheck_details_and_persist_after_restart(self):
        result=self.run_flow();self.assertEqual(result['status'],'opened');self.assertFalse(result['registered'])
        self.ledger.close();self.ledger=RegistrationLedger(self.path);self.history=LobbyHistory(self.ledger)
        self.assertEqual(self.run_flow()['status'],'empty');self.assertEqual(self.adapter.actions,['T1'])
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM registrations').fetchone()[0],0)

    def test_wrong_details_stay_unknown_and_never_register_or_retry(self):
        self.adapter.detail_rows=rows(price='60')
        self.assertEqual(self.run_flow()['status'],'unknown')
        self.assertEqual(self.run_flow()['status'],'empty')
        self.assertEqual(self.adapter.actions,['T1'])

    def test_pause_and_expired_snapshot_do_not_click(self):
        self.adapter.hook=lambda sample:self.control.set_mode('manual')
        self.assertEqual(self.run_flow()['status'],'blocked');self.assertEqual(self.adapter.actions,[])
        self.control.set_mode('automatic')
        self.adapter.hook=lambda sample:sample.update(observed=monotonic()-10)
        self.assertEqual(self.run_flow()['status'],'blocked');self.assertEqual(self.adapter.actions,[])

    def test_reordered_list_cancels_and_keeps_history(self):
        self.adapter.fail=True
        self.assertEqual(self.run_flow()['reason'],'lobby_changed_before_click')
        self.assertEqual(self.run_flow()['status'],'empty')
        self.assertEqual(self.adapter.actions,[])

    def test_registered_and_pending_tournaments_are_excluded(self):
        self.ledger.register('T1','10',False)
        self.assertEqual(self.run_flow()['status'],'empty')
        self.assertEqual(self.adapter.actions,[])

    def test_concurrent_history_claims_open_only_once(self):
        selection=parse_card(rows())
        def claim(_):
            ledger=RegistrationLedger(self.path)
            try:return LobbyHistory(ledger).claim(selection)
            finally:ledger.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(claim,range(2)))
        self.assertEqual(sum(row['status']=='opening' for row in results),1)

    def test_manual_takeover_during_claim_cancels_before_navigation(self):
        original=self.history.claim
        def claim(selection):
            worker=threading.Thread(target=self.control.set_mode,args=('manual',),daemon=True)
            worker.start();worker.join(1)
            self.assertFalse(worker.is_alive())
            return original(selection)
        self.history.claim=claim
        self.assertEqual(self.run_flow()['status'],'unknown')
        self.assertEqual(self.adapter.actions,[])

    def test_expiry_during_claim_is_checked_again_before_navigation(self):
        original=self.history.claim;offset=[0]
        def claim(selection):
            result=original(selection);offset[0]=6;return result
        self.history.claim=claim
        result=open_next_tournament(self.adapter,self.history,self.rules,self.control,clock=lambda:monotonic()+offset[0])
        self.assertEqual(result['status'],'unknown');self.assertEqual(self.adapter.actions,[])
