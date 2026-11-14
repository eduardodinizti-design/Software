"""A1 — Antecipação de decisão: leitura antecipada + FOLD/CHECK preparado.

Hoje o operador só paga o custo do cérebro (advise_table, ~330ms) DENTRO da vez
do hero. Este módulo guarda, por (mesa, mão), uma decisão SEGURA já computada e a
IMPRESSÃO DIGITAL do estado em que ela foi tomada. Na chegada da vez, se a mão e a
impressão digital BATEM e a ação ainda é oferecida, devolve a decisão na hora —
sem repagar o cérebro. Qualquer divergência INVALIDA e força recomputar ao vivo.

Trava de segurança (dinheiro real): só se antecipa ação SEM-COMMIT (`fold`/`check`).
`call`/`raise` comprometem ficha e NUNCA são preparados — decidem-se sempre ao vivo.

PURO: sem OCR, sem captura, sem clique, sem relógio. Só stdlib. O chamador (o
operador) fornece o `advice` já lido e os sinais baratos do estado/botões; este
módulo só decide "posso reusar, e ainda vale?". Ver docs do adendo A1–A5 e
[[nvt-metodologia-preventiva]] (invariantes + testes + fixtures offline).
"""
import math
from collections import OrderedDict

# Único conjunto de ações que podem ser PREPARADAS: não comprometem ficha. Um
# fold/check errado não custa stack; um call/raise antecipado, sim. Por isso
# call/raise ficam SEMPRE fora da antecipação (decisão ao vivo, nó validado).
SAFE_ACTIONS = ('fold', 'check')


def _round_bb(value, quantum=0.5):
    """Quantiza um valor em BB para estabilizar a impressão digital contra o jitter
    de OCR (3.49 vs 3.51 não devem gerar impressões diferentes). None preserva None."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return None
    return round(value / quantum) * quantum


def _bets_signature(table_state):
    """Apostas vivas como tupla ordenada e hashável (assento, bet_bb quantizado).
    Ignora apostas ausentes/zeradas/ilegíveis — elas não mudam o espaço da decisão."""
    bets = (table_state or {}).get('bets') or []
    out = []
    for bet in bets:
        if not isinstance(bet, dict):
            continue
        seat = bet.get('seat')
        amount = _round_bb(bet.get('bet_bb'))
        if seat is not None and amount is not None and amount > 0:
            out.append((seat, amount))
    return tuple(sorted(out))


def decision_fingerprint(table_state):
    """O QUE a decisão pré-flop depende: posição do hero, quanto falta pagar e o
    padrão de apostas vivas. NÃO inclui os botões de propósito — a mesma decisão
    pode ser preparada num frame sem a linha de ação e disparada quando ela surge;
    a disponibilidade da ação é checada à parte, em `take` (invariante 3)."""
    ts = table_state or {}
    hero_pos = (ts.get('positions') or {}).get('hero')
    to_call = _round_bb(ts.get('to_call_bb'))
    return (hero_pos, to_call, _bets_signature(ts))


def available_actions(buttons):
    """Conjunto (frozenset, maiúsculas) das ações REALMENTE oferecidas agora. Só
    conta botão com `action` resolvido — rótulo não identificado/PRESELECT não é
    ação disponível e não deve autorizar disparo."""
    acts = set()
    for button in (buttons or []):
        if isinstance(button, dict) and button.get('action'):
            acts.add(str(button['action']).upper())
    return frozenset(acts)


def _as_cards(hero_cards):
    """Normaliza cartas do hero para tupla comparável; vazio/ inválido -> None."""
    if not hero_cards:
        return None
    try:
        cards = tuple(hero_cards)
    except TypeError:
        return None
    return cards if len(cards) == 2 and all(cards) else None


class AnticipationStore:
    """Loja de decisões SEGURAS pré-computadas, por (mesa, mão), com invalidadores
    baratos. Limitada (LRU) para não crescer numa sessão longa. Mantém contadores
    para a auditoria (quantas preparadas, quantos aproveitamentos, por que descartou)."""

    def __init__(self, limit=256):
        self._limit = max(1, int(limit))
        self._store = OrderedDict()          # (table_key, hand_id) -> prep dict
        self.stats = dict(prepared=0, hits=0, miss_absent=0, miss_state=0,
                          miss_not_offered=0, discarded_hand=0,
                          rejected_unsafe=0, rejected_premium=0)

    @staticmethod
    def _key(table_key, hand_id):
        return (table_key, hand_id)

    def prepare(self, table_key, hand_id, advice, fingerprint, hero_cards, is_premium=None):
        """Guarda a decisão SE for segura de antecipar. Retorna True se guardou.

        Rejeita (sem guardar) quando: mão sem id; advice não é dict; não é
        status ADVICE pré-flop; a ação recomendada não é fold/check; ou é um FOLD
        de mão premium (blindagem, invariante 5). `is_premium` pode ser um callable
        (recebe as cartas) ou um bool já avaliado pelo chamador."""
        if hand_id is None or not isinstance(advice, dict):
            return False
        recommended = str(advice.get('recommended') or '').lower()
        phase = advice.get('phase')
        if (advice.get('status') != 'ADVICE' or phase not in (None, 'preflop')
                or recommended not in SAFE_ACTIONS):
            self.stats['rejected_unsafe'] += 1
            return False
        if recommended == 'fold':
            premium = is_premium(hero_cards) if callable(is_premium) else bool(is_premium)
            if premium:
                self.stats['rejected_premium'] += 1
                return False
        key = self._key(table_key, hand_id)
        self._store[key] = dict(
            action=recommended,
            fingerprint=fingerprint,
            hero_cards=_as_cards(hero_cards),
            validated=bool(advice.get('validated')),
            node_id=advice.get('node_id'),
        )
        self._store.move_to_end(key)
        while len(self._store) > self._limit:
            self._store.popitem(last=False)
        self.stats['prepared'] += 1
        return True

    def take(self, table_key, hand_id, fingerprint, available_now, hero_cards):
        """Devolve a decisão preparada se — e só se — ainda VALE. None força o
        chamador a recomputar ao vivo (advise_table). As checagens, em ordem:

        1. existe prep para (mesa, mão)?                      senão -> miss_absent
        2. as cartas batem? (prep tinha cartas e divergem)    senão -> DESCARTA (mão nova)
        3. a impressão digital do estado bate?                senão -> miss_state (mantém)
        4. a ação preparada está sendo OFERECIDA agora?       senão -> miss_not_offered

        Só o passo 2 apaga a prep (a mão mudou de verdade). 3 e 4 podem ser estado
        transitório/leitura ruim de UM frame — mantém a prep para reavaliar no
        próximo, sem nunca disparar fora do contrato."""
        if hand_id is None:
            self.stats['miss_absent'] += 1
            return None
        key = self._key(table_key, hand_id)
        prep = self._store.get(key)
        if prep is None:
            self.stats['miss_absent'] += 1
            return None
        cards_now = _as_cards(hero_cards)
        if prep['hero_cards'] is not None and cards_now is not None and prep['hero_cards'] != cards_now:
            del self._store[key]
            self.stats['discarded_hand'] += 1
            return None
        if prep['fingerprint'] != fingerprint:
            self.stats['miss_state'] += 1
            return None
        if prep['action'].upper() not in available_actions_set(available_now):
            self.stats['miss_not_offered'] += 1
            return None
        self.stats['hits'] += 1
        return dict(action=prep['action'], source='anticipated',
                    validated=prep['validated'], node_id=prep['node_id'])

    def invalidate(self, table_key, hand_id=None):
        """Esquece a prep de uma mão (hand_id dado) ou de toda a mesa (hand_id=None).
        Chamar ao detectar fim de torneio/mesa fechada ou troca dura de contexto."""
        if hand_id is not None:
            self._store.pop(self._key(table_key, hand_id), None)
            return
        for key in [k for k in self._store if k[0] == table_key]:
            del self._store[key]

    def __len__(self):
        return len(self._store)


def available_actions_set(available_now):
    """Aceita tanto um frozenset já pronto (de `available_actions`) quanto a lista
    crua de botões, normalizando para o conjunto de ações em maiúsculas."""
    if isinstance(available_now, (set, frozenset)):
        return frozenset(str(a).upper() for a in available_now)
    return available_actions(available_now)


_UNSET = object()


class TurnEpochTracker:
    """A2 — debounce da detecção da vez do hero, por mesa.

    PROBLEMA (medido ao vivo 13/11): a linha de botões PISCA — um frame lê
    NO_BUTTON_ROW no meio da vez (animação/OCR) e, sem debounce, isso encerra a
    "época de decisão", forçando o cérebro a recomputar quando a vez reaparece.

    PORQUE É SEGURO SEGURAR: na vez do hero o vilão NÃO pode agir, e a única ação
    que o A1 reaproveita é fold/check — que é SEMPRE a última decisão pré-flop da
    mão (fold = fora; check no BB = pré-flop fechado). Logo, manter a época viva
    através de um pisca nunca reusa uma decisão diferente da MESMA mão.

    INVALIDADORES: a época fecha quando (a) `debounce` visitas CONSECUTIVAS fora da
    vez acontecem — fim real da vez, não pisca; ou (b) a MÃO muda (hand_key novo) —
    nova situação. `close()` força (fim de torneio / mesa morta). PURO, sem relógio."""

    def __init__(self, debounce=3):
        self._debounce = max(1, int(debounce))
        self._epoch = {}            # table_key -> época atual
        self._in_turn = {}          # table_key -> dentro de uma época aberta?
        self._nonturn = {}          # table_key -> visitas consecutivas fora da vez
        self._hand = {}             # table_key -> última mão vista na vez

    def on_turn(self, table_key, hand_key=None):
        """Registrar a vez do hero presente. Incrementa a época se ela acabou de
        (re)abrir OU se a mão mudou. Retorna a época atual (int)."""
        prev_hand = self._hand.get(table_key, _UNSET)
        hand_changed = hand_key is not None and prev_hand is not _UNSET and hand_key != prev_hand
        self._hand[table_key] = hand_key
        self._nonturn[table_key] = 0
        if hand_changed or not self._in_turn.get(table_key):
            self._epoch[table_key] = self._epoch.get(table_key, 0) + 1
        self._in_turn[table_key] = True
        return self._epoch[table_key]

    def on_nonturn(self, table_key):
        """Registrar uma visita FORA da vez. Só encerra a época após `debounce`
        visitas consecutivas (um pisca isolado não encerra). Retorna True se
        encerrou agora."""
        streak = self._nonturn.get(table_key, 0) + 1
        self._nonturn[table_key] = streak
        if streak >= self._debounce:
            if self._in_turn.get(table_key):
                self._in_turn[table_key] = False
                return True
        return False

    def close(self, table_key):
        """Força o encerramento da época (fim de torneio, mesa fechada)."""
        self._in_turn[table_key] = False
        self._nonturn[table_key] = self._debounce

    def epoch(self, table_key):
        return self._epoch.get(table_key, 0)

    def in_turn(self, table_key):
        return bool(self._in_turn.get(table_key))
