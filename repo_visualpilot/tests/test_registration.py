from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
from time import monotonic
import unittest

from visualpilot.lab.registration import (RegistrationLedger, RegistrationRules, LabControl,
                                         adjust_and_register, parse_popup)


def popup_rows(amount=10, tournament='T1', offer='P1'):
    return [([], text, .99) for text in ('LABORATORIO FICTICIO', f'Torneio: {tournament}',
        f'Oferta: {offer}', 'Tipo: MTT', 'Bounty: SIM', f'Custo: {amount} fichas ficticias',
        'Stack: 10000', 'Minimo: 10', 'Maximo: 100', 'Passo: 5', 'Registrar')]


class Fixture:
    def __init__(self, amount=10):
        self.amount, self.revision = amount, 1
        self.actions = []
        self.token = None
        self.stuck = self.lost_receipt = False
        self.hook = lambda sample: None

    def capture(self):
        rows = popup_rows(self.amount)
        if self.token:
            rows = [r for r in rows if r[1].startswith(('LABORATORIO', 'Torneio:', 'Oferta:', 'Custo:'))]
            if not self.lost_receipt:
                rows.append(([], 'Inscricao: CONFIRMADA', .99))
        sample = dict(rows=rows, observed=monotonic(), revision=self.revision,
                      source='laboratory', receipt_token=self.token)
        self.hook(sample)
        return sample

    def apply(self, action, revision, token):
        if revision != self.revision:
            return False
        self.actions.append(action)
        if action == 'register':
            self.token = token
        elif not self.stuck:
            self.amount += 5 if action == 'increase' else -5
        self.revision += 1
        return True


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'ledger.sqlite'
        self.ledger = RegistrationLedger(self.path)
        self.rules = RegistrationRules(('T1', 'T2', 'T3', 'T4'))
        self.control = LabControl()

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def run_flow(self, fixture, **kwargs):
        return adjust_and_register(fixture, self.ledger, self.rules, 50, self.control, **kwargs)

    def test_increment_decrement_and_entry_cost_reaches_purchase_ledger(self):
        for start, action in ((40, 'increase'), (60, 'decrease')):
            with self.subTest(start=start):
                fixture = Fixture(start)
                if start == 60:
                    self.ledger.db.execute('DELETE FROM registrations')
                    self.ledger.db.execute('DELETE FROM tournaments')
                result = self.run_flow(fixture)
                self.assertEqual(result['status'], 'confirmed')
                self.assertEqual(fixture.actions, [action, action, 'register'])
                row = self.ledger.db.execute('SELECT * FROM tournaments').fetchone()
                self.assertEqual(row['entry_cost'], '50')
                self.assertEqual(row['bounty'], 1)

    def test_ambiguous_malformed_and_low_confidence_ocr_never_become_numbers(self):
        rows = popup_rows(25); rows[5] = ([], 'Custo:25fichas ficticias', .99)
        self.assertEqual(parse_popup(rows)['amount'], 25)
        for text in ('Custo: 5O fichas ficticias', 'Custo: 5 0 fichas ficticias',
                     'Custo: 50/100 fichas ficticias', 'Custo: -50 fichas ficticias',
                     'Custo: 5.0 fichas ficticias'):
            rows = popup_rows(); rows[5] = ([], text, .99)
            with self.assertRaises(ValueError): parse_popup(rows)
        for score in (.5, float('nan')):
            rows = popup_rows(); rows[5] = ([], rows[5][1], score)
            with self.assertRaises(ValueError): parse_popup(rows)
        with self.assertRaises(ValueError): parse_popup(popup_rows()+[popup_rows()[5]])
        with self.assertRaises(ValueError): parse_popup(popup_rows()+[([], 'Custo: 5O fichas ficticias', .5)])

    def test_failed_increment_does_not_click_again(self):
        fixture = Fixture(); fixture.stuck = True
        self.assertEqual(self.run_flow(fixture)['status'], 'blocked')
        self.assertEqual(fixture.actions, ['increase'])

    def test_step_limit_includes_final_read_without_extra_click(self):
        fixture = Fixture(40)
        self.assertEqual(self.run_flow(fixture, max_steps=1)['status'], 'blocked')
        self.assertEqual(fixture.actions, ['increase'])
        fixture = Fixture(45)
        self.assertEqual(self.run_flow(fixture, max_steps=1)['status'], 'confirmed')
        self.assertEqual(fixture.actions, ['increase', 'register'])

    def test_pause_manual_and_resume_during_ocr_cancel_old_action(self):
        for mode in ('paused', 'manual', 'automatic'):
            fixture = Fixture(50)
            fixture.hook = lambda _: self.control.set_mode(mode)
            self.assertEqual(self.run_flow(fixture)['status'], 'blocked')
            self.assertEqual(fixture.actions, [])
            self.control.set_mode('automatic')

    def test_stale_future_nonlab_and_replaced_popup_are_blocked(self):
        for fault in ('stale', 'future', 'external', 'replaced', 'different_offer'):
            fixture = Fixture(40)
            def inject(sample):
                if fault == 'stale': sample['observed'] -= 10
                if fault == 'future': sample['observed'] += 10
                if fault == 'external': sample['source'] = 'live'
                if fault == 'replaced': fixture.revision += 1
                if fault == 'different_offer' and fixture.actions: sample['rows'] = popup_rows(45, offer='P2')
            fixture.hook = inject
            self.assertEqual(self.run_flow(fixture)['status'], 'blocked')
            self.assertNotIn('register', fixture.actions)

    def test_unknown_receipt_survives_restart_and_cannot_register_twice(self):
        fixture = Fixture(50); fixture.lost_receipt = True
        result = self.run_flow(fixture)
        self.assertEqual(result['status'], 'unknown')
        self.ledger.close(); self.ledger = RegistrationLedger(self.path)
        next_fixture = Fixture(50)
        self.assertEqual(self.run_flow(next_fixture)['reason'], 'offer_already_seen')
        self.assertEqual(next_fixture.actions, [])
        row = self.ledger.db.execute('SELECT status FROM registrations').fetchone()
        self.assertEqual(row[0], 'reserved')

    def test_expiry_while_reserving_never_reaches_register_click(self):
        fixture = Fixture(50)
        offset = [0]
        original = self.ledger.reserve_entry
        def reserve(*args):
            result = original(*args)
            offset[0] = 6
            return result
        self.ledger.reserve_entry = reserve
        result = self.run_flow(fixture, clock=lambda: monotonic()+offset[0])
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(fixture.actions, [])

    def test_pause_after_submission_still_accounts_for_explicit_receipt(self):
        fixture = Fixture(50)
        def pause(sample):
            if fixture.token: self.control.set_mode('paused')
        fixture.hook = pause
        self.assertEqual(self.run_flow(fixture)['status'], 'confirmed')
        self.assertEqual(fixture.actions, ['register'])
        self.assertEqual(self.control.mode, 'paused')

    def test_manual_takeover_while_reserving_does_not_wait_or_submit(self):
        fixture = Fixture(50)
        original = self.ledger.reserve_entry
        def reserve(*args):
            # A different thread must acquire control even inside reservation.
            worker = threading.Thread(target=self.control.set_mode, args=('manual',), daemon=True)
            worker.start()
            worker.join(1)
            self.assertFalse(worker.is_alive(), 'Reserva bloqueou a tomada manual de controle.')
            return original(*args)
        self.ledger.reserve_entry = reserve
        self.assertEqual(self.run_flow(fixture)['status'], 'unknown')
        self.assertEqual(fixture.actions, [])
        self.assertEqual(self.control.mode, 'manual')

    def test_receipt_mismatch_and_contradiction_do_not_release_reservation(self):
        popup = parse_popup(popup_rows(50))
        token = self.ledger.reserve_entry(popup, self.rules, 50)['token']
        receipt = dict(tournament='T2', offer='P1', amount=50, accepted=True)
        with self.assertRaises(ValueError): self.ledger.confirm_entry(token, receipt)
        receipt['tournament'] = 'T1'
        self.ledger.confirm_entry(token, receipt)
        receipt['accepted'] = False
        with self.assertRaises(ValueError): self.ledger.confirm_entry(token, receipt)

    def test_limits_reserve_slots_and_finished_entry_does_not_refund_budget(self):
        rules = replace(self.rules, max_session_cost=100, max_simultaneous=1)
        first = parse_popup(popup_rows(50)); second = parse_popup(popup_rows(50, tournament='T2'))
        token = self.ledger.reserve_entry(first, rules, 50)['token']
        self.assertEqual(self.ledger.reserve_entry(second, rules, 50)['reason'], 'simultaneous_limit')
        self.ledger.confirm_entry(token, dict(tournament='T1', offer='P1', amount=50, accepted=True))
        self.ledger.finish(token)
        token = self.ledger.reserve_entry(second, rules, 50)['token']
        self.ledger.confirm_entry(token, dict(tournament='T2', offer='P1', amount=50, accepted=True))
        self.ledger.finish(token)
        third = parse_popup(popup_rows(50, tournament='T3'))
        self.assertEqual(self.ledger.reserve_entry(third, rules, 50)['reason'], 'session_budget')

    def test_concurrent_attempts_share_last_slot_and_budget(self):
        rules = replace(self.rules, max_simultaneous=1, max_session_cost=50)
        def reserve(tournament):
            ledger = RegistrationLedger(self.path)
            try: return ledger.reserve_entry(parse_popup(popup_rows(50, tournament)), rules, 50)
            finally: ledger.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, ('T1', 'T2')))
        self.assertEqual(sum(r['status'] == 'reserved' for r in results), 1)

    def test_filters_and_unreachable_or_excessive_target(self):
        popup = parse_popup(popup_rows())
        for rules, target in ((self.rules, 51), (self.rules, True), (self.rules, 12),
                (replace(self.rules, targets=('T2',)), 50),
                (replace(self.rules, allowed_types=('SNG',)), 50),
                (replace(self.rules, minimum_stack=20000), 50)):
            with self.assertRaises(ValueError): rules.check(popup, target)

    def test_four_slots_and_fifth_target_rejected(self):
        for tournament in self.rules.targets:
            result = self.ledger.reserve_entry(parse_popup(popup_rows(50, tournament)), self.rules, 50)
            self.assertEqual(result['status'], 'reserved')
        with self.assertRaises(ValueError): replace(self.rules, targets=(*self.rules.targets, 'T5')).validate()
        other = replace(self.rules, targets=('T5',))
        self.assertEqual(self.ledger.reserve_entry(parse_popup(popup_rows(50, 'T5')), other, 50)['reason'], 'simultaneous_limit')
