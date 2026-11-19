"""Sombra de solver pós-flop GENÉRICA (SHADOW, NUNCA executa) — família IP-abre vs BB,
pote simples (single-raised), chip EV. Consome os packs do `import_texas_srp`
(`btn_vs_bb_40`, depois `btn_vs_bb_100`, etc.) e, por APROXIMAÇÃO de família, empresta
o estudo a spots semelhantes (ex.: CO vs BB).

Diferenças p/ o `solver_cbet_shadow` (btn_vs_bb_25, que fica intocado):
  - Dirigido por PACK (spot/stack/sizes vêm do arquivo), múltiplos stacks (40/100/...).
  - Sizes no VOCABULÁRIO do nosso slider: 1/3, 1/2, 2/3, all-in (t33/t50/t66/allin).
  - FLOP + TURN (turn = agregado de range na linha primária).
  - APROXIMAÇÃO: native_ip=BTN, mas aceita hero IP em POS_FAMILY (BTN/CO/HJ...) vs BB,
    com caveat. Empresta o bucket de stack vizinho quando fora do nativo (lei de
    cobertura por bucket).
  - EXCEÇÃO de size por SPR = Plano Geométrico por street (postflop_adjustments). A
    sombra só SINALIZA (caveat + plano de referência) quando o SPR pede geométrico no
    turn; não força size.

Segue o gate: execution_allowed=False, não troca a recomendação da heurística. Fora do
spot/stack/flop/rua cobertos devolve None e nada é dito.
"""
import json
import os
from functools import lru_cache
from itertools import permutations

import postflop_adjustments as _pa

RANKS = '23456789TJQKA'
SUITS = 'shdc'

# Posições IP que podem emprestar por aproximação o estudo de BTN (abre e joga IP vs BB
# em pote simples). Quanto mais longe do botão, mais "aproximação" — vira caveat, não veto.
POS_FAMILY = ('BTN', 'CO', 'HJ', 'LJ', 'MP', 'UTG')
# LEI DE COBERTURA (Eduardo 19/11, "nao morrer no pos-flop"): sem teto de bucket — SEMPRE
# empresta o pack de stack mais proximo (25/40/100...), com caveat honesto da distancia.
# Nenhuma profundidade fica descoberta; a aproximacao melhora conforme rodamos mais spots.
STACK_BORROW_MAX_BB = None
MIN_RANGE_WEIGHT = 0.25
DECISIVE_THRESHOLD = 0.80
# SPR a partir do qual o turn ganha nota de Plano Geométrico (encaixar shove no river):
# abaixo disso já estamos rasos e o size coarse resolve.
GEO_TURN_SPR_MIN = 1.5

_DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'strategy_data', 'postflop_solver')
# Packs desta família (o btn_vs_bb_25 NÃO entra aqui — é do solver_cbet_shadow).
_PACK_FILES = ('btn_vs_bb_40.json', 'btn_vs_bb_100.json')


def _canon(cards):
    best = None
    for perm in permutations(SUITS):
        m = dict(zip(SUITS, perm))
        s = ''.join(sorted((c[0] + m[c[1]] for c in cards),
                           key=lambda c: (-RANKS.index(c[0]), c[1])))
        if best is None or s < best:
            best = s
    return best


def _parse_flop(s):
    return [s[i:i + 2] for i in (0, 2, 4)]


class Pack:
    def __init__(self, data):
        self.family = data.get('family')
        self.native_ip = (data.get('native_ip') or 'BTN').upper()
        self.spot = data.get('spot')
        self.label = data.get('label')
        self.version = data.get('version')
        self.grading = data.get('grading')
        self.pot_bb = data.get('pot_bb')
        self.stack_bb = data.get('stack_bb')
        self.our_sizes = data.get('our_sizes') or []
        self._by_canon = {}
        for e in data.get('flops', []):
            self._by_canon[e.get('canon') or _canon(_parse_flop(e['flop']))] = e

    def match_flop(self, board):
        """(entry, [σ...]) isomórfico ao board (3 cartas), σ: naipe dataset->live."""
        if not board or len(board) != 3:
            return None, []
        try:
            key = _canon(list(board))
        except (ValueError, KeyError, IndexError):
            return None, []
        entry = self._by_canon.get(key)
        if entry is None:
            return None, []
        ds = _parse_flop(entry['flop'])
        live = sorted(board)
        sig = []
        for perm in permutations(SUITS):
            m = dict(zip(SUITS, perm))
            if sorted(c[0] + m[c[1]] for c in ds) == live:
                sig.append(m)
        return (entry, sig) if sig else (None, [])


@lru_cache(maxsize=8)
def _load_dir(directory=None):
    d = directory or os.environ.get('SOLVER_SRP_SHADOW_DIR') or _DEFAULT_DIR
    packs = []
    for fn in _PACK_FILES:
        p = os.path.join(d, fn)
        try:
            with open(p, encoding='utf-8') as fh:
                packs.append(Pack(json.load(fh)))
        except (OSError, ValueError, KeyError):
            continue
    return tuple(packs)


def _packs_by_proximity(eff_bb, directory=None):
    """Packs da família ordenados por proximidade de stack (bucket vizinho primeiro). Sem
    teto quando STACK_BORROW_MAX_BB é None (lei de cobertura: nunca morrer por profundidade
    descoberta)."""
    cand = []
    for pk in _load_dir(directory):
        if not isinstance(pk.stack_bb, (int, float)):
            continue
        dd = abs(pk.stack_bb - eff_bb)
        if STACK_BORROW_MAX_BB is not None and dd > STACK_BORROW_MAX_BB:
            continue
        cand.append((dd, pk))
    return [pk for _, pk in sorted(cand, key=lambda x: x[0])]


def _pick_pack_for_flop(eff_bb, board3, directory=None):
    """Pack de stack mais próximo QUE TAMBÉM COBRE o flop. Evita gap quando um pack (ex.:
    100bb parcial, 26 flops) está mais perto mas não tem a textura: cai no próximo (ex.:
    40bb, 100 flops). Devolve (pack, entry, sigmas) ou (None, None, [])."""
    for pk in _packs_by_proximity(eff_bb, directory):
        entry, sig = pk.match_flop(board3)
        if entry is not None:
            return pk, entry, sig
    return None, None, []


def _agg_for_combo(entry, sigmas, hero):
    agg = entry.get('agg') or {}
    for m in sigmas:
        inv = {v: k for k, v in m.items()}
        try:
            c0 = hero[0][0] + inv[hero[0][1]]
            c1 = hero[1][0] + inv[hero[1][1]]
        except (KeyError, IndexError):
            continue
        for key in (c0 + c1, c1 + c0):
            if key in agg:
                return agg[key], key
    return None, None


def _turn_for_card(entry, sigmas, turn_card):
    """Nó de turn (agregado) p/ a carta de turn ao vivo, traduzindo o naipe via σ."""
    turn = entry.get('turn') or {}
    if not turn or not turn_card:
        return None
    for m in sigmas:
        inv = {v: k for k, v in m.items()}          # live suit -> dataset suit
        try:
            ds_card = turn_card[0] + inv[turn_card[1]]
        except (KeyError, IndexError):
            continue
        if ds_card in turn:
            return turn[ds_card]
    return None


_BUCKET_FRAC = {'t33': 1.0 / 3.0, 't50': 0.5, 't66': 2.0 / 3.0}


def _size_faced(to_call_bb, pot_bb, eff_bb, def_keys):
    """Size de c-bet enfrentado pelo BB -> bucket de `def` (t33/t50/t66 ou allin), pelo
    valor real. `pot_bb` já inclui a aposta do vilão -> pote antes = pot - to_call."""
    if not isinstance(to_call_bb, (int, float)) or to_call_bb <= 0 or not def_keys:
        return None
    if isinstance(eff_bb, (int, float)) and to_call_bb >= eff_bb - 1e-6:
        return 'allin' if 'allin' in def_keys else None
    pot_before = (pot_bb - to_call_bb) if isinstance(pot_bb, (int, float)) else None
    if not pot_before or pot_before <= 0:
        return None
    frac = to_call_bb / pot_before
    cand = [(k, _BUCKET_FRAC[k]) for k in def_keys if k in _BUCKET_FRAC]
    if not cand:
        return None
    return min(cand, key=lambda kv: abs(kv[1] - frac))[0]


def _mix(actions, freq, min_show=0.10):
    return [{'action': a, 'frequency': round(f, 4)}
            for a, f in sorted(zip(actions, freq), key=lambda x: -x[1]) if f >= min_show]


def _coarse(actions, freq):
    """(ação_referência, decisivo?). Agrega qualquer aposta (t33/t50/t66/allin) em 'bet'
    p/ decidir check×bet; devolve também o size mais jogado quando aposta."""
    pairs = list(zip(actions, freq))
    check = sum(f for a, f in pairs if a == 'check')
    bet = sum(f for a, f in pairs if a != 'check')
    coarse = 'check' if check >= bet else 'bet'
    decisive = max(check, bet) >= DECISIVE_THRESHOLD
    size = None
    if coarse == 'bet':
        bets = [(a, f) for a, f in pairs if a != 'check']
        size = max(bets, key=lambda x: x[1])[0] if bets else None
    return coarse, decisive, size


def _geo_note(street, pot_bb, eff_bb):
    """Nota de Plano Geométrico p/ o turn: se o SPR pede geométrico, devolve o plano de
    referência (postflop_adjustments) e um caveat. A sombra NÃO força — só sinaliza."""
    if str(street).upper() != 'TURN':
        return None, []
    if not isinstance(pot_bb, (int, float)) or not isinstance(eff_bb, (int, float)):
        return None, []
    if pot_bb <= 0 or eff_bb <= 0:
        return None, []
    spr = eff_bb / pot_bb
    if spr < GEO_TURN_SPR_MIN:
        return None, []
    plan = _pa.geometric_street_plan(spr, 'TURN', pot_bb, eff_bb)
    if not plan:
        return None, []
    return (dict(spr=round(spr, 2), plan=plan),
            ['SOLVER_SHADOW_GEOMETRIC_PLAN_TURN',
             'SIZE_PODE_SER_GEOMETRICO_PARA_ENCAIXAR_SHOVE_RIVER'])


def lookup(hero, board, *, hero_pos, villain_pos, to_call_bb, pot_bb,
           hero_stack_bb=None, villain_stack_bb=None, street='flop',
           mode='chip_ev', turn_card=None, directory=None):
    """Sombra genérica IP-vs-BB SRP p/ UMA leitura, ou None se não coberto.

    FLOP: hero IP (to_call==0) -> c-bet [per-combo]; hero BB (to_call>0) -> def [agregado].
    TURN: hero IP, to_call==0, board de 4 cartas -> 2ª barrela [agregado por carta].
    Devolve dict com recommended_shadow/mix/freq/actions/caveats/execution_allowed=False.
    """
    # Postflop SRP c-bet é ~chip-EV mesmo em PKO (o bounty/ICM mexe sobretudo no all-in
    # pré-flop e na defesa OOP, não na c-bet IP). Lei de cobertura: aproveitar por
    # APROXIMAÇÃO em pko/pko_icm, com caveat. ICM PURO de bolha fica de fora (lá a
    # sobrevivência muda o pós-flop de verdade).
    if mode not in ('chip_ev', 'pko', 'pko_icm'):
        return None
    if not hero or len(hero) != 2 or not board:
        return None
    st = str(street).lower()
    hp, vp = (hero_pos or '').upper(), (villain_pos or '').upper()
    # Spot = IP (família) vs BB. Dois papéis do hero:
    #  - AGG: hero é o IP (abre e c-beta/barrela) -> per-combo (dirige).
    #  - DEF: hero é o BB enfrentando a c-bet do IP -> agregado (só GUIA).
    is_agg = (hp in POS_FAMILY and vp == 'BB')
    is_def = (hp == 'BB' and vp in POS_FAMILY)
    if not (is_agg or is_def):
        return None
    eff = min([s for s in (hero_stack_bb, villain_stack_bb)
               if isinstance(s, (int, float))] or [None])
    if eff is None:
        return None
    flop3 = board[:3]
    pack, entry, sigmas = _pick_pack_for_flop(eff, flop3, directory)
    if pack is None or entry is None:
        return None

    caveats = ['POSTFLOP_SOLVER_SHADOW', 'SOLVER_SHADOW_NOT_FOR_EXECUTION',
               'SOLVER_GRADING_FREQ_NO_EV', 'SOLVER_SHADOW_SPOT_%s' % (pack.spot or '').upper()]
    ip_pos = hp if is_agg else vp                # posição do IP (p/ caveat de aproximação)
    if ip_pos != pack.native_ip:
        caveats.append('SOLVER_SHADOW_SPOT_APPROX_%s_DE_%s' % (ip_pos, pack.native_ip))
    if mode != 'chip_ev':
        caveats.append('SOLVER_SHADOW_CHIP_EV_APPROX_EM_%s' % mode.upper())
    if isinstance(pack.stack_bb, (int, float)) and abs(pack.stack_bb - eff) > 1e-6:
        caveats.append('SOLVER_SHADOW_STACK_BUCKET_%g_PARA_%gBB' % (pack.stack_bb, eff))

    common = dict(spot=pack.spot, family=pack.family, native_ip=pack.native_ip,
                  source=pack.version, grading=pack.grading, flop=entry['flop'],
                  iso=(entry['flop'] != ''.join(flop3)), our_sizes=pack.our_sizes,
                  execution_allowed=False)

    # ---------- TURN: 2ª barrela do IP (agregado por carta) ----------
    if st == 'turn':
        if is_agg:
            if (to_call_bb in (0, None)) and len(board) >= 4:
                tc = turn_card or (board[3] if len(board) > 3 else None)
                tnode = _turn_for_card(entry, sigmas, tc)
                if tnode is None:
                    return None
                actions, freq = tnode['actions'], tnode['freq']
                coarse, decisive, size = _coarse(actions, freq)
                geo, geo_cav = _geo_note('turn', pot_bb, eff)
                return dict(common, side='agg', per_combo=False, node='ip_turn_barrel',
                            street='turn', turn_card=tc, turn_after=entry.get('turn_after'),
                            recommended_shadow=coarse, bet_size=size, decisive=decisive,
                            mix=_mix(actions, freq), actions=actions, freq=freq,
                            geometric=geo,
                            caveats=caveats + ['SOLVER_SHADOW_TURN_RANGE_AGGREGATE'] + geo_cav)
        return None

    # ---------- FLOP ----------
    if st != 'flop' or len(board) != 3:
        return None

    # Nó 1: IP decide c-bet depois do check do BB (per-combo).
    if is_agg and (to_call_bb in (0, None)):
        freq, combo_key = _agg_for_combo(entry, sigmas, hero)
        actions = entry.get('agg_actions') or pack.our_sizes
        if freq is None:
            return dict(common, side='agg', per_combo=True, node='ip_cbet_vs_check',
                        street='flop', recommended_shadow=None, combo_in_range=False,
                        mix=None, actions=actions, freq=None,
                        caveats=caveats + ['SOLVER_SHADOW_COMBO_BELOW_RANGE_WEIGHT'])
        coarse, decisive, size = _coarse(actions, freq)
        return dict(common, side='agg', per_combo=True, node='ip_cbet_vs_check',
                    street='flop', combo=combo_key, combo_in_range=True,
                    recommended_shadow=coarse, bet_size=size, decisive=decisive,
                    mix=_mix(actions, freq), actions=actions, freq=freq, caveats=caveats)

    # Nó 2: hero BB responde à c-bet do IP (AGREGADO do range -> só GUIA, não dirige a
    # mão específica; igual à disciplina do btn_vs_bb_25). Mapeia o size enfrentado ao
    # bucket de `def` do pack.
    if is_def and isinstance(to_call_bb, (int, float)) and to_call_bb > 0:
        defs = entry.get('def') or {}
        size = _size_faced(to_call_bb, pot_bb, eff, list(defs.keys()))
        node = defs.get(size) if size else None
        if not node:
            return None
        actions, freq = node['actions'], node['freq']
        coarse = max(zip(actions, freq), key=lambda x: x[1])[0]
        decisive = max(freq) >= DECISIVE_THRESHOLD
        return dict(common, side='def', per_combo=False, node='bb_vs_cbet', street='flop',
                    bet_faced=size, recommended_shadow=coarse, decisive=decisive,
                    mix=_mix(actions, freq), actions=actions, freq=freq,
                    caveats=caveats + ['SOLVER_SHADOW_DEF_RANGE_AGGREGATE_NAO_PER_COMBO'])
    return None
