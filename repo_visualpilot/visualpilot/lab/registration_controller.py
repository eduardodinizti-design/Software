"""One-at-a-time, fixed-price registration through the isolated visual laboratory."""
from decimal import Decimal
import threading
from time import monotonic

from .lobby import LobbyHistory, LobbyRules, open_next_tournament, parse_card, validar_detalhes
from .registration import field, parse_receipt


class RegistrationController:
    def __init__(self, adapter, ledger, rules, control, *, clock=monotonic):
        rules.validate()
        if rules.max_entry_cost > 50:
            raise ValueError('Limite autorizado: 50 fichas por inscrição.')
        self.adapter, self.ledger, self.rules, self.control = adapter, ledger, rules, control
        self.clock = clock
        self.history = LobbyHistory(ledger)
        self.running = threading.Lock()

    def set_mode(self, mode):
        if hasattr(self.adapter, 'set_mode'):
            self.adapter.set_mode(mode)
        self.control.set_mode(mode)

    def fresh(self, sample):
        if sample.get('source') != 'laboratory' or not 0 <= self.clock()-sample['observed'] <= 5:
            raise ValueError('Observação fora do laboratório ou vencida.')

    def observe(self, stage):
        sample = self.adapter.capture_stage(stage)
        self.fresh(sample)
        field(sample['rows'], r'LABORATORIO\s*FICTICIO')
        return sample

    def context(self, sample):
        card = parse_card(sample['rows'])
        if not card['readable'] or card['registration'] != 'open':
            raise ValueError('Dados incompletos ou registro não aberto.')
        card['offer'] = field(sample['rows'], r'Oferta: ([A-Z0-9-]{1,32})')
        card['bounty'] = field(sample['rows'], r'Bounty: (SIM|NAO)') == 'SIM'
        return {k: card[k] for k in ('tournament','name','kind','buyin','stack','start_time','registration','offer','bounty')}

    def execute_cycle(self):
        if not self.running.acquire(blocking=False):
            return dict(status='blocked', reason='cycle_already_running')
        token = None
        try:
            self.adapter.sync_control()
            revision = self.control.revision
            rules = self.rules
            rules.validate()
            if rules.max_entry_cost > 50:
                raise ValueError('Limite autorizado: 50 fichas por inscrição.')
            self.control.perform(revision, lambda: None)
            navigation = open_next_tournament(self.adapter, self.history,
                LobbyRules(max_buyin=str(rules.max_entry_cost), targets=rules.targets,
                           allowed_types=rules.allowed_types, minimum_stack=rules.minimum_stack),
                self.control, clock=self.clock)
            if navigation['status'] != 'opened':
                return navigation
            self.ledger.audit('registration_flow', dict(stage='details', navigation_token=navigation['token']))
            self.control.perform(revision, lambda: None)
            details = self.observe('details')
            validar_detalhes(navigation['selection'], details, clock=self.clock)
            context = self.context(details)
            value = Decimal(context['buyin'])
            # The existing entry ledger accepts integral chip units. Never truncate
            # a fractional cost or silently reinterpret stored amounts as cents.
            if value != value.to_integral_value():
                raise ValueError('Custo fracionário ainda não suportado pelo histórico de inscrições.')
            target = int(value)
            popup = dict(context, amount=target, minimum=target, maximum=target, step=1)
            rules.check(popup, target)

            def apply(action, sample, token=None):
                self.fresh(sample)
                return self.adapter.apply_step(action, sample['revision'], token)

            if not self.control.perform(revision, lambda: apply('open_modal', details)):
                raise ValueError(self.adapter.last_error or 'details_replaced')
            modal = self.observe('modal')
            if self.context(modal) != context:
                raise ValueError('Modal difere do torneio/oferta selecionado.')
            self.ledger.audit('registration_flow', dict(stage='modal_verified', tournament=context['tournament']))
            self.control.perform(revision, lambda: None)
            # SQLite waits outside the control lock; manual takeover remains possible.
            reservation = self.ledger.reserve_entry(popup, rules, target)
            if reservation['status'] != 'reserved':
                return reservation
            token = reservation['token']
            if not self.control.perform(revision, lambda: apply('confirm', modal, token)):
                # The adapter contract guarantees False means no click was applied.
                self.ledger.confirm_entry(token, dict(tournament=context['tournament'],
                    offer=context['offer'], amount=target, accepted=False))
                return dict(status='blocked', reason=self.adapter.last_error or 'modal_replaced', token=token)
            self.ledger.audit('registration_flow', dict(stage='submitted', token=token))
            receipt = self.observe('receipt')
            if receipt.get('receipt_token') != token:
                raise ValueError('Recibo sem correlação com a reserva.')
            # Bookkeeping continues if pause/manual arrives after submission.
            result = self.ledger.confirm_entry(token, parse_receipt(receipt['rows']))
            self.ledger.audit('registration_flow', dict(stage='receipt_recorded', result=result))
            return result
        except Exception as exc:
            result = dict(status='unknown' if token else 'blocked', reason=str(exc)[:500],
                          error_type=type(exc).__name__)
            if token:
                result['token'] = token
            self.ledger.audit('registration_flow_interrupted', result)
            return result
        finally:
            self.running.release()
