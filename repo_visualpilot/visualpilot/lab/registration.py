"""Registration and amount selection for an isolated fictitious GUI laboratory."""
from dataclasses import dataclass
import math
import re
import threading
from time import monotonic
import uuid

from .tournament_purchases import PurchaseLedger


def field(rows, pattern):
    """Never concatenate digits, infer missing text, or ignore duplicate fields."""
    if ': ' in pattern:
        label = pattern.split(': ', 1)[0]
        candidates = [text for _, text, _ in rows if re.match(re.escape(label)+r'\s*:', str(text).strip())]
        if len(candidates) != 1:
            raise ValueError('Campo ausente ou ambíguo.')
    pattern = pattern.replace(': ', r':\s*')
    matches = [(re.fullmatch(pattern, str(text).strip()), score) for _, text, score in rows]
    matches = [(match, score) for match, score in matches if match]
    if len(matches) != 1:
        raise ValueError('Campo ausente ou ambíguo.')
    match, score = matches[0]
    if not math.isfinite(float(score)) or not .95 <= float(score) <= 1:
        raise ValueError('Campo pouco legível.')
    return match.group(1) if match.lastindex else match.group()


def parse_popup(rows):
    field(rows, r'LABORATORIO\s*FICTICIO')
    field(rows, r'Registrar')
    result = dict(
        tournament=field(rows, r'Torneio: ([A-Z0-9-]{1,32})'),
        offer=field(rows, r'Oferta: ([A-Z0-9-]{1,32})'),
        kind=field(rows, r'Tipo: (MTT|SNG)'),
        bounty=field(rows, r'Bounty: (SIM|NAO)') == 'SIM',
        amount=int(field(rows, r'Custo: ([0-9]{1,6})\s*fichas\s*ficticias')),
        stack=int(field(rows, r'Stack: ([0-9]{1,8})')),
        minimum=int(field(rows, r'Minimo: ([0-9]{1,6})')),
        maximum=int(field(rows, r'Maximo: ([0-9]{1,6})')),
        step=int(field(rows, r'Passo: ([0-9]{1,6})')))
    if not (0 < result['minimum'] <= result['amount'] <= result['maximum']
            and result['step'] > 0 and result['stack'] > 0):
        raise ValueError('Limites do seletor inválidos.')
    return result


def parse_receipt(rows):
    field(rows, r'LABORATORIO\s*FICTICIO')
    return dict(tournament=field(rows, r'Torneio: ([A-Z0-9-]{1,32})'),
                offer=field(rows, r'Oferta: ([A-Z0-9-]{1,32})'),
                amount=int(field(rows, r'Custo: ([0-9]{1,6})\s*fichas\s*ficticias')),
                accepted=field(rows, r'Inscricao: (CONFIRMADA|RECUSADA)') == 'CONFIRMADA')


@dataclass(frozen=True)
class RegistrationRules:
    targets: tuple[str, ...]
    max_entry_cost: int = 50
    max_session_cost: int = 200
    max_simultaneous: int = 4
    allowed_types: tuple[str, ...] = ('MTT',)
    minimum_stack: int = 1000

    def validate(self):
        if (not isinstance(self.targets, tuple) or not 1 <= len(self.targets) <= 4
                or any(not isinstance(t, str) or not re.fullmatch(r'[A-Z0-9-]{1,32}', t) for t in self.targets)
                or len(set(self.targets)) != len(self.targets)):
            raise ValueError('Selecione de um a quatro torneios distintos.')
        for value in (self.max_entry_cost, self.max_session_cost, self.max_simultaneous, self.minimum_stack):
            if type(value) is not int or value <= 0:
                raise ValueError('Limite inválido.')
        if self.max_simultaneous > 4 or not self.allowed_types or any(t not in ('MTT', 'SNG') for t in self.allowed_types):
            raise ValueError('Filtro ou limite simultâneo inválido.')

    def check(self, popup, target):
        self.validate()
        if type(target) is not int or not 0 < target <= self.max_entry_cost:
            raise ValueError('Custo alvo excede o limite por inscrição.')
        if popup['tournament'] not in self.targets or popup['kind'] not in self.allowed_types:
            raise ValueError('Torneio fora dos filtros.')
        if popup['stack'] < self.minimum_stack:
            raise ValueError('Stack abaixo do mínimo.')
        if not popup['minimum'] <= target <= popup['maximum'] or (target - popup['amount']) % popup['step']:
            raise ValueError('Valor alvo não é alcançável pelo seletor.')


class RegistrationLedger(PurchaseLedger):
    """Reserves cost and a slot atomically, including unknown outcomes after restart."""
    def __init__(self, path):
        super().__init__(path)
        self.db.execute('''CREATE TABLE IF NOT EXISTS registrations(
            token TEXT PRIMARY KEY, tournament TEXT NOT NULL, offer TEXT NOT NULL,
            amount INTEGER NOT NULL, bounty INTEGER NOT NULL, status TEXT NOT NULL, UNIQUE(tournament, offer))''')

    def reserve_entry(self, popup, rules, target):
        rules.check(popup, target)
        if popup['amount'] != target:
            raise ValueError('Valor selecionado ainda não foi confirmado.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            previous = self.db.execute('SELECT * FROM registrations WHERE tournament=? AND offer=?',
                                       (popup['tournament'], popup['offer'])).fetchone()
            occupied = self.db.execute("SELECT * FROM registrations WHERE status IN ('reserved','confirmed')").fetchall()
            spent = self.db.execute("SELECT COALESCE(SUM(amount),0) FROM registrations WHERE status!='rejected'").fetchone()[0]
            reason = None
            if previous:
                reason = 'offer_already_seen'
            elif self.db.execute('SELECT 1 FROM tournaments WHERE id=?', (popup['tournament'],)).fetchone():
                reason = 'tournament_already_registered'
            elif any(row['tournament'] == popup['tournament'] for row in occupied):
                reason = 'tournament_pending_or_active'
            elif len(occupied) >= rules.max_simultaneous:
                reason = 'simultaneous_limit'
            elif spent + target > rules.max_session_cost:
                reason = 'session_budget'
            if reason:
                result = dict(status='blocked', reason=reason)
            else:
                token = uuid.uuid4().hex
                self.db.execute('INSERT INTO registrations VALUES(?,?,?,?,?,?)',
                                (token, popup['tournament'], popup['offer'], target, int(popup['bounty']), 'reserved'))
                result = dict(status='reserved', token=token)
            self.audit('entry_reservation', dict(popup=popup, result=result))
            self.db.execute('COMMIT')
            return result
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def confirm_entry(self, token, receipt):
        if type(receipt.get('accepted')) is not bool:
            raise ValueError('Recibo sem resultado explícito.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT * FROM registrations WHERE token=?', (token,)).fetchone()
            if row is None or (row['tournament'], row['offer'], row['amount']) != (
                    receipt['tournament'], receipt['offer'], receipt['amount']):
                raise ValueError('Recibo não corresponde à inscrição reservada.')
            status = 'confirmed' if receipt['accepted'] else 'rejected'
            if row['status'] not in ('reserved', status):
                raise ValueError('Recibo contraditório.')
            self.db.execute('UPDATE registrations SET status=? WHERE token=?', (status, token))
            # Entry cost becomes the existing purchase ledger's budget baseline.
            # Bounty was explicitly read with the offer, never inferred from its title.
            if receipt['accepted']:
                self.register(row['tournament'], row['amount'], bool(row['bounty']))
            self.audit('entry_receipt', dict(token=token, receipt=receipt))
            self.db.execute('COMMIT')
            return dict(status=status, token=token)
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def finish(self, token):
        """Explicit laboratory completion releases the slot, never refunds spend."""
        changed = self.db.execute("UPDATE registrations SET status='finished' WHERE token=? AND status='confirmed'", (token,)).rowcount
        if changed != 1:
            raise ValueError('Somente uma inscrição confirmada pode encerrar.')
        self.audit('entry_finished', dict(token=token))


class LabControl:
    def __init__(self):
        self.lock = threading.RLock()
        self.revision = 0
        self.mode = 'automatic'

    def set_mode(self, mode):
        if mode not in ('automatic', 'manual', 'paused'):
            raise ValueError('Modo inválido.')
        with self.lock:
            self.mode = mode
            self.revision += 1

    def perform(self, revision, operation):
        # OCR is outside this lock; handoff invalidates an in-flight observation.
        with self.lock:
            if self.mode != 'automatic' or revision != self.revision:
                raise ValueError('Controle alterado; obtenha uma nova observação.')
            return operation()


def adjust_and_register(adapter, ledger, rules, target, control, *, max_steps=20, clock=monotonic):
    """Closed-loop simulated GUI only. Adapter must reject a replaced popup revision.

    capture() returns rows, observed, revision, source and optional receipt_token.
    apply(action, revision, token) mutates only the laboratory fixture; False means
    no action occurred. Exceptions/absent receipts leave a reservation unresolved.
    """
    if type(max_steps) is not int or not 0 <= max_steps <= 100:
        raise ValueError('Limite de ajustes inválido.')
    rules.validate()
    if hasattr(adapter, 'sync_control'):
        adapter.sync_control()
    revision = control.revision
    expected = context = None
    token = None
    steps = 0

    def fresh(sample):
        age = clock() - sample['observed']
        if sample.get('source') != 'laboratory' or not 0 <= age <= 5:
            raise ValueError('Captura inválida, expirada ou fora do laboratório.')

    def observe():
        sample = adapter.capture()
        fresh(sample)
        return sample

    def apply(action, sample, token=None):
        fresh(sample)
        return adapter.apply(action, sample['revision'], token)

    try:
        for steps in range(max_steps + 1):
            control.perform(revision, lambda: None)
            sample = observe()
            popup = parse_popup(sample['rows'])
            rules.check(popup, target)
            new_context = {k: v for k, v in popup.items() if k != 'amount'}
            if context is not None and new_context != context:
                raise ValueError('Oferta mudou durante o ajuste.')
            if expected is not None and popup['amount'] != expected:
                raise ValueError('Ajuste não confirmado; sem progresso ou valor inesperado.')
            context = new_context
            if popup['amount'] == target:
                control.perform(revision, lambda: None)
                # SQLite may wait for another reservation. Never hold the control
                # lock during that wait; handoff must still cancel the next click.
                reservation = ledger.reserve_entry(popup, rules, target)
                if reservation['status'] != 'reserved':
                    return reservation
                token = reservation['token']
                if not control.perform(revision, lambda: apply('register', sample, token)):
                    ledger.confirm_entry(token, dict(tournament=popup['tournament'], offer=popup['offer'], amount=target, accepted=False))
                    return dict(status='blocked', reason=getattr(adapter, 'last_error', None) or 'popup_replaced', token=token)
                receipt_sample = observe()
                if receipt_sample.get('receipt_token') != token:
                    raise ValueError('Confirmação sem correlação com o pedido.')
                # Accounting must record a receipt even if the user pauses after submit.
                return dict(ledger.confirm_entry(token, parse_receipt(receipt_sample['rows'])), steps=steps)
            if steps == max_steps:
                raise ValueError('Limite de ajustes atingido.')
            direction = 1 if popup['amount'] < target else -1
            expected = popup['amount'] + direction * popup['step']
            action = 'increase' if direction == 1 else 'decrease'
            if not control.perform(revision, lambda: apply(action, sample)):
                raise ValueError(getattr(adapter, 'last_error', None) or 'Popup substituído antes do ajuste.')
        raise AssertionError('Unreachable')
    except Exception as exc:
        result = dict(status='unknown' if token else 'blocked', reason=str(exc)[:500],
                      error_type=type(exc).__name__, steps=steps)
        if token:
            result['token'] = token
        ledger.audit('entry_interrupted', result)
        return result
