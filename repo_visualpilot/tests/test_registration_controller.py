from pathlib import Path
import tempfile
import threading
from time import monotonic
import unittest

from visualpilot.lab.lobby import parse_card
from visualpilot.lab.registration import LabControl, RegistrationLedger, RegistrationRules
from visualpilot.lab.registration_controller import RegistrationController


def rows(price='28.34+14.16+7.50', id='T1'):
    return [([], text, .99) for text in [
        'LABORATORIO FICTICIO', f'Torneio: {id}', 'Nome: CORUJAO', 'Tipo: MTT',
        f'Buy-in: {price} fichas ficticias', 'Stack: 20000', 'Inicio: 22:00',
        'Registro: ABERTO', 'Oferta: O1', 'Bounty: SIM']]


class Adapter:
    def __init__(self):
        self.actions=[]; self.last_error=None; self.token=None; self.hook=lambda stage,sample:None
        self.price='28.34+14.16+7.50'; self.receipt_amount=50; self.reject=False
        self.failed=None; self.after_action=lambda action:None

    def sync_control(self): pass

    def sample(self, values):
        return dict(rows=values, source='laboratory', observed=monotonic(), revision=1,
                    image='test.png', receipt_token=self.token)

    def capture_lobby(self):
        sample=self.sample(rows(self.price))
        sample['cards']=[dict(parse_card(sample['rows']),point=[50,50],box=[0,0,100,100])]
        return sample

    def open_card(self, card, revision):
        self.actions.append('details');return True

    def capture_details(self): return self.sample(rows(self.price))

    def capture_stage(self, stage):
        values=rows(self.price)
        if stage=='receipt':
            values=[([], text,.99) for text in ['LABORATORIO FICTICIO','Torneio: T1','Oferta: O1',
                f'Custo: {self.receipt_amount} fichas ficticias','Inscricao: '+('RECUSADA' if self.reject else 'CONFIRMADA')]]
        sample=self.sample(values);self.hook(stage,sample);return sample

    def apply_step(self, action, revision, token):
        if self.failed==action:
            self.last_error='replaced';return False
        self.token=token;self.actions.append(action);self.after_action(action);return True


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'ledger.sqlite'
        self.ledger=RegistrationLedger(self.path);self.control=LabControl();self.adapter=Adapter()
        self.rules=RegistrationRules(targets=('T1',))
        self.controller=RegistrationController(self.adapter,self.ledger,self.rules,self.control)

    def tearDown(self): self.ledger.close();self.temp.cleanup()

    def test_full_flow_and_persistent_no_duplicate(self):
        result=self.controller.execute_cycle();self.assertEqual(result['status'],'confirmed')
        self.assertEqual(self.adapter.actions,['details','open_modal','confirm'])
        self.assertEqual(self.ledger.db.execute('SELECT entry_cost FROM tournaments').fetchone()[0],'50')
        self.ledger.close();self.ledger=RegistrationLedger(self.path)
        controller=RegistrationController(self.adapter,self.ledger,self.rules,self.control)
        self.assertEqual(controller.execute_cycle()['status'],'empty')
        self.assertEqual(len(self.adapter.actions),3)

    def test_missing_receipt_remains_reserved_and_never_retries(self):
        self.adapter.hook=lambda stage,sample: sample.update(rows=[]) if stage=='receipt' else None
        self.assertEqual(self.controller.execute_cycle()['status'],'unknown')
        self.assertEqual(self.ledger.db.execute('SELECT status FROM registrations').fetchone()[0],'reserved')
        self.assertEqual(self.controller.execute_cycle()['status'],'empty')
        self.assertEqual(self.adapter.actions.count('confirm'),1)

    def test_changed_modal_and_wrong_receipt(self):
        self.adapter.hook=lambda stage,sample: sample.update(rows=rows('40')) if stage=='modal' else None
        self.assertEqual(self.controller.execute_cycle()['status'],'blocked')
        self.assertNotIn('confirm',self.adapter.actions)

    def test_wrong_receipt_amount_is_unknown(self):
        self.adapter.receipt_amount=40
        self.assertEqual(self.controller.execute_cycle()['status'],'unknown')
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0],0)

    def test_uncorrelated_receipt_is_unknown(self):
        self.adapter.hook=lambda stage,sample: sample.update(receipt_token='other') if stage=='receipt' else None
        self.assertEqual(self.controller.execute_cycle()['status'],'unknown')

    def test_manual_during_ocr_blocks_confirmation(self):
        self.adapter.hook=lambda stage,sample: self.control.set_mode('manual') if stage=='modal' else None
        self.assertEqual(self.controller.execute_cycle()['status'],'blocked')
        self.assertNotIn('confirm',self.adapter.actions)

    def test_manual_after_submission_still_records_receipt(self):
        self.adapter.after_action=lambda action:self.control.set_mode('manual') if action=='confirm' else None
        self.assertEqual(self.controller.execute_cycle()['status'],'confirmed')

    def test_pause_before_cycle_and_resume_requires_new_capture(self):
        self.controller.set_mode('paused')
        self.assertEqual(self.controller.execute_cycle()['status'],'blocked')
        self.assertFalse(self.adapter.actions)
        self.controller.set_mode('automatic')
        self.assertEqual(self.controller.execute_cycle()['status'],'confirmed')

    def test_known_no_click_releases_reservation_as_rejected(self):
        self.adapter.failed='confirm'
        self.assertEqual(self.controller.execute_cycle()['status'],'blocked')
        self.assertEqual(self.ledger.db.execute('SELECT status FROM registrations').fetchone()[0],'rejected')

    def test_explicit_rejection_not_registered(self):
        self.adapter.reject=True
        self.assertEqual(self.controller.execute_cycle()['status'],'rejected')
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM tournaments').fetchone()[0],0)

    def test_fractional_cost_not_truncated_and_high_limit_rejected(self):
        self.adapter.price='49.99'
        self.assertEqual(self.controller.execute_cycle()['status'],'blocked')
        self.assertNotIn('open_modal',self.adapter.actions)
        with self.assertRaises(ValueError):
            RegistrationController(self.adapter,self.ledger,RegistrationRules(targets=('T1',),max_entry_cost=100),self.control)

    def test_four_uncertain_reservations_block_fifth(self):
        for index in range(2,6):
            id=f'T{index}'
            popup=dict(tournament=id,offer='O1',kind='MTT',bounty=False,amount=10,stack=10000,minimum=10,maximum=10,step=1)
            self.ledger.reserve_entry(popup,RegistrationRules(targets=(id,)),10)
        result=self.controller.execute_cycle()
        self.assertEqual(result['reason'],'simultaneous_limit')
        self.assertNotIn('confirm',self.adapter.actions)

    def test_takeover_during_database_wait_is_not_locked_out(self):
        reserve=self.ledger.reserve_entry
        def wrapped(*args):
            result=reserve(*args)
            thread=threading.Thread(target=lambda:self.control.set_mode('manual'))
            thread.start();thread.join(1);self.assertFalse(thread.is_alive())
            return result
        self.ledger.reserve_entry=wrapped
        self.assertEqual(self.controller.execute_cycle()['status'],'unknown')
        self.assertNotIn('confirm',self.adapter.actions)

    def test_expired_after_reservation_never_clicks(self):
        reserve=self.ledger.reserve_entry
        def wrapped(*args):
            result=reserve(*args);self.controller.clock=lambda:monotonic()+10;return result
        self.ledger.reserve_entry=wrapped
        self.assertEqual(self.controller.execute_cycle()['status'],'unknown')
        self.assertNotIn('confirm',self.adapter.actions)

    def test_second_simultaneous_cycle_does_not_capture(self):
        self.controller.running.acquire()
        try:
            self.assertEqual(self.controller.execute_cycle()['reason'],'cycle_already_running')
            self.assertFalse(self.adapter.actions)
        finally:self.controller.running.release()


if __name__=='__main__':unittest.main()
