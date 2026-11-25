"""Sombra de solver pós-flop — pacote As7d2c do PR#12 (SHADOW, NUNCA executa).

Segunda fonte de sombra, COMPLEMENTAR ao `solver_cbet_shadow` (100 flops, só flop):
este pacote é UM board — As7d2c (+ 24 isomorfos de naipe) — mas com **flop E turn**
per-combo, dos DOIS jogadores, do banco NVT do PR#12 (TexasSolver, discounted CFR, gap
0,046bb, iter 91). Destilado do SQLite de 2,38 GB para ~8,7 MB (flop+turn); o RIVER
(343k nós, ~1,9 GB) ficou de fora — grande demais p/ achatar; consulta sob demanda no
SQLite é trabalho futuro.

Modelo (≠ do pacote de 100 flops): HU chip-EV, pote 5,5bb, **22,5bb** efetivos, menu
**bet 1/3, raise 100%, all-in** (o de 100 flops é 33/50/70/allin, 23bb). São duas
referências independentes do mesmo spot — convivem, não se sobrepõem.

Grading por frequência (`ev_available=False`), `execution_allowed=False` — igual ao
resto do pós-flop. A própria fonte marca `LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION`.

História dos nós (chave de lookup) no formato do banco: lista de passos
`'<actor>:<kind>:<amount>'` (ex. `['1:check:0','0:bet:1.833']`), actor 1=BB(OOP, age
primeiro), 0=BTN(IP); passos de carta vêm como `'BOARD:<carta>'` (turn). O flop-cbet do
BTN (BB deu check) é a história `['1:check:0']`.

LIMITE DE USO AO VIVO: casar um nó de TURN exige o histórico de apostas do flop, que o
advisor ao vivo ainda não encadeia (infra existe em `strategy/hand_state.py` +
`strategy/action_sequence.py`, não plugada no `advise_postflop`). Hoje só o FLOP é
casável ao vivo; turn fica p/ estudo/auditoria e p/ quando o histórico pós-flop for
encadeado.
"""
import gzip
import json
import os
from functools import lru_cache
from itertools import permutations

RANKS = '23456789TJQKA'
SUITS = 'shdc'
ROOT_BOARD = ('As', '7d', '2c')

POS = {0: 'BTN', 1: 'BB'}                                 # oop=1 -> BB age primeiro no flop

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'strategy_data', 'postflop_solver',
                             'as7d2c_pr12_flop_turn.json.gz')

# Histórias canônicas dos nós de flop úteis ao vivo (no board do pacote).
HIST_BB_FIRST = []                                        # BB age primeiro (check/bet/allin)
HIST_BTN_CBET = ['1:check:0']                             # BTN decide c-bet após o check do BB


def _data_path(path=None):
    return path or os.environ.get('SOLVER_PR12_SHADOW_PATH') or _DEFAULT_PATH


@lru_cache(maxsize=2)
def load_pack(path=None):
    """Carrega (e cacheia) o pacote destilado. None se ausente/ilegível (a sombra some
    em silêncio, nunca quebra o conselho)."""
    try:
        with gzip.open(_data_path(path), 'rb') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _flop_sigmas(flop3):
    """Permutações de naipe σ (ROOT_BOARD As7d2c -> flop ao vivo) que casam exatamente.
    Vazio se o flop não é isomorfo a As7d2c. σ é dict suit->suit (dataset->live)."""
    if not flop3 or len(flop3) != 3:
        return []
    try:
        live = sorted(flop3)
    except TypeError:
        return []
    out = []
    for perm in permutations(SUITS):
        m = dict(zip(SUITS, perm))
        if sorted(c[0] + m[c[1]] for c in ROOT_BOARD) == live:
            out.append(m)
    return out


def _translate_combo(hero, sigma):
    """Mão do hero (naipes ao vivo) -> rotulagem do pacote via σ^-1. Devolve as duas
    ordens de chave a testar, ou None se irreconhecível."""
    inv = {v: k for k, v in sigma.items()}
    try:
        c0 = hero[0][0] + inv[hero[0][1]]
        c1 = hero[1][0] + inv[hero[1][1]]
    except (KeyError, IndexError):
        return None
    return (c0 + c1, c1 + c0)


def _node_key(dataset_board, history):
    return '%s#%s' % (''.join(dataset_board), '|'.join(history) or 'root')


def _mix(actions, freq, *, min_show=0.10):
    pairs = sorted(zip(actions, freq), key=lambda x: -x[1])
    return [{'action': a, 'frequency': round(f, 4)} for a, f in pairs if f >= min_show]


def _recommended(actions, freq):
    return max(zip(actions, freq), key=lambda x: x[1])[0]


BASE_CAVEATS = ('POSTFLOP_SOLVER_SHADOW', 'SOLVER_SHADOW_NOT_FOR_EXECUTION',
                'SOLVER_SHADOW_SPOT_BTN_VS_BB_25_AS7D2C', 'SOLVER_GRADING_FREQ_NO_EV',
                'SOLVER_SHADOW_PR12_TREE_BET33_RAISE100_22_5BB',
                'LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION')


def lookup(hero, live_board, history, *, path=None):
    """Sombra per-combo do pacote As7d2c (PR#12) p/ a mão do hero num nó dado por
    `history`, ou None se o board não é As7d2c(iso)/o nó não existe/o combo não está no
    range. `live_board`: 3 cartas (flop) ou 4 (turn). `history`: passos no formato do
    banco (ver módulo); para a c-bet do BTN use HIST_BTN_CBET.

    Devolve dict com `recommended_shadow`, `mix`, `freq`, `actions`, `amounts_bb`,
    `actor_pos`, `combo`, `iso`, `caveats`, `execution_allowed=False`. Puro estudo."""
    pack = load_pack(path)
    if pack is None or not hero or len(hero) != 2 or not live_board or len(live_board) < 3:
        return None
    flop3 = list(live_board)[:3]
    sigmas = _flop_sigmas(flop3)
    if not sigmas:
        return None                                      # board não é As7d2c isomórfico
    nodes = pack['nodes']
    for sigma in sigmas:
        inv = {v: k for k, v in sigma.items()}
        # Board em rotulagem do pacote: flop fixo As7d2c + (turn traduzido, se houver).
        dataset_board = list(ROOT_BOARD)
        hist = list(history)
        if len(live_board) >= 4:
            try:
                tcard = live_board[3][0] + inv[live_board[3][1]]
            except (KeyError, IndexError):
                continue
            dataset_board.append(tcard)
        node = nodes.get(_node_key(dataset_board, hist))
        if node is None:
            continue
        keys = _translate_combo(hero, sigma)
        if not keys:
            continue
        combos = node['combos']
        combo_key = next((k for k in keys if k in combos), None)
        if combo_key is None:
            # Nó existe mas a mão não está no range daquele ator -> honesto.
            return dict(spot='btn_vs_bb_25_as7d2c', node_history=hist,
                        street=node['street'], actor_pos=node['actor_pos'],
                        board=node['board'], iso=(flop3 != list(ROOT_BOARD)),
                        actions=node['actions'], amounts_bb=node['amounts_bb'],
                        combo_in_range=False, recommended_shadow=None, freq=None, mix=None,
                        execution_allowed=False,
                        caveats=list(BASE_CAVEATS) + ['SOLVER_SHADOW_COMBO_NOT_IN_RANGE'])
        freq = combos[combo_key]
        caveats = list(BASE_CAVEATS)
        if node['street'] == 'TURN':
            caveats.append('SOLVER_SHADOW_TURN_LIVE_MATCH_NEEDS_POSTFLOP_HISTORY')
        return dict(spot='btn_vs_bb_25_as7d2c', node_history=hist, street=node['street'],
                    actor_pos=node['actor_pos'], board=node['board'],
                    iso=(flop3 != list(ROOT_BOARD)), combo=combo_key, combo_in_range=True,
                    actions=node['actions'], amounts_bb=node['amounts_bb'],
                    freq=[round(x, 4) for x in freq],
                    recommended_shadow=_recommended(node['actions'], freq),
                    mix=_mix(node['actions'], freq), execution_allowed=False, caveats=caveats)
    return None


def flop_cbet(hero, live_board, *, path=None):
    """Atalho ao vivo: c-bet do BTN no flop As7d2c (BB deu check). None fora da cobertura."""
    if not live_board or len(live_board) != 3:
        return None
    return lookup(hero, live_board, HIST_BTN_CBET, path=path)
