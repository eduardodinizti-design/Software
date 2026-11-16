"""Sombra de solver de TURN — pacote dos 24 boards (SHADOW, NUNCA executa).

Terceira fonte de sombra pós-flop, COMPLEMENTAR a `solver_cbet_shadow` (100 flops, só
flop) e `solver_pr12_shadow` (1 board As7d2c, flop+turn da árvore cheia). Este pacote
cobre **24 boards** (+ isomorfos de naipe de cada um) com o FLOP e as linhas CANÔNICAS
de TURN resolvidas no nosso TexasSolver local:

  FLOP  : root (BB age primeiro) e c-bet do BTN (após check do BB) — per-combo.
  TURN  : nas duas linhas que chegam ao turn sem aposta pendente, para cada carta de
          turn, as decisões check-vs-aposta dos DOIS jogadores:
            - checkthrough : flop deu check-check
            - betcall      : flop foi aposta(menor)-call
          em cada uma: `bb_turn` (BB lidera) e `btn_turn` (BB deu check, BTN barrela).

Modelo: HU chip-EV, pote 5,5bb, 22,5bb efetivos, BTN(IP)/BB(OOP). Menu de turn do
solver (apostas absolutas em bb; tokens de ação vêm com o tamanho, ex. `bet_2`, `bet_3`).
Grading por frequência (`ev_available=False`), `execution_allowed=False`.

LIMITE DE USO AO VIVO (igual ao PR#12): casar um nó de TURN exige o histórico de apostas
do flop, que o `advise_postflop` ao vivo ainda não encadeia. Hoje o FLOP é casável ao
vivo; o TURN é p/ ESTUDO/HOMOLOGAÇÃO e p/ quando o histórico pós-flop for encadeado. A
API semântica (`turn_lead`/`turn_barrel` por linha e carta) existe para isso.
"""
import gzip
import json
import os
from functools import lru_cache
from itertools import permutations

SUITS = 'shdc'
POS = {0: 'BTN', 1: 'BB'}

_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'strategy_data', 'postflop_solver',
                             'turn_pack_24boards.json.gz')

HIST_BTN_CBET = ['1:check:0']          # flop: BTN decide c-bet após check do BB

BASE_CAVEATS = ('POSTFLOP_SOLVER_SHADOW', 'SOLVER_SHADOW_NOT_FOR_EXECUTION',
                'SOLVER_SHADOW_SPOT_BTN_VS_BB_25_24BOARDS', 'SOLVER_GRADING_FREQ_NO_EV',
                'TURN_PACK_CANONICAL_LINES_ONLY',
                'LAB_POLICY_REQUIRES_WINDOWS_EXECUTION_VALIDATION')


def _data_path(path=None):
    return path or os.environ.get('SOLVER_TURN_SHADOW_PATH') or _DEFAULT_PATH


@lru_cache(maxsize=2)
def load_pack(path=None):
    """Carrega (e cacheia) o pacote. None se ausente/ilegível — a sombra some em silêncio."""
    try:
        with gzip.open(_data_path(path), 'rb') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _parse_board_str(s):
    return [s[i:i + 2] for i in range(0, len(s), 2)]


def _sigmas_for_root(root_flop, live_flop):
    """Permutações de naipe σ (root -> live) que casam o flop exatamente. σ: dict
    suit(dataset)->suit(live). Vazio se não isomórfico."""
    try:
        live = sorted(live_flop)
    except TypeError:
        return []
    out = []
    for perm in permutations(SUITS):
        m = dict(zip(SUITS, perm))
        if sorted(c[0] + m[c[1]] for c in root_flop) == live:
            out.append(m)
    return out


def _match_board(live_flop, pack):
    """Acha o board-raiz do pacote isomórfico ao flop ao vivo. Devolve lista de
    (root_str, root_flop, sigma) — pode haver mais de um σ p/ o mesmo root."""
    hits = []
    for root_str in pack['boards']:
        root_flop = _parse_board_str(root_str)
        for sigma in _sigmas_for_root(root_flop, list(live_flop)):
            hits.append((root_str, root_flop, sigma))
    return hits


def _translate_combo(hero, sigma):
    """Mão do hero (naipes ao vivo) -> rótulo do pacote via σ^-1. Duas ordens de chave."""
    inv = {v: k for k, v in sigma.items()}
    try:
        c0 = hero[0][0] + inv[hero[0][1]]
        c1 = hero[1][0] + inv[hero[1][1]]
    except (KeyError, IndexError):
        return None
    return (c0 + c1, c1 + c0)


def _mix(actions, freq, *, min_show=0.08):
    pairs = sorted(zip(actions, freq), key=lambda x: -x[1])
    return [{'action': a, 'frequency': round(f, 4)} for a, f in pairs if f >= min_show]


def _recommended(actions, freq):
    return max(zip(actions, freq), key=lambda x: x[1])[0]


def _result(node, combo_key, freq, iso, extra_caveats=()):
    caveats = list(BASE_CAVEATS) + list(extra_caveats)
    if node['street'] == 'TURN':
        caveats.append('SOLVER_SHADOW_TURN_LIVE_MATCH_NEEDS_POSTFLOP_HISTORY')
    return dict(spot='btn_vs_bb_25_24boards', street=node['street'],
                actor_pos=node['actor_pos'], board=node['board'], iso=iso,
                actions=node['actions'], amounts_bb=node['amounts_bb'],
                pot_bb=node.get('pot_bb'), combo=combo_key, combo_in_range=True,
                freq=[round(x, 4) for x in freq],
                recommended_shadow=_recommended(node['actions'], freq),
                mix=_mix(node['actions'], freq),
                execution_allowed=False, caveats=caveats)


def _lookup_node(hero, live_flop, node_key_from_root, *, path=None):
    """Núcleo: para cada σ que casa o flop, monta a chave do nó via
    `node_key_from_root(root_str, root_flop, sigma)` e tenta achar o combo do hero."""
    pack = load_pack(path)
    if pack is None or not hero or len(hero) != 2 or not live_flop:
        return None
    hits = _match_board(list(live_flop)[:3], pack)
    if not hits:
        return None
    nodes = pack['nodes']
    for root_str, root_flop, sigma in hits:
        key = node_key_from_root(root_str, root_flop, sigma)
        if key is None:
            continue
        node = nodes.get(key)
        if node is None:
            continue
        keys = _translate_combo(hero, sigma)
        if not keys:
            continue
        combos = node['combos']
        combo_key = next((k for k in keys if k in combos), None)
        iso = (root_flop != list(live_flop)[:3])
        if combo_key is None:
            return dict(spot='btn_vs_bb_25_24boards', street=node['street'],
                        actor_pos=node['actor_pos'], board=node['board'], iso=iso,
                        actions=node['actions'], amounts_bb=node['amounts_bb'],
                        pot_bb=node.get('pot_bb'), combo_in_range=False,
                        recommended_shadow=None, freq=None, mix=None,
                        execution_allowed=False,
                        caveats=list(BASE_CAVEATS) + ['SOLVER_SHADOW_COMBO_NOT_IN_RANGE'])
        return _result(node, combo_key, combos[combo_key], iso)
    return None


def flop_cbet(hero, live_flop, *, path=None):
    """C-bet do BTN no flop (BB deu check), per-combo. None fora da cobertura dos 24."""
    if not live_flop or len(live_flop) != 3:
        return None

    def key(root_str, root_flop, sigma):
        return '%s#%s' % (root_str, '|'.join(HIST_BTN_CBET))
    return _lookup_node(hero, live_flop, key, path=path)


def _turn_lookup(hero, live_board4, line, actor, *, path=None):
    if not live_board4 or len(live_board4) != 4:
        return None
    pack = load_pack(path)
    if pack is None or not hero or len(hero) != 2:
        return None
    live_flop, live_turn = list(live_board4)[:3], live_board4[3]
    hits = _match_board(live_flop, pack)
    if not hits:
        return None
    slot = 'bb_turn' if actor == 'BB' else 'btn_turn'
    nodes, lines = pack['nodes'], pack['lines']
    for root_str, root_flop, sigma in hits:
        inv = {v: k for k, v in sigma.items()}
        try:
            ds_turn = live_turn[0] + inv[live_turn[1]]      # carta de turn no rótulo do pacote
        except (KeyError, IndexError):
            continue
        line_idx = lines.get(root_str, {}).get(line, {})
        entry = line_idx.get(ds_turn)
        if not entry or slot not in entry:
            continue
        node = nodes.get('%s#%s' % (''.join(root_flop + [ds_turn]), entry[slot]))
        if node is None:
            continue
        keys = _translate_combo(hero, sigma)
        if not keys:
            continue
        combos = node['combos']
        combo_key = next((k for k in keys if k in combos), None)
        iso = (root_flop != live_flop)
        if combo_key is None:
            return dict(spot='btn_vs_bb_25_24boards', street='TURN', line=line,
                        actor_pos=actor, board=node['board'], iso=iso,
                        actions=node['actions'], amounts_bb=node['amounts_bb'],
                        pot_bb=node.get('pot_bb'), combo_in_range=False,
                        recommended_shadow=None, freq=None, mix=None,
                        execution_allowed=False,
                        caveats=list(BASE_CAVEATS) + ['SOLVER_SHADOW_COMBO_NOT_IN_RANGE',
                                                      'SOLVER_SHADOW_TURN_LIVE_MATCH_NEEDS_POSTFLOP_HISTORY'])
        res = _result(node, combo_key, combos[combo_key], iso, extra_caveats=())
        res['line'] = line
        return res
    return None


def turn_lead(hero, live_board4, line, *, path=None):
    """Sombra do turn quando o hero é o BB e LIDERA (check-vs-aposta, to_call=0), na
    linha dada ('checkthrough' ou 'betcall'). Estudo/homologação. None fora da cobertura."""
    return _turn_lookup(hero, live_board4, line, 'BB', path=path)


def turn_barrel(hero, live_board4, line, *, path=None):
    """Sombra do turn quando o hero é o BTN e decide BARRELAR após o check do BB
    (check-vs-aposta, to_call=0), na linha dada. Estudo/homologação."""
    return _turn_lookup(hero, live_board4, line, 'BTN', path=path)
