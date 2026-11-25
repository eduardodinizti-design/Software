"""Sombra de solver pós-flop (SHADOW, NUNCA executa) — pacote `btn_vs_bb_25`.

Overlay de SOMBRA sobre o conselho pós-flop: quando o spot ao vivo é exatamente o
que o TexasSolver resolveu (BTN abre, BB paga, ~25bb, pote de um raise só, FLOP) e
o board cai num dos 100 flops do pacote (por ISOMORFISMO de naipe), anexa a
frequência REAL do solver ao lado do que a heurística já decidiu. Não troca a
recomendação, não libera execução: é estudo/auditoria (segue o gate — solver em
sombra até homologação). Fora do spot/flop cobertos devolve None e nada é dito.

Dois nós cobertos (ver `import-texas-cbet.py`, que gerou o pacote):
  - `agg`: c-bet do BTN (IP) DEPOIS do BB dar check. PER-COMBO (freq da mão do hero
    sobre [check, b33, b50, b70, allin]). Só combos com peso de range IP >= 0.25.
  - `def`: resposta do BB (OOP) a cada size de aposta do BTN. AGREGADO do range
    (não é por combo): freq média sobre [call, raise, fold].

Limites honestos embutidos (viram caveats na saída):
  - Só FLOP (o pacote não gravou turn/river).
  - `def` é agregado de range, não específico da mão do hero.
  - `grading='freq'` (sem EV por ação): a ação mais jogada é a de referência; >=10%
    conta como mista aceita.
  - chip EV (o pacote não tem ICM/PKO).
"""
import json
import os
from functools import lru_cache
from itertools import permutations

RANKS = '23456789TJQKA'
SUITS = 'shdc'

SPOT = 'btn_vs_bb_25'
# Profundidade coberta (bb efetivos). O pacote é 25bb; aceitamos uma janela estreita
# em volta — fora dela a dinâmica muda o bastante p/ não emprestar o nó.
STACK_MIN_BB = 20.0
STACK_MAX_BB = 30.0
# Peso mínimo de range IP p/ um combo estar no pacote `agg` (igual ao do conversor).
# Um combo do hero ausente do `agg` => fora do range de open / peso baixo: dizemos isso
# em vez de inventar frequência.
MIN_RANGE_WEIGHT = 0.25

# Ações do lado agressor (IP), na ordem do pacote.
AGG_ACTIONS = ('check', 'b33', 'b50', 'b70', 'allin')
# Fração de pote nominal de cada size de aposta do BTN (p/ mapear o size enfrentado
# pelo BB ao nó `def` correto). 'allin' é tratado à parte (cobre o stack).
BET_FRACTIONS = (('b33', 0.33), ('b50', 0.50), ('b70', 0.70))

# Caminho padrão: o pacote vive dentro do próprio cérebro (auto-contido). Override por
# variável de ambiente p/ testes/realocação.
_DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             'strategy_data', 'postflop_solver', 'btn_vs_bb_25.json')


def _data_path(path=None):
    return path or os.environ.get('SOLVER_CBET_SHADOW_PATH') or _DEFAULT_PATH


def _canon(cards):
    """Forma canônica de um flop (menor string sobre as permutações de naipe) — a MESMA
    do conversor `import-texas-cbet.py`, p/ casar o índice por isomorfismo."""
    best = None
    for perm in permutations(SUITS):
        m = dict(zip(SUITS, perm))
        s = ''.join(sorted((c[0] + m[c[1]] for c in cards),
                           key=lambda c: (-RANKS.index(c[0]), c[1])))
        if best is None or s < best:
            best = s
    return best


def _parse_flop(flop_str):
    """'8h2s2d' -> ['8h','2s','2d']."""
    return [flop_str[i:i + 2] for i in (0, 2, 4)]


class ShadowPack:
    """Pacote de sombra carregado e indexado por flop canônico. Imutável após carga."""

    def __init__(self, data):
        self.spot = data.get('spot')
        self.label = data.get('label')
        self.version = data.get('version')
        self.grading = data.get('grading')
        self.pot_bb = data.get('pot_bb')
        self.stack_bb = data.get('stack_bb')
        self.note = data.get('note')
        self._by_canon = {}
        for entry in data.get('flops', []):
            self._by_canon[_canon(_parse_flop(entry['flop']))] = entry

    def _match_flop(self, board):
        """Acha a entrada do pacote isomórfica ao `board` (3 cartas) e as permutações de
        naipe σ (dataset->live) que levam o flop do pacote EXATAMENTE no board ao vivo.
        Devolve (entry, [σ...]) ou (None, []). σ é dict suit->suit."""
        if not board or len(board) != 3:
            return None, []
        try:
            key = _canon(list(board))
        except (ValueError, KeyError, IndexError):
            return None, []
        entry = self._by_canon.get(key)
        if entry is None:
            return None, []
        ds_cards = _parse_flop(entry['flop'])
        live_set = sorted(board)
        sigmas = []
        for perm in permutations(SUITS):
            m = dict(zip(SUITS, perm))
            mapped = sorted(c[0] + m[c[1]] for c in ds_cards)
            if mapped == live_set:
                sigmas.append(m)
        return (entry, sigmas) if sigmas else (None, [])

    def _agg_for_combo(self, entry, sigmas, hero):
        """Freq per-combo do lado `agg` (c-bet do BTN) p/ a mão do hero, traduzindo os
        naipes do hero p/ a rotulagem do pacote via σ^-1 (dataset<-live). Testa todas as
        σ e as duas ordens da chave; por simetria de naipe a freq é a mesma onde existir.
        Devolve (freq_list, combo_key) ou (None, None) se o combo não está no pacote."""
        agg = entry.get('agg') or {}
        for m in sigmas:
            inv = {v: k for k, v in m.items()}          # live suit -> dataset suit
            try:
                c0 = hero[0][0] + inv[hero[0][1]]
                c1 = hero[1][0] + inv[hero[1][1]]
            except (KeyError, IndexError):
                continue
            for key in (c0 + c1, c1 + c0):
                if key in agg:
                    return agg[key], key
        return None, None


def _load(path):
    with open(path, encoding='utf-8') as fh:
        return ShadowPack(json.load(fh))


@lru_cache(maxsize=4)
def load_pack(path=None):
    """Carrega (e cacheia) o pacote de sombra. None se o arquivo não existe/ilegível —
    a sombra some em silêncio, nunca quebra o conselho."""
    p = _data_path(path)
    try:
        return _load(p)
    except (OSError, ValueError, KeyError):
        return None


def _mix(actions, freq, *, min_show=0.10):
    """[(ação, freq)] ordenado por freq desc; só ações com freq >= min_show (mix aceito)."""
    pairs = sorted(zip(actions, freq), key=lambda x: -x[1])
    return [{'action': a, 'frequency': round(f, 4)} for a, f in pairs if f >= min_show]


def _recommended(actions, freq):
    """Ação de referência = a mais jogada (argmax da freq do solver)."""
    return max(zip(actions, freq), key=lambda x: x[1])[0]


# Limiar p/ um nó ser DECISIVO (uma ação coarse domina). Abaixo disso é MISTO e a
# camada "solver-preferido" NÃO sobrepõe a heurística (coinflip não vira regra).
DECISIVE_THRESHOLD = 0.80


def _agg_coarse(freq):
    """(coarse, decisive, bet_size) do lado agg. coarse 'check'/'bet'; bet_size = o maior
    size apostado (b33/b50/b70/allin) quando aposta, senão None."""
    check = freq[0]
    bet_sum = sum(freq[1:])
    coarse = 'check' if check >= bet_sum else 'bet'
    decisive = max(check, bet_sum) >= DECISIVE_THRESHOLD
    bet_size = None
    if coarse == 'bet':
        # ordem de AGG_ACTIONS[1:] = b33,b50,b70,allin
        bet_size = max(zip(AGG_ACTIONS[1:], freq[1:]), key=lambda x: x[1])[0]
    return coarse, decisive, bet_size


def _def_coarse(actions, freq):
    """(coarse, decisive) do lado def: argmax call/raise/fold e se domina (>= limiar)."""
    coarse = max(zip(actions, freq), key=lambda x: x[1])[0]
    return coarse, max(freq) >= DECISIVE_THRESHOLD


def _size_faced(to_call_bb, pot_bb, hero_stack_bb, villain_stack_bb):
    """Mapeia a aposta do BTN enfrentada pelo BB ao nó `def` (b33/b50/b70/allin).
    `pot_bb` já inclui a aposta do vilão -> pote antes = pot - to_call."""
    if not isinstance(to_call_bb, (int, float)) or to_call_bb <= 0:
        return None
    # All-in: o vilão apostou ~o stack efetivo (cobre o hero / compromete tudo).
    eff = None
    stacks = [s for s in (hero_stack_bb, villain_stack_bb) if isinstance(s, (int, float))]
    if stacks:
        eff = min(stacks)
    if eff is not None and to_call_bb >= eff - 1e-6:
        return 'allin'
    pot_before = pot_bb - to_call_bb if isinstance(pot_bb, (int, float)) else None
    if not pot_before or pot_before <= 0:
        return None
    frac = to_call_bb / pot_before
    # Aposta muito grande (> ~85% do pote) sem ser all-in cai no maior size do pacote.
    if frac >= 0.85:
        return 'b70'
    return min(BET_FRACTIONS, key=lambda x: abs(x[1] - frac))[0]


def lookup(hero, board, *, hero_pos, villain_pos, to_call_bb, pot_bb,
           hero_stack_bb=None, villain_stack_bb=None, mode='chip_ev',
           aggressor=None, path=None):
    """Sombra do solver p/ UMA leitura, ou None se o spot/flop não é coberto.

    Cobre só: FLOP, pote de um raise só BTN vs BB ~25bb chip EV, e um dos dois nós:
      - hero = BTN (IP), to_call == 0  -> c-bet do BTN (BB deu check) [per-combo].
      - hero = BB (OOP), to_call > 0   -> resposta do BB à aposta do BTN [agregado].

    Devolve dict com `recommended_shadow`, `mix`, `freq`, `actions`, `caveats` e
    `execution_allowed=False`. NÃO decide nada: é overlay de estudo/auditoria.
    """
    if not hero or len(hero) != 2 or not board or len(board) != 3:
        return None                                      # só flop (3 cartas)
    if mode != 'chip_ev':
        return None                                      # pacote é chip EV
    hp = (hero_pos or '').upper()
    vp = (villain_pos or '').upper()
    if {hp, vp} != {'BTN', 'BB'}:
        return None                                      # spot é exatamente BTN vs BB
    eff = min([s for s in (hero_stack_bb, villain_stack_bb)
               if isinstance(s, (int, float))] or [None])
    if eff is None or not (STACK_MIN_BB <= eff <= STACK_MAX_BB):
        return None                                      # fora da profundidade coberta
    pack = load_pack(path)
    if pack is None:
        return None
    entry, sigmas = pack._match_flop(board)
    if entry is None:
        return None                                      # flop fora dos 100 do pacote

    base_caveats = ['POSTFLOP_SOLVER_SHADOW', 'SOLVER_SHADOW_NOT_FOR_EXECUTION',
                    'SOLVER_SHADOW_FLOP_ONLY', 'SOLVER_GRADING_FREQ_NO_EV',
                    'SOLVER_SHADOW_SPOT_%s' % SPOT.upper()]
    if eff != pack.stack_bb:
        base_caveats.append('SOLVER_SHADOW_STACK_BUCKET_%g_FOR_%gBB' % (pack.stack_bb, eff))

    common = dict(spot=SPOT, source=pack.version, grading=pack.grading,
                  flop=entry['flop'], stratum=entry.get('stratum'),
                  iso=(entry['flop'] != ''.join(board)), execution_allowed=False)

    # --- Nó 1: BTN (IP) decide c-bet depois do check do BB (to_call == 0) ---
    if hp == 'BTN' and (to_call_bb == 0 or to_call_bb is None):
        freq, combo_key = pack._agg_for_combo(entry, sigmas, hero)
        if freq is None:
            # Flop coberto, mas a mão do hero não está no range de open do BTN (peso
            # < %.2f) -> honesto: sem freq per-combo, não inventa.
            return dict(common, side='agg', per_combo=True, node='btn_cbet_vs_check',
                        recommended_shadow=None, combo_in_range=False, mix=None,
                        actions=list(AGG_ACTIONS), freq=None,
                        caveats=base_caveats + ['SOLVER_SHADOW_COMBO_BELOW_RANGE_WEIGHT'])
        coarse, decisive, bet_size = _agg_coarse(freq)
        return dict(common, side='agg', per_combo=True, node='btn_cbet_vs_check',
                    combo=combo_key, combo_in_range=True,
                    actions=list(AGG_ACTIONS), freq=[round(x, 4) for x in freq],
                    recommended_shadow=_recommended(AGG_ACTIONS, freq),
                    coarse=coarse, decisive=decisive, bet_size=bet_size,
                    mix=_mix(AGG_ACTIONS, freq), caveats=list(base_caveats))

    # --- Nó 2: BB (OOP) responde à aposta do BTN (to_call > 0) ---
    if hp == 'BB' and isinstance(to_call_bb, (int, float)) and to_call_bb > 0:
        size = _size_faced(to_call_bb, pot_bb, hero_stack_bb, villain_stack_bb)
        node = (entry.get('def') or {}).get(size) if size else None
        if not node:
            return None                                  # size enfrentado fora da árvore
        actions, freq = node['actions'], node['freq']
        coarse, decisive = _def_coarse(actions, freq)
        return dict(common, side='def', per_combo=False, node='bb_vs_cbet',
                    bet_faced=size, actions=list(actions), freq=[round(x, 4) for x in freq],
                    recommended_shadow=_recommended(actions, freq),
                    coarse=coarse, decisive=decisive,
                    mix=_mix(actions, freq),
                    caveats=base_caveats + ['SOLVER_SHADOW_DEF_RANGE_AGGREGATE_NOT_PER_COMBO'])

    return None                                          # nó não coberto (donk, x/r, etc.)
