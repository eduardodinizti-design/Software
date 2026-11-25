"""B06 — estado por MÃO (plano de evolução do cérebro, Lote 2).

Acumula o estado de UMA mão com IDENTIDADE persistente (mesa, mão): participantes
iniciais e seus stacks, jogadores ainda ativos, foldados (que NÃO somem da
história), contribuições, pote e a lista de eventos CONFIRMADOS. Um snapshot de
OUTRA mão não contamina o estado (guarda por identidade). O estado de apostas
(nível open/3bet/4bet, agressor, reabertura) vem do replay do B07
(`action_sequence.replay`) — UM só caminho de reconstrução. PURO: sem captura.
"""
from preflop_study import Blocked
from strategy.action_sequence import replay


class HandState:
    def __init__(self, identity, participants, *, hero=None, blinds=None):
        """identity: (table_id, hand_id) — ambos não-vazios. participants:
        {position: start_stack_bb} dos jogadores no início da mão. hero: posição do
        hero (opcional). blinds: (sb, bb) opcional."""
        if not (isinstance(identity, tuple) and len(identity) == 2 and all(identity)):
            raise Blocked('INVALID_HAND_IDENTITY')
        if not isinstance(participants, dict) or not participants:
            raise Blocked('NO_PARTICIPANTS')
        self.identity = identity
        self.participants = dict(participants)         # start stacks, imutável por mão
        self.hero = hero
        self.blinds = blinds
        self.events = []                               # eventos CONFIRMADOS (B07)

    def _guard(self, identity):
        if identity != self.identity:
            # Snapshot de outra mão/mesa: NUNCA contamina este estado.
            raise Blocked('HAND_IDENTITY_MISMATCH')

    def append(self, event, *, identity=None):
        """Acrescenta UM evento confirmado. `identity` (se dado) é conferido contra a
        mão atual antes de aplicar (não contamina de outra mão)."""
        if identity is not None:
            self._guard(identity)
        self.events.append(dict(event))
        return self

    def ingest(self, identity, events):
        """Substitui a sequência confirmada desta mão por `events`, conferindo a
        identidade primeiro. Snapshot de outra mão é REJEITADO (não contamina)."""
        self._guard(identity)
        self.events = [dict(e) for e in events]
        return self

    # ---- estado derivado (via replay do B07; UM só caminho de reconstrução) ----
    def betting(self):
        kw = {} if self.blinds is None else dict(blinds=self.blinds)
        return replay(self.events, self.participants, **kw)

    @property
    def folded(self):
        return self.betting().get('folded', [])

    @property
    def active(self):
        """Jogadores ainda na mão (foldados preservados na história, fora daqui)."""
        b = self.betting()
        return b['active'] if b['status'] == 'OK' else [p for p in self.participants]

    @property
    def pot(self):
        return self.betting().get('pot', 0.0)

    @property
    def contributions(self):
        return self.betting().get('contributions', {})

    @property
    def label(self):
        """Nível do pote (unopened/limped/open/3bet/4bet/5bet+) ou 'pending'."""
        return self.betting().get('label', 'pending')

    @property
    def aggressor(self):
        return self.betting().get('aggressor')

    def remaining_stacks(self):
        """Stack ATUAL por jogador = inicial - contribuições (fichas conciliadas)."""
        contrib = self.contributions
        return {p: self.participants[p] - contrib.get(p, 0.0) for p in self.participants}
