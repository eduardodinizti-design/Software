"""Exploratory live preflop advisor over the NVT range reference.

Separate from preflop_study.py: that module is a strict, exact-match SIMULATION
validator; this one turns the live table reading into a usable recommendation by
consulting the validated range pack at the nearest stack bucket. It is labelled
EXPLORATORY and never authorises execution.

The NVT pack is a reference, optimised for short stacks. VALIDATED buckets are
5-25bb (9-max, chip EV + ICM + PKO). Buckets 30/40bb exist as UNVALIDATED REFERENCE
(advise, never auto-execute; flagged UNVALIDATED_REFERENCE_RANGE). Deep buckets
50/60/80/100bb are the DEEP ladder: 100bb is HRC-solved (chip EV + PKO early/mid,
9-max, bounty 0.53/0.71), the intermediate rungs 50/60/80 have no solve yet and
BORROW the nearest populated bucket (flagged), so a deep table advises instead of
abstaining. Stacks above the top bucket (100bb) reuse the 100bb range as a flagged
reference (STACK_ABOVE_SOLVED_DEPTH). Post-flop is out of coverage here.

No capture, no clicks. Stack bucketing and the 9-max table are explicit
approximations, reported in every answer.
"""
import hashlib
import json
from pathlib import Path

from preflop_study import hand_key, Blocked
from preflop_equity import range_from_node, equity_vs_range, required_equity
from hud_exploit import classify_villain, shove_calloff_delta, exploit_caveats
import preflop_exploit
from strategy.scenarios import classify as classify_scenario, from_table_state
from preflop_tree_book import TreeBook

RAISE_FLOOR_BB = 1.5  # a bet above the BB (1.0) is a raise, not a blind post
# Detecção de open-shove (all-in de primeira aposta): separa o open/iso normal
# (2-3bb) de um jam. Prefere o stack atrás do abridor (~0 = all-in); sem leitura
# de stack, usa o tamanho da aposta como proxy.
SHOVE_MIN_BET_BB = 3.5        # abaixo disso é open/iso normal, nunca shove
SHOVE_REMAINING_BB = 0.75     # stack atrás <= isso => efetivamente all-in
SHOVE_SIZE_FALLBACK_BB = 5.0  # sem stack lido, 1ª aposta >= isso é tratada como shove
# Preflop action order (earliest to latest); the opener is the earliest-position
# player among those at the top bet level, callers having matched that bet later.
_PREFLOP_ORDER = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB')

# Camada heurística: spots cuja range muda devagar com o stack e SEM troca de regime
# (min-raise x shove) podem pegar emprestada a range validada do stack mais próximo.
# vs_3bet / vs_open_shove ficam de FORA (território de call-off por equity, que é mais
# preciso que emprestar). open_shove entra para o push/fold curto.
BORROWABLE_SPOTS = frozenset({'open_raise', 'open_shove', 'vs_open', 'vs_limp'})
SHOVE_SPOTS = frozenset({'open_shove', 'vs_open_shove'})   # tabelas puras de push/fold
# Spots de PUSH/FOLD onde, faltando o nó exato do contexto (tipicamente spreads
# enviesados curtos_ini/curtos_fim ou PKO), cabe uma REFERÊNCIA Nash SOMBRA: reusa a
# MESMA tabela Nash de um contexto vizinho (spread 'iguais' do mesmo modo/stage, ou
# Nash chip-EV), marcada validated=False. Não inventa range; só sinaliza a aproximação.
NASH_SHADOW_SPOTS = frozenset({'open_shove', 'vs_open_shove', '3bet_shove'})
PUSHFOLD_MAX_BB = 12   # <= isso, first-in tenta SHOVE antes de open-raise
# ZONA DE SHOVE: abaixo disso o hero está em regime de push/fold. NÃO se pega range
# emprestada por proximidade de stack para spots de RAISE (open_raise/vs_open/
# vs_limp) — emprestar uma range de open aqui produz MINI-RAISES SUICIDAS. Só
# tabelas puras de push/fold (open_shove/vs_open_shove) valem. Além disso, o
# first-in tenta o SHOVE antes do open-raise nessa zona.
SHOVE_ZONE_MAX_BB = 20
# Até este stack um 3bet enfrentado é efetivamente COMMIT (4bet-jam/call-off), mesmo sem
# nó validado (o pack só tem vs_3bet a 25bb). Cobre a fresta 20-25bb em pko/icm.
VS3BET_JAM_MAX_BB = 25

_RANKS = '23456789TJQKA'


def _hand_tier(cards):
    """Tier de força pré-flop (teoria mais próxima p/ o fallback "nunca abstém"):
    premium / strong / playable / trash. Grosso mas SEMPRE classifica (nunca None)."""
    try:
        a, b = cards[0], cards[1]
        ra, rb = _RANKS.index(a[0].upper()), _RANKS.index(b[0].upper())
        suited = a[1].lower() == b[1].lower()
    except Exception:                                # noqa: BLE001
        return 'trash'
    hi, lo = max(ra, rb), min(ra, rb)
    pair = ra == rb
    T, N, S, A_ = _RANKS.index('T'), _RANKS.index('9'), _RANKS.index('7'), _RANKS.index('A')
    if pair and hi >= T:
        return 'premium'                             # TT+
    if hi == A_ and lo == _RANKS.index('K'):
        return 'premium'                             # AK
    if pair and hi >= S:
        return 'strong'                              # 77-99
    if hi == A_ and lo >= _RANKS.index('Q'):
        return 'strong'                              # AQ+
    if suited and hi >= _RANKS.index('K') and lo >= _RANKS.index('T'):
        return 'strong'                              # KTs+/KQs/QJs-ish
    if pair:
        return 'playable'                            # 22-66
    if hi == A_:
        return 'playable'                            # qualquer Ax
    if hi >= T and lo >= T:
        return 'playable'                            # broadways offsuit
    if suited and (hi - lo) <= 1 and lo >= _RANKS.index('5'):
        return 'playable'                            # suited connectors médios+
    if suited and hi >= _RANKS.index('K'):
        return 'playable'                            # Kxs
    return 'trash'


_GAP_SEEN = set()


def _log_gap(flag):
    """APONTA o gap de cobertura (p/ cobertura real posterior com solver). Append em
    logs/gaps_cobertura.jsonl, dedup em memória por (reason,spot,heroPos,bucket,tier,facing).
    Passivo; nunca quebra o cérebro."""
    try:
        bucket = None
        stk = flag.get('stack_bb')
        if isinstance(stk, (int, float)):
            bucket = min((5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100),
                         key=lambda s: abs(s - stk))
        key = (flag.get('reason'), flag.get('spot'), flag.get('hero_pos'), bucket,
               flag.get('tier'), flag.get('facing'))
        if key in _GAP_SEEN:
            return
        _GAP_SEEN.add(key)
        import json as _j
        import os as _os
        d = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'logs')
        _os.makedirs(d, exist_ok=True)
        with open(_os.path.join(d, 'gaps_cobertura.jsonl'), 'a', encoding='utf-8') as fh:
            fh.write(_j.dumps(dict(flag, bucket=bucket), ensure_ascii=False) + '\n')
    except Exception:                                # noqa: BLE001
        pass


# Catalog stack-distribution profiles by position (UTG..BB), from the engine's
# nearestSpread. "iguais" = even; "curtos_ini"/"curtos_fim" = the short stacks sit
# in the early / late positions. A real table is classified to the nearest one.
_SPREADS = {
    'iguais':     (25, 25, 25, 25, 25, 25, 25, 25, 25),
    'curtos_fim': (35, 35, 30, 30, 25, 20, 15, 15, 20),
    'curtos_ini': (15, 15, 20, 20, 25, 30, 35, 35, 30),
}


def infer_spread(position_stacks, min_seats=5):
    """Nearest catalog ICM stack spread for the table (iguais/curtos_ini/
    curtos_fim), replicating the engine's nearestSpread: compare each seat's
    stack-to-mean ratio against each profile's, pick the least-squares nearest.
    Returns None when too few stacks are known to classify (keep the default)."""
    seats = [(_PREFLOP_ORDER.index(p), st) for p, st in (position_stacks or {}).items()
             if p in _PREFLOP_ORDER and isinstance(st, (int, float)) and st > 0]
    if len(seats) < min_seats:
        return None
    mean = sum(st for _, st in seats) / len(seats)
    best, best_dist = 'iguais', float('inf')
    for name, prof in _SPREADS.items():
        m = sum(prof[i] for i, _ in seats) / len(seats)
        dist = sum((st / mean - prof[i] / m) ** 2 for i, st in seats)
        if dist < best_dist - 1e-9:
            best_dist, best = dist, name
    return best


def _bet_levels(amounts):
    """Group raise amounts into distinct levels (callers matching a raise sit on
    the same level). Returns the sorted list of level representatives, low->high.
    A single level is a raised pot (with any number of callers); two or more
    levels mean a reraise happened (3bet/4bet)."""
    levels = []
    for a in sorted(amounts):
        if not levels or a > levels[-1] + max(0.5, 0.15 * levels[-1]):
            levels.append(a)
        else:
            levels[-1] = max(levels[-1], a)
    return levels


def _opener_is_shove(table_state, opener_position, opener_bet):
    """O abridor está all-in? Usa o stack atrás dele (seats[...]['stack_bb']) se
    lido (~0 => shove); senão cai no tamanho da aposta. Opens normais (2-3bb) e
    isos (<=~4bb) não disparam."""
    if not isinstance(opener_bet, (int, float)) or opener_bet < SHOVE_MIN_BET_BB:
        return False
    positions = table_state.get('positions') or {}
    seats = table_state.get('seats') or {}
    seat = next((s for s, p in positions.items() if p == opener_position), None)
    remaining = (seats.get(seat) or {}).get('stack_bb') if seat else None
    # 1) stack ATRÁS do abridor ~0 => all-in dele.
    if isinstance(remaining, (int, float)) and remaining <= SHOVE_REMAINING_BB:
        return True
    # 2) ROBUSTO (não depende de ler o stack do ABRIDOR, que falha — causou o KK vs 3bet-shove
    #    virar four_bet): se a aposta do abridor >= o stack do HERO, o hero NÃO consegue raisar
    #    (só call-off all-in ou fold) = facing-all-in. Usa o stack do hero (lido confiável).
    hero_stack = (seats.get('hero') or {}).get('stack_bb')
    if isinstance(hero_stack, (int, float)) and hero_stack > 0 and opener_bet >= hero_stack:
        return True
    # 3) sem stack do abridor lido: aposta gigante (>= fallback) é shove.
    if remaining is None:
        return opener_bet >= SHOVE_SIZE_FALLBACK_BB
    return False


def infer_live_spot(table_state):
    """Spot pré-flop para o roteamento ao vivo, DELEGADO ao classificador ÚNICO do
    B08 (`strategy.scenarios.classify`). Esta função é um ADAPTADOR: converte o
    cenário explícito (com limpers/callers) para o shape legado usado por
    `advise_from_reading` ({spot, opener, callers, allin, reason}). Assim há UM só
    caminho de classificação (laboratório e ao vivo) — limps deixam de virar
    first_in e os callers não somem. A detecção de SHOVE (stack atrás ~0) segue
    via `_opener_is_shove`, que o classificador de estrutura não faz."""
    c = classify_scenario(from_table_state(table_state))
    scen = c['scenario']
    opener = c.get('aggressor')
    top = max(c['raise_levels']) if c.get('raise_levels') else 0.0

    if scen in ('unopened', 'limped'):
        # Pote não aberto OU só limpado: o hero abre/isola. O roteamento first_in já
        # trata os limpers (iso) na camada seguinte; o cenário 'limped' é marcado.
        return dict(spot='first_in', opener=None, limpers=c['n_limpers'])
    if scen in ('open', 'open_with_callers', 'limp_then_iso'):
        if _opener_is_shove(table_state, opener, top):
            return dict(spot='vs_open_shove', opener=opener, callers=c['n_callers'], allin=True)
        return dict(spot='vs_open', opener=opener, callers=c['n_callers'])
    if scen == 'vs_3bet':
        # min-3bet com stack atrás NÃO é shove (allin=False) -> sem call-off por equity.
        return dict(spot='vs_3bet', opener=opener,
                    allin=_opener_is_shove(table_state, opener, top))
    if scen == 'threebet_cold':
        # hero enfrenta open + 3bet (cold). Sem nó -> advise_from_reading decide no
        # short (jam/call premium, resto fold); deep segue abstendo. allin=3bettor shovou.
        return dict(spot='threebet_cold', opener=opener,
                    allin=_opener_is_shove(table_state, opener, top),
                    reason='MULTIWAY_OR_3BET_NOT_COVERED')
    if scen == 'vs_4bet_or_more':
        return dict(spot='abstain', opener=None, reason='MULTIWAY_OR_4BET_NOT_COVERED')
    # pending: hero abriu sem reraise, ou sequência ambígua -> abstém (motivo legado).
    reason = 'HERO_OPENED_NO_RERAISE' if c.get('reason') == 'HERO_RAISED_NO_RERAISE' \
        else (c.get('reason') or 'NOT_COVERED')
    return dict(spot='abstain', opener=None, reason=reason)


def _sb_limped(table_state):
    """O SB completou o limp (~1bb, não um raise)? O nó `vs_limp` do pack modela a
    batalha de blinds (BB vs limp do SB), então a rota só vale nesse caso."""
    positions = table_state.get('positions') or {}
    sb_seat = next((s for s, p in positions.items() if p == 'SB'), None)
    if sb_seat is None:
        return False
    sb_bet = next((b.get('bet_bb') for b in (table_state.get('bets') or [])
                   if b.get('seat') == sb_seat), None)
    return isinstance(sb_bet, (int, float)) and 0.9 <= sb_bet <= 1.1


# Risk premium (ICM) de referência por fase, com stacks iguais (paráfrase da skill
# poker-icm-mtt): ~2,2% a 75% do field, 3,5% a 50%, 7,9% a 25%, ~13,5% na bolha;
# pico também na mesa final. Aproximação por FASE — não é ICM resolvido.
ICM_STAGE_RP = {'pre_itm': 0.09, 'bubble': 0.135, 'ft': 0.12}


def _icm_risk_premium(mode, stage, to_call_bb, stack_bb):
    """Equity extra (pontos) exigida além das pot odds no call-off, por ICM.

    0 em chip EV. Em ICM, parte do RP de referência da fase e escala pela FRAÇÃO
    do stack em risco (proxy de cobertura: arriscar pouco do stack = hero cobre o
    shove curto = pressão ICM menor; all-in = RP cheio). PKO desconta (bounties
    aliviam, às vezes RP negativo). Aproximação explícita, não um solver de ICM."""
    if mode not in ('icm', 'pko_icm'):
        return 0.0
    base = ICM_STAGE_RP.get(stage, 0.05)
    if mode == 'pko_icm':
        base *= 0.6
    if isinstance(to_call_bb, (int, float)) and isinstance(stack_bb, (int, float)) and stack_bb > 0:
        base *= max(0.0, min(1.0, to_call_bb / stack_bb))
    return round(base, 4)


def scale_bounty_bb(base_bb, bounties, villain_position, positions):
    """Escala o `base_bb` (BB-equity do bounty INICIAL, entrada --bounty-bb) pelo bounty
    do VILÃO lido na mesa: base_bb × (bounty_vilão / bounty_base). `bounty_base` = menor
    bounty lido (o inicial; quem ainda não eliminou ninguém carrega a base). Alvo que
    ACUMULOU KOs (bounty > base) vale mais -> caça mais larga. Sem base_bb ou sem leitura
    do vilão -> base_bb sem escala (flag). Devolve (bounty_bb_efetivo, caveat|None)."""
    if not base_bb:
        return base_bb, None
    vals = {s: v for s, v in (bounties or {}).items() if isinstance(v, (int, float)) and v > 0}
    if not vals:
        return base_bb, 'BOUNTY_READ_NONE_FLAT_BASE'
    vseat = next((s for s, p in (positions or {}).items() if p == villain_position), None)
    vb = vals.get(vseat)
    base = min(vals.values())
    if not vb or base <= 0:
        return base_bb, 'BOUNTY_VILLAIN_UNREAD_FLAT_BASE'
    mult = vb / base
    return round(base_bb * mult, 2), 'BOUNTY_SCALED_x%.2f_VILLAIN_%g_BASE_%g' % (mult, vb, base)


class PreflopAdvisor:
    # Short stacks (5-25) come from the validated NVT pack; 30/40 from the deep
    # reference pack (not HRC-validated, flagged in every answer). 100 is HRC-solved
    # deep (chip EV + PKO early/mid). 50/60/80 are ladder rungs with no solve yet:
    # they borrow the nearest populated bucket (flagged). 100 is the top bucket;
    # deeper stacks reuse it as a flagged reference (see bucket_stack).
    STACK_BUCKETS = (5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 80, 100)
    # ALINHAMENTO DE BUCKET POR MODO: cada modo tem sua GRADE NATIVA de solves
    # (chip_ev/icm cobrem 30/40; PKO topa em 25; PKO-ICM usa 25/35/100 — grades
    # DIFERENTES). Quando o stack real cai ENTRE os buckets nativos do modo (ex.:
    # 40bb PKO-ICM, cujo solve mora em 35bb), o lookup exato falha. Se o bucket
    # nativo mais próximo COM nó validado do MESMO contexto estiver a <= ALIGN_TOL
    # do stack real, é um ALINHAMENTO de grade (não um empréstimo heurístico): conta
    # como VALIDADO, exatamente como chip_ev 33bb->30bb já conta hoje. Fora da
    # tolerância cai no borrow flagged (validated=False) — honesto: 40bb PKO (nativo
    # só até 25bb = 38%) NÃO vira coberto, é range genuinamente faltando.
    ALIGN_TOL = 0.20
    # Clone 0.5: nossos cenários (strategy.scenarios) vs os nomes das árvores solved.
    _TREE_SCENARIO_ALIASES = {'vs_4bet_or_more': 'vs_4bet'}

    def __init__(self, pack, *, sources=None, strict=True, tree_book=None):
        if pack.get('format') != 'nvt-range-export' or pack.get('version') != 1:
            raise Blocked('UNSUPPORTED_RANGE_FORMAT')
        self.hands = pack['hands']
        if len(self.hands) != 169:
            raise Blocked('INVALID_HAND_INDEX')
        self.nodes = list(pack['nodes'])   # includes unvalidated reference (deep) nodes
        self.engine_commit = pack.get('engineCommit')
        self.sources = list(sources or [])  # B01: origem(ns) por sha256 (ver manifest())
        self.strict = strict
        # Clone 0.5: livro de árvores de EV solved (deep/multiway) para spots específicos.
        # Fonte de ESTUDO (validated=False/execution_allowed=False) — ver advise().
        # Carga PREGUIÇOSA (só no 1º consult opt-in) p/ não pesar construções em testes.
        self.tree_book = tree_book
        # B02 — índice de lookup SEM sombra silenciosa. Nós que compartilham a mesma
        # chave são uma COLISÃO: um nó velho JAMAIS pode esconder calado um nó
        # atualizado. Precedência explícita: um nó VALIDADO sempre vence um de
        # referência não-validado (qualquer que seja a ordem de carga) -> um update
        # validado nunca é sombreado por uma range de referência. Dois nós do MESMO
        # nível de validação com uma chave só é ambiguidade real: em strict é FATAL
        # no load (conserta-se a fonte/manifesto, B01), no laboratório e não com ficha;
        # fora do strict, mantém o primeiro e REGISTRA o descarte em self.collisions.
        self._index = {}
        self.collisions = []
        grouped = {}
        for n in self.nodes:
            grouped.setdefault(self._key_of(n), []).append(n)
        for key, group in grouped.items():
            if len(group) == 1:
                self._index[key] = group[0]
                continue
            validated = [n for n in group if n.get('validated') is True]
            pool = validated or group
            if len(pool) > 1 and strict:
                raise Blocked('AMBIGUOUS_RANGE_NODE:%s' %
                              ','.join(sorted(str(n.get('id')) for n in pool)))
            chosen = pool[0]
            self._index[key] = chosen
            self.collisions.append(dict(
                key=key, count=len(group), chosen=chosen.get('id'),
                dropped=[n.get('id') for n in group if n is not chosen],
                resolved_by=('validated_over_reference'
                             if validated and len(validated) < len(group) else 'first_kept')))
        self._shove_cache = {}
        self._equity_cache = {}          # (node_id, cartas, iters, seed) -> equity bruta

    @staticmethod
    def _source_entry(path, raw, pack):
        """Entrada do manifesto de fontes (B01): path + sha256 dos BYTES exatos do
        pack + contagem de nós/validados + proveniência do motor. É a ponte
        auditável da decisão ao vivo de volta à fonte exata."""
        nodes = pack.get('nodes') or []
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
                    nodes=len(nodes),
                    validated=sum(1 for n in nodes if n.get('validated') is True),
                    engine_commit=pack.get('engineCommit'),
                    generated_at=pack.get('generatedAt'))

    def manifest(self):
        """Manifesto de proveniência (B01): quais pack(s), por sha256, alimentam o
        lookup; cobertura de nós; e colisões de chave resolvidas no load. Liga uma
        decisão ao vivo às fontes exatas (bytes)."""
        return dict(sources=list(self.sources), engine_commit=self.engine_commit,
                    total_nodes=len(self.nodes),
                    validated_nodes=sum(1 for n in self.nodes if n.get('validated') is True),
                    index_keys=len(self._index), collisions=list(self.collisions),
                    strict=self.strict)

    @classmethod
    def from_file(cls, path, *, strict=True):
        raw = Path(path).read_bytes()
        pack = json.loads(raw.decode('utf-8'))
        return cls(pack, sources=[cls._source_entry(path, raw, pack)], strict=strict)

    @classmethod
    def from_files(cls, *paths, strict=False):
        """Merge several packs (e.g. the validated short pack plus the deep
        reference pack). They must share format/version and the 169-hand index.
        Cada fonte entra no manifesto por sha256 (B01); colisões de chave entre os
        packs são resolvidas sem sombra silenciosa (B02, ver __init__).

        strict=False por padrão (ao contrário de __init__/from_file): um merge é,
        por natureza, onde fontes distintas se sobrepõem — ex.: o pack `deep`
        reexporta nós de bucket curto que também estão no pack validado. Em vez de
        QUEBRAR o operador no startup, o merge resolve de forma determinística pela
        ORDEM do manifesto (a 1ª fonte passada é a autoritária: passe o pack
        validado PRIMEIRO) e REGISTRA cada colisão em self.collisions / manifest()
        para auditoria. Passe strict=True para exigir fontes sem sobreposição."""
        merged = None
        sources = []
        for path in paths:
            raw = Path(path).read_bytes()
            pack = json.loads(raw.decode('utf-8'))
            sources.append(cls._source_entry(path, raw, pack))
            if merged is None:
                merged = dict(pack)
            elif pack.get('hands') != merged['hands']:
                raise Blocked('HAND_INDEX_MISMATCH_BETWEEN_PACKS')
            else:
                merged = dict(merged, nodes=merged['nodes'] + pack['nodes'])
        return cls(merged, sources=sources, strict=strict)

    @staticmethod
    def _key_of(node):
        c = node['context']
        return (c['mode'], c['format'], c['stage'], c['players'], c['stack'],
                node['spot'], node['hero'], tuple(node.get('vs') or ()),
                node.get('spread'))

    def bucket_stack(self, stack_bb):
        """Nearest covered stack bucket, or (None, reason) when out of coverage.

        The solved solutions top out at the 100bb bucket, but real tournaments
        play deeper, especially early. Preflop open/3bet ranges change slowly when
        deep, so a stack at or beyond the top bucket (100bb) uses the 100bb range as
        the best available reference (the extrapolation is flagged in the caveats),
        rather than abstaining and leaving a common deep table without advice."""
        if not isinstance(stack_bb, (int, float)) or stack_bb <= 0:
            return None, 'STACK_UNKNOWN'
        if stack_bb >= self.STACK_BUCKETS[-1]:
            return self.STACK_BUCKETS[-1], 'OK'
        return min(self.STACK_BUCKETS, key=lambda s: abs(s - stack_bb)), 'OK'

    def open_range_combos(self, position, stack_bb, *, mode='chip_ev', stage='mid',
                          players=9, spread=None, table_format=None):
        """Range de OPEN (combos ponderados) de `position` no pack validado.

        Reusa o nó spot='open_raise' (ação 'raise') via `range_from_node`. É o range
        do AGRESSOR pré-flop num pote de UM raise só — NÃO estreitado pela ação
        pós-flop (quem usa sinaliza isso nos caveats). Serve de range do vilão para a
        equity pós-flop (estimada por Monte Carlo). Devolve (combos, node) ou (None, motivo)."""
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return None, why
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, table_format, stage, players, bucket,
                                'open_raise', position, (), spread))
        if node is None:                         # degrau vazio (ex.: 60bb) -> empresta o solved mais próximo
            node, _ = self._nearest_stack_node(
                mode, table_format, stage, players, 'open_raise', position, (), spread, bucket)
        if node is None:
            return None, 'NO_OPEN_NODE_FOR_CONTEXT'
        combos = range_from_node(node, self.hands, actions=('raise',))
        return (combos or None), node

    def call_range_combos(self, caller_position, opener_position, stack_bb, *,
                          mode='chip_ev', stage='mid', players=9, spread=None, table_format=None):
        """Range de FLAT (combos ponderados) de `caller_position` ao enfrentar o open
        de `opener_position`, no pack validado (nó spot='vs_open', ação 'call'). É o
        range do vilão num pote de um raise só quando o HERO abriu e o vilão pagou —
        complementa `open_range_combos`. Devolve (combos, node) ou (None, motivo)."""
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return None, why
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, table_format, stage, players, bucket,
                                'vs_open', caller_position, (opener_position,), spread))
        if node is None:                         # degrau vazio -> empresta o solved mais próximo
            node, _ = self._nearest_stack_node(
                mode, table_format, stage, players, 'vs_open', caller_position,
                (opener_position,), spread, bucket)
        if node is None:
            return None, 'NO_VS_OPEN_NODE_FOR_CONTEXT'
        combos = range_from_node(node, self.hands, actions=('call',))
        return (combos or None), node

    def _nearest_stack_node(self, mode, table_format, stage, players, spot, hero, vs, spread, bucket):
        """Nó do MESMO contexto no stack coberto mais próximo (p/ a camada heurística
        de fallback). Em empate de distância, prefere o stack MAIOR — ranges mais
        fundas (raise puro) são mais seguras de emprestar para baixo do que ranges de
        jam (push/fold) para cima. Devolve (node, stack_de_origem) ou (None, None)."""
        for s in sorted((x for x in self.STACK_BUCKETS if x != bucket),
                        key=lambda x: (abs(x - bucket), -x)):
            node = self._index.get((mode, table_format, stage, players, s, spot, hero, vs, spread))
            if node is not None:
                return node, s
        return None, None

    def _nash_shadow_node(self, mode, table_format, stage, players, bucket, spot, hero, vs, spread):
        """Referência Nash SOMBRA para a zona de shove quando o nó EXATO do contexto
        não existe. NÃO inventa range: devolve a MESMA tabela Nash de um contexto
        vizinho já validado no pack, com o caveat que explicita a aproximação:
          1) mesmo modo/stage/bucket, spread 'iguais' (assume stacks parelhos) — é o
             nó ICM/PKO-ICM correto do stage, só sem o viés de spread;
          2) Nash chip-EV do mesmo (bucket, spot, hero, vs) — sem ajuste ICM/PKO.
        Só para NASH_SHADOW_SPOTS (push/fold puro). Devolve (node, caveat) ou (None,
        None). O chamador marca validated=False (nunca auto-executa)."""
        if spot not in NASH_SHADOW_SPOTS:
            return None, None
        if spread != 'iguais':                           # (1) mesmo modo/stage, spread parelho
            n = self._index.get((mode, table_format, stage, players, bucket, spot, hero, vs, 'iguais'))
            if n is not None:
                return n, 'NASH_SHADOW_SPREAD_IGUAIS_APPROX'
        if not (mode == 'chip_ev' and table_format == 'regular'  # (2) Nash chip-EV
                and stage == 'mid' and spread is None):
            n = self._index.get(('chip_ev', 'regular', 'mid', players, bucket, spot, hero, vs, None))
            if n is not None:
                return n, 'NASH_SHADOW_CHIP_EV_REF_ICM_PKO_ADJ_NOT_APPLIED'
        # (3) COBERTURA DO CONTEXTO (não da mão): nenhum nó no bucket exato -> empresta o
        # BUCKET mais próximo que TENHA a tabela de push/fold (preferindo 'iguais' do
        # mesmo modo/stage; senão o Nash chip-EV). Push/fold só ALARGA com stack menor,
        # então a range do bucket vizinho é aproximação SEGURA. Garante que TODA a zona
        # de shove tenha decisão (shove/fold) — qualquer mão, qualquer short — em vez de
        # abster (Eduardo 19/11: atacar o contexto do range, não a mão específica).
        best = None
        for b in self.STACK_BUCKETS:
            for key in ((mode, table_format, stage, players, b, spot, hero, vs, 'iguais'),
                        ('chip_ev', 'regular', 'mid', players, b, spot, hero, vs, None)):
                n = self._index.get(key)
                if n is not None:
                    d = abs(b - (bucket or 0))
                    if best is None or d < best[0]:
                        best = (d, n)
                    break
        if best is not None:
            return best[1], 'NASH_SHADOW_NEAREST_BUCKET_APPROX'
        return None, None

    def _aligned_stack_node(self, mode, table_format, stage, players, spot, hero, vs, spread, stack_bb):
        """Nó VALIDADO do MESMO contexto no bucket NATIVO do modo mais próximo, quando
        o stack real cai ENTRE os buckets nativos (grades diferentes por modo — ver
        ALIGN_TOL). DIFERE de _nearest_stack_node: aqui só vale se o bucket nativo
        mais próximo COM nó VALIDADO estiver a <= ALIGN_TOL do stack real (adjacente
        na grade do modo) -> o nó conta como VALIDADO (alinhamento de grade, não
        empréstimo de regime). Devolve (node, bucket_alinhado) ou (None, None)."""
        if not isinstance(stack_bb, (int, float)) or stack_bb <= 0:
            return None, None
        best = None
        for b in self.STACK_BUCKETS:
            node = self._index.get((mode, table_format, stage, players, b, spot, hero, vs, spread))
            if node is None or node.get('validated') is not True:
                continue
            d = abs(b - stack_bb)
            if best is None or d < best[0]:
                best = (d, b, node)
        if best is None:
            return None, None
        d, b, node = best
        if d / stack_bb <= self.ALIGN_TOL:
            return node, b
        return None, None

    def _trees(self):
        """TreeBook (Clone 0.5) carregado sob demanda. Diretório ausente -> livro
        vazio (glob não acha nada), nunca erro. Cacheado (inclusive vazio)."""
        if self.tree_book is None:
            try:
                self.tree_book = TreeBook.from_directory()
            except Exception:                        # noqa: BLE001 — árvore é opcional
                self.tree_book = TreeBook()
        return self.tree_book

    def advise(self, *, hero_cards, hero_position, stack_bb, mode='chip_ev',
               table_format=None, stage='mid', players=9, spot='open_raise', vs=(), spread=None,
               scenario=None, aggressor=None, limpers=(), callers=(), effective_stack_bb=None,
               to_beat=None, to_call=None, facing_all_in=False, tournament_profile=None,
               reference_tree_study=False, _nash_shadow_ok=False):
        """An exploratory recommendation for one preflop spot, or an abstention.

        Returns status ADVICE | ABSTAIN | OUT_OF_RANGE with the action mix, EVs,
        the recommended (most frequent) action, and the approximations made. ICM/
        PKO nodes carry a stack spread; absent one, equal stacks ('iguais') are
        assumed and flagged.

        Camada de ÁRVORE DE REFERÊNCIA (Clone 0.5): para spots específicos deep/
        multiway (vs_3bet, vs_4bet, open_with_callers, limped) existe uma árvore
        solved offline. Consulta OPT-IN: só quando o caller informa `scenario`.
        NUNCA auto-executável (validated=False/execution_allowed=False); se não
        casar, segue EXATAMENTE o fluxo normal (callers sem `scenario` não mudam)."""
        if scenario is not None:
            tree_adv = self._tree_consult(
                hero_cards=hero_cards, scenario=scenario, hero_position=hero_position,
                aggressor=aggressor, limpers=limpers, callers=callers, mode=mode, stage=stage,
                stack_bb=stack_bb,
                effective_stack_bb=effective_stack_bb if effective_stack_bb is not None else stack_bb,
                to_beat=to_beat, to_call=to_call, facing_all_in=facing_all_in,
                tournament_profile=tournament_profile, reference_tree_study=reference_tree_study)
            if tree_adv is not None:
                return tree_adv
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return self._abstain(why, stack_bb=stack_bb)
        try:
            hand = hand_key(hero_cards)
        except Blocked as exc:
            return self._abstain(str(exc))
        spread_was_default = spread is None and mode in ('icm', 'pko_icm')
        spread = spread if spread is not None else ('iguais' if mode in ('icm', 'pko_icm') else None)
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, table_format, stage, players, bucket, spot, hero_position, tuple(vs), spread))
        # Convenção de spread: os solves PKO early/mid do tipo tournament-model
        # (pkoearly/pkomid) são gravados SEM spread (spread=None), ao contrário dos
        # ICM-staged (bubble/ft/preitm, que são 'iguais'/'curtos'). Quando o caller
        # não informou spread e o nó 'iguais' não existe, tenta o nó sem-spread do
        # MESMO contexto ANTES de emprestar range de outro stack — senão um PKO mid
        # de 100bb responderia (errado) com um range de pre-ITM 25bb emprestado.
        if node is None and spread_was_default:
            alt = self._index.get((mode, table_format, stage, players, bucket, spot,
                                   hero_position, tuple(vs), None))
            if alt is not None:
                node, spread = alt, None
        aligned_bucket = None
        # ALINHAMENTO DE GRADE POR MODO: o bucket global snapou para um degrau que o
        # MODO não solva (ex.: 40bb PKO-ICM -> solve mora em 35bb). Antes do borrow
        # heurístico, procura o bucket NATIVO validado do MESMO contexto a <=ALIGN_TOL
        # do stack real. Gated a >= SHOVE_ZONE_MAX_BB: abaixo disso o regime é
        # push/fold e NÃO se realinha spot de raise (preserva a guarda anti mini-raise).
        if node is None and isinstance(stack_bb, (int, float)) and stack_bb >= SHOVE_ZONE_MAX_BB:
            anode, ab = self._aligned_stack_node(
                mode, table_format, stage, players, spot, hero_position, tuple(vs), spread, stack_bb)
            if anode is not None:
                node, aligned_bucket, bucket = anode, ab, ab
        borrowed_from = None
        # GUARDA DA ZONA DE SHOVE (<20BB): não empresta range de RAISE por proximidade
        # de stack — isso gerava mini-raises suicidas. Só push/fold puro vale aqui.
        shove_zone = isinstance(stack_bb, (int, float)) and stack_bb < SHOVE_ZONE_MAX_BB
        blocked_borrow = shove_zone and spot in BORROWABLE_SPOTS and spot not in SHOVE_SPOTS
        if node is None and spot in BORROWABLE_SPOTS and not blocked_borrow:
            # Camada heurística: sem nó no bucket exato, PEGA EMPRESTADA a range
            # validada do stack mais próximo (flagged). Vira conselho em vez de
            # abstenção — mas NÃO é auto-executável (validated=False abaixo).
            node, borrowed_from = self._nearest_stack_node(
                mode, table_format, stage, players, spot, hero_position, tuple(vs), spread, bucket)
        # CAMADA NASH SOMBRA (ÚLTIMO RECURSO, só push/fold): sem nó no contexto exato
        # nem empréstimo de stack, reusa a tabela Nash de um contexto vizinho como
        # REFERÊNCIA (validated=False). Fecha a ABSTENÇÃO em spreads enviesados/PKO
        # curtos sem inventar range. GATED por `_nash_shadow_ok`: só o re-try explícito
        # de último recurso (fim de advise_from_reading, quando o fluxo normal já
        # abstém) a liga — assim a sombra NUNCA preempta um nó validado/melhor.
        nash_shadow = None
        if node is None and _nash_shadow_ok:
            node, nash_shadow = self._nash_shadow_node(
                mode, table_format, stage, players, bucket, spot, hero_position, tuple(vs), spread)
        if node is None:
            reason = 'SHOVE_ZONE_PUSHFOLD_ONLY_NO_BORROW' if blocked_borrow \
                else 'NO_VALIDATED_NODE_FOR_CONTEXT'
            return self._abstain(reason,
                                 context=dict(mode=mode, stage=stage, stack=bucket, spot=spot,
                                              hero=hero_position, players=players))
        i = self.hands.index(hand)
        raw_validated = bool(node.get('validated'))
        # stack emprestado OU sombra Nash de outro contexto não auto-executam
        validated = raw_validated and borrowed_from is None and nash_shadow is None
        caveats = self._caveats(bucket, stack_bb, players, mode, spread)
        if not raw_validated:
            caveats.append('UNVALIDATED_REFERENCE_RANGE')
        if nash_shadow is not None:
            caveats.append(nash_shadow)
        if aligned_bucket is not None:
            caveats.append('BUCKET_ALIGNED_%gBB_TO_%dBB_NATIVE_GRID' % (stack_bb, aligned_bucket))
        if borrowed_from is not None:
            caveats.append('STACK_BORROWED_%dBB_TO_%dBB_HEURISTIC' % (borrowed_from, bucket))
        base = dict(spot=spot, hero_position=hero_position, hand=hand, node_id=node['id'],
                    source=node['source'], validated=validated, exploratory=True,
                    execution_allowed=False, stack_bb=stack_bb, stack_bucket=bucket,
                    stack_borrowed_from=borrowed_from,
                    bucketed=bucket != stack_bb, players_assumed=players, caveats=caveats)
        if i in (node.get('outOfRange') or []):
            return dict(base, status='OUT_OF_RANGE')
        mix, ev = [], {}
        for act in node['actions']:
            freq = node['freq'][act][i]
            if freq > 0:
                mix.append(dict(action=act, frequency=freq))
            values = (node.get('ev') or {}).get(act)
            ev[act] = values[i] if values is not None and len(values) == 169 else None
        recommended = max(mix, key=lambda m: m['frequency'])['action'] if mix else None
        return dict(base, status='ADVICE', mix=mix, ev=ev, ev_unit=node['evUnit'], recommended=recommended)

    def _tree_consult(self, *, hero_cards, scenario, hero_position, aggressor, limpers,
                      callers, mode, stage, stack_bb, effective_stack_bb, to_beat, to_call,
                      facing_all_in, tournament_profile, reference_tree_study):
        """Consulta o TreeBook (Clone 0.5) e devolve um conselho NÃO-executável, ou
        None (sem árvore -> o advise segue o fluxo normal). Cenário traduzido dos
        nossos nomes (strategy.scenarios) p/ os das árvores."""
        book = self._trees()
        if not getattr(book, 'records', None):
            return None
        tree_scenario = self._TREE_SCENARIO_ALIASES.get(scenario, scenario)
        try:
            hand = hand_key(hero_cards)
        except Blocked:
            return None            # cartas inválidas: deixa o fluxo normal abster
        ctx = dict(scenario=tree_scenario, hero_position=hero_position, aggressor=aggressor,
                   limpers=list(limpers or ()), callers=list(callers or ()),
                   mode=mode, stage=stage, effective_stack_bb=effective_stack_bb,
                   to_beat=to_beat, to_call=to_call, facing_all_in=facing_all_in,
                   tournament_profile=tournament_profile,
                   reference_tree_study=reference_tree_study)
        node = book.lookup(hero_cards, ctx)
        if node is None:
            return None
        return self._tree_answer(node, hero_cards, hand, scenario, hero_position,
                                 stack_bb, effective_stack_bb)

    def _tree_answer(self, node, hero_cards, hand, scenario, hero_position,
                     stack_bb, effective_stack_bb):
        """Monta o conselho de árvore no MESMO contrato do advise(). SEMPRE
        validated=False e execution_allowed=False: o operador trata como estudo
        (sombra) e NÃO clica. NÃO projeta all-in de árvore curta em stack fundo
        (reinterpretação fica no executor, que aqui nunca roda)."""
        options = node['options']
        active = [o for o in options if o['frequency'] > 0]
        recommended = max(options, key=lambda o: o['frequency'])['action'] if options else None
        tree_depth = node['context']['effective_stack_bb']
        caveats = ['CONTEXTUAL_TREE_REFERENCE', 'UNVALIDATED_REFERENCE_RANGE']
        if node.get('research_only'):
            caveats.append('STUDY_ONLY_TREE_NOT_CONVERGED')
        if tree_depth != effective_stack_bb:
            caveats.append('TREE_DEPTH_%gBB_OBSERVED_%gBB' % (tree_depth, effective_stack_bb))
        return dict(
            status='ADVICE', phase='preflop', origin='CONTEXTUAL_TREE_REFERENCE',
            spot=scenario, hero_position=hero_position, hand=hand, hero_cards=list(hero_cards),
            node_id=node['id'], source=node['source'], source_sha256=node['sha256'],
            validated=False, solver_validated=False, source_validated=False,
            execution_allowed=False, exploratory=True,
            stack_bb=stack_bb, stack_bucket=tree_depth, effective_stack_bb=effective_stack_bb,
            bucketed=tree_depth != effective_stack_bb,
            mix=[dict(action=o['action'], frequency=o['frequency']) for o in active],
            recommended=recommended,
            ev={o['action']: o.get('reference_ev_bb') for o in options},
            ev_unit='reference_bb_relative_to_fold',
            reference_reasons=node.get('reference_reasons'),
            tree_quality=node.get('quality'), research_only=node.get('research_only'),
            caveats=caveats)

    def explain(self, *, hero_cards, hero_position, stack_bb, mode='chip_ev',
                table_format=None, stage='mid', players=9, spot='open_raise', vs=(), spread=None):
        """B03 — consulta EXPLICÁVEL. Roda advise() e devolve uma explicação
        estruturada que LIGA a recomendação à FONTE (sha256 do(s) pack(s) + nó) e
        mostra EXATAMENTE as aproximações feitas (bucket de stack, stack emprestado,
        mesa 9-max de referência, profundidade acima do solve). Diagnóstico offline;
        não captura nem clica. Critério B04/B05: cada recomendação tem fonte, hash e
        nó; toda aproximação mostra a diferença."""
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        try:
            hand = hand_key(hero_cards)
        except Blocked:
            hand = None
        adv = self.advise(hero_cards=hero_cards, hero_position=hero_position, stack_bb=stack_bb,
                          mode=mode, table_format=table_format, stage=stage, players=players,
                          spot=spot, vs=tuple(vs), spread=spread)
        node = next((n for n in self.nodes if n.get('id') == adv.get('node_id')), None)
        requested = dict(mode=mode, table_format=table_format, stage=stage, players=players,
                         stack_bb=stack_bb, spot=spot, hero=hero_position, vs=list(vs),
                         spread=spread, hand=hand)
        source = dict(node_id=adv.get('node_id'), source=adv.get('source'),
                      validated=adv.get('validated'),
                      pack_sha256=[s.get('sha256') for s in self.sources] or None,
                      node_context=(node or {}).get('context'))
        # DIFERENÇAS exatas entre o contexto pedido e o nó de fonte usado.
        diffs = {}
        if adv.get('stack_bucket') is not None and adv.get('stack_bucket') != stack_bb:
            diffs['stack_bucketed'] = dict(from_bb=stack_bb, to_bucket=adv.get('stack_bucket'))
        if adv.get('stack_borrowed_from') is not None:
            diffs['stack_borrowed_from_bb'] = adv.get('stack_borrowed_from')
        if players != 9:
            diffs['players_requested_vs_9max_ref'] = players
        if isinstance(stack_bb, (int, float)) and stack_bb > self.STACK_BUCKETS[-1]:
            diffs['above_solved_depth_top_bucket'] = self.STACK_BUCKETS[-1]
        return dict(requested=requested, source=source, differences=diffs,
                    answer=dict(status=adv.get('status'), recommended=adv.get('recommended'),
                                mix=adv.get('mix'), ev=adv.get('ev'), reason=adv.get('reason'),
                                caveats=adv.get('caveats')),
                    exploratory=True, execution_allowed=adv.get('execution_allowed'))

    def advise_first_in(self, **kwargs):
        """First-in (unopened): respeita o REGIME por stack. Na ZONA DE SHOVE
        (<SHOVE_ZONE_MAX_BB) tenta SHOVE antes do open-raise (push/fold puro); mais
        fundo, open-raise antes do shove. A guarda de zona de shove já impede o
        empréstimo de ranges de raise aqui — juntas eliminam o mini-raise suicida."""
        kwargs.pop('spot', None)
        kwargs.pop('vs', None)
        stack = kwargs.get('stack_bb')
        short = isinstance(stack, (int, float)) and stack < SHOVE_ZONE_MAX_BB
        order = ('open_shove', 'open_raise') if short else ('open_raise', 'open_shove')
        result = None
        for spot in order:
            result = self.advise(spot=spot, vs=(), **kwargs)
            if not (result['status'] == 'ABSTAIN'
                    and result.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'):
                return result
        # SB/BB NÃO têm range de OPEN (não abrem). Mas com LIMPER o hero ISOLA (não é blind
        # battle) — usa a range de REFERÊNCIA do BTN (mesma régua do `_iso_worthy`) p/ ter um
        # NÓ REAL executável, em vez de cair na aproximação sem nó (bug do AQ/AA no BB vs
        # limpers: advise_from_reading dava raise não-executável -> operador abstinha).
        pos = kwargs.get('hero_position')
        if pos in ('SB', 'BB'):
            ref_kwargs = dict(kwargs, hero_position='BTN')
            for spot in order:
                r2 = self.advise(spot=spot, vs=(), **ref_kwargs)
                if not (r2['status'] == 'ABSTAIN'
                        and r2.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'):
                    # no BB o fold é de graça -> CHECK (nunca foldar com check disponível).
                    if pos == 'BB' and r2.get('recommended') == 'fold':
                        r2['recommended'] = 'check'
                        r2.setdefault('caveats', []).append('BB_CHECK_GRATIS_EM_VEZ_DE_FOLD')
                    r2.setdefault('caveats', []).append('ISO_REF_BTN_PARA_%s' % pos)
                    return r2
        return result

    def _iso_worthy(self, hand, bucket, *, mode='chip_ev', stage='mid', players=9, position='UTG'):
        """Mão vale um ISO sobre limper? Régua = o range de OPEN DA POSIÇÃO DO HERÓI
        (BTN/CO isola LARGO; EP isola apertado). Antes usava UTG fixo em toda posição,
        o que foldava iso ÓBVIO de posição tardia (44 no BTN, A4o no CO — bug relatado
        pelo Eduardo 18/11). Folda só o que a PRÓPRIA posição não abriria (lixo).
        O range de blind-battle do SB (~91%) não serve de régua: com limper não é blind
        battle. Sem nó p/ a posição, cai no UTG; sem nada -> não bloqueia."""
        tf = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        # SB/BB abrem em BLIND-BATTLE (~91%, largo demais p/ régua de iso) -> usa o
        # range do BTN (sólido, não blind-battle) p/ esses; demais usam a própria.
        ref = 'BTN' if position in ('SB', 'BB') else position
        node = (self._index.get((mode, tf, stage, players, bucket, 'open_raise', ref, (), None))
                or self._index.get((mode, tf, stage, players, bucket, 'open_raise', 'UTG', (), None)))
        if node is None or hand not in self.hands:
            return True
        i = self.hands.index(hand)
        if i in (node.get('outOfRange') or []):
            return False
        freq = node['freq'].get('raise') or []
        return i < len(freq) and freq[i] > 0

    # Famílias de árvore (Clone 0.5) que o classificador ÚNICO pode casar ao vivo.
    _TREE_LIVE_SCENARIOS = frozenset({'vs_3bet', 'vs_4bet_or_more', 'open_with_callers', 'limped'})

    def _tree_from_reading(self, table_state, hero_cards, positions, hero, kwargs):
        """Consulta a árvore de referência a partir da leitura ao vivo, pelo mesmo
        classificador (strategy.scenarios). Devolve o conselho de ESTUDO (nunca
        executável) ou None (sem árvore -> roteamento normal). Shove -> facing_all_in
        True, então a árvore NÃO-terminal não é usada num all-in."""
        if not getattr(self._trees(), 'records', None):
            return None
        try:
            c = classify_scenario(from_table_state(table_state))
        except Exception:                                # noqa: BLE001 — leitura ruim -> fluxo normal
            return None
        scen = c.get('scenario')
        if scen not in self._TREE_LIVE_SCENARIOS or c.get('hero_position') is None:
            return None
        top = max(c['raise_levels']) if c.get('raise_levels') else 0.0
        facing_all_in = bool(c.get('aggressor')) and _opener_is_shove(table_state, c['aggressor'], top)
        stack_bb = hero.get('stack_bb')
        return self._tree_consult(
            hero_cards=hero_cards, scenario=scen, hero_position=c['hero_position'],
            aggressor=c.get('aggressor'), limpers=c.get('limpers') or (),
            callers=c.get('callers') or (), mode=kwargs.get('mode', 'chip_ev'),
            stage=kwargs.get('stage', 'mid'), stack_bb=stack_bb,
            effective_stack_bb=stack_bb, to_beat=top or None,
            to_call=(table_state.get('to_call') or {}).get('to_call_bb'),
            facing_all_in=facing_all_in, tournament_profile=kwargs.get('tournament_profile'),
            reference_tree_study=kwargs.get('reference_tree_study', False))

    # Abstenções de PERCEPÇÃO (leitura falhou): o fallback não inventa ação em cima de
    # leitura ruim -> fica ABSTAIN e o operador joga o seguro (anti-freeze). As demais
    # (COBERTURA) NUNCA abstêm: viram ação pela teoria mais próxima (Eduardo 19/11).
    _PERCEPTION_ABSTAINS = frozenset({
        'HERO_POSITION_UNKNOWN', 'HERO_CARDS_UNKNOWN', 'STACK_UNKNOWN'})

    def advise_from_reading(self, table_state, hero_cards, **kwargs):
        """LEI "NUNCA ABSTÉM" (Eduardo 19/11): nunca devolve ABSTAIN por falta de
        cobertura. Roda o núcleo; se abstiver por COBERTURA, tapa com a teoria mais
        próxima (tier de mão: push/fold curto, open/call fundo) e FLAGGA o gap
        (caveats GAP_COBERTURA_APROX/APONTAR_PARA_SOLVER + `gap_flag`) p/ cobertura real
        posterior com solver. Só ABSTÉM em falha de PERCEPÇÃO (leitura)."""
        table_state = self._derive_to_call(table_state)   # deriva to_call dos bets se OCR não leu
        r = self._advise_from_reading_core(table_state, hero_cards, **kwargs)
        if (isinstance(r, dict) and r.get('status') == 'ABSTAIN'
                and r.get('reason') not in self._PERCEPTION_ABSTAINS):
            try:
                fb = self._never_abstain_fallback(table_state, hero_cards, r)
            except Exception:                       # noqa: BLE001 — fallback nunca quebra
                fb = None
            if isinstance(fb, dict):
                return fb
        return r

    @staticmethod
    def _derive_to_call(table_state):
        """Se o OCR NÃO leu o to_call (None) mas há bets por assento, deriva
        to_call = max(0, maior aposta do vilão - aposta do hero). Evita o `to_call=0.0`
        enganoso num spot facing-a-bet (pot-odds / call-off errados = "acha que é de graça").
        Só age quando None (não sobrescreve leitura real); marca derived=True p/ auditoria."""
        tc = (table_state.get('to_call') or {}).get('to_call_bb')
        if tc is not None:
            return table_state
        bets = table_state.get('bets') or []
        vals = [b.get('bet_bb') for b in bets if isinstance(b.get('bet_bb'), (int, float))]
        if not vals:
            return table_state
        maxbet = max(vals)
        herobet = next((b.get('bet_bb') for b in bets
                        if b.get('seat') == 'hero' and isinstance(b.get('bet_bb'), (int, float))), 0.0)
        derived = max(0.0, round(maxbet - herobet, 2))
        new = dict(table_state)
        new['to_call'] = dict(table_state.get('to_call') or {}, to_call_bb=derived, derived=True)
        return new

    def _never_abstain_fallback(self, table_state, hero_cards, prev):
        """Ação pela TEORIA MAIS PRÓXIMA p/ um abstém de cobertura. Sempre devolve uma
        decisão (nunca None). Flagga o gap p/ cobertura real posterior."""
        positions = table_state.get('positions') or {}
        hero_pos = positions.get('hero')
        hero = table_state.get('seats', {}).get('hero', {})
        stack = hero.get('stack_bb')
        to_call = (table_state.get('to_call') or {}).get('to_call_bb') or 0.0
        bets = [b.get('bet_bb') for b in (table_state.get('bets') or [])
                if isinstance(b.get('bet_bb'), (int, float))]
        facing = any(b and b > 1.5 for b in bets) or (isinstance(to_call, (int, float)) and to_call > 1.0)
        tier = _hand_tier(hero_cards)
        short = isinstance(stack, (int, float)) and stack <= SHOVE_ZONE_MAX_BB
        allin = bool(prev.get('allin') or (facing and any(b and b >= (stack or 1e9) - 1e-6 for b in bets)))
        if facing:
            if tier == 'premium':
                rec = 'all_in' if (short or allin) else 'call'
            elif tier == 'strong' and not short and isinstance(to_call, (int, float)) and to_call <= 3.0:
                rec = 'call'
            else:
                rec = 'fold'
        else:                                        # sem aposta p/ pagar (first-in-ish)
            if tier in ('premium', 'strong'):
                rec = 'all_in' if short else 'raise'
            elif tier == 'playable' and not short:
                rec = 'raise'
            elif hero_pos == 'BB':
                rec = 'check'                        # BB de graça -> check, nunca fold
            else:
                rec = 'fold'
        reason = prev.get('reason') or 'UNKNOWN'
        out = dict(status='ADVICE', recommended=rec, validated=False,
                   execution_allowed=False, exploratory=True,
                   mix=[{'action': rec, 'frequency': 1.0}],
                   spot=prev.get('spot'),
                   caveats=['GAP_COBERTURA_APROX', 'GAP_APROX_%s' % reason,
                            'NEAREST_THEORY_HAND_TIER_%s' % tier.upper(),
                            'APONTAR_PARA_SOLVER'],
                   gap_flag=dict(reason=reason, spot=prev.get('spot'),
                                 hero_pos=hero_pos, stack_bb=stack, tier=tier, facing=facing))
        if rec == 'all_in' and isinstance(stack, (int, float)):
            out['sizing'] = dict(size_bb=round(stack, 1), basis='nearest-theory shove', heuristic=True)
        _log_gap(out['gap_flag'])
        return out

    def _advise_from_reading_core(self, table_state, hero_cards, **kwargs):
        """Núcleo (antigo advise_from_reading). Pode devolver ABSTAIN; o wrapper
        público converte abstém de cobertura em ação."""
        positions = table_state.get('positions') or {}
        hero = table_state.get('seats', {}).get('hero', {})
        if 'hero' not in positions:
            return self._abstain('HERO_POSITION_UNKNOWN')
        # ÁRVORE DE REFERÊNCIA (Clone 0.5): consulta ANTES do roteamento normal, pelo
        # MESMO classificador único (strategy.scenarios). Fonte de ESTUDO/sombra
        # (validated=False/execution_allowed=False) p/ spots deep/multiway que o pack
        # não cobre. Se casar uma árvore, devolve o conselho dela; senão -> None e o
        # fluxo normal segue INALTERADO. Só aparece ao vivo o nó NÃO-study-only.
        tree_adv = self._tree_from_reading(table_state, hero_cards, positions, hero, kwargs)
        if tree_adv is not None:
            return tree_adv
        # `bounty_bb` (PKO) só serve ao call-off; tira do kwargs p/ não vazar nos nós
        # de range (self.advise não o aceita).
        bounty_bb = kwargs.pop('bounty_bb', None)
        spot = infer_live_spot(table_state)
        base = dict(hero_cards=hero_cards, hero_position=positions['hero'], stack_bb=hero.get('stack_bb'))
        # For ICM/PKO-ICM, classify the table's stack spread from the read stacks
        # instead of always assuming equal stacks; keep the default when unset or
        # too few stacks read (infer_spread returns None).
        if kwargs.get('mode') in ('icm', 'pko_icm') and kwargs.get('spread') is None:
            seats = table_state.get('seats', {})
            spread = infer_spread({pos: seats.get(seat, {}).get('stack_bb')
                                   for seat, pos in positions.items()})
            if spread is not None:
                kwargs['spread'] = spread
        # SHOVE ZONE vs OPEN = 3BET-JAM (resteal/squeeze). Short stack enfrentando um
        # open: a linha é 3bet ALL-IN pela range validada `3bet_shove`, NÃO o 3bet/call
        # de stack fundo (que não tem nó curto -> abstinha, e com caller virava range HU
        # larga não-validada). Regra do Eduardo: short + open (+caller = squeeze) = 3bet
        # all-in. Tenta o nó de JAM ANTES; só casa com nó validado (buckets 12-25), senão
        # cai no fluxo vs_open normal (sub-12bb / fundo).
        # vs_open SEM caller: jam no shove zone (<20bb); 20bb+ usa o vs_open MISTO.
        # SQUEEZE (com caller): não há nó multiway validado, então o 3bet-JAM validado
        # vale em TODO o alcance do nó 3bet_shove (12-25bb), não só <20.
        _stk = hero.get('stack_bb')
        _in_jam_zone = isinstance(_stk, (int, float)) and (
            _stk < SHOVE_ZONE_MAX_BB or (spot.get('callers') and _stk <= 25))
        _short_vs_open = spot['spot'] == 'vs_open' and spot.get('opener') and _in_jam_zone
        _jam = (self.advise(spot='3bet_shove', vs=(spot['opener'],), **base, **kwargs)
                if _short_vs_open else None)
        # Abaixo do menor bucket de 3bet_shove (12bb) não há nó. A range de JAM só
        # ALARGA com stack menor, então usar a range de 12bb num stack <12bb é
        # ESTRITAMENTE SEGURO (jama mais TIGHT que o ótimo, nunca jama demais). Dá
        # decisão validada em vez de abster. Flag honesto marca a aproximação.
        if (_short_vs_open and isinstance(_stk, (int, float)) and _stk < 12
                and not (isinstance(_jam, dict) and _jam.get('status') == 'ADVICE')):
            base12 = dict(base, stack_bb=12)
            _j12 = self.advise(spot='3bet_shove', vs=(spot['opener'],), **base12, **kwargs)
            if isinstance(_j12, dict) and _j12.get('status') == 'ADVICE':
                _j12.setdefault('caveats', []).append('JAM_CURTO_SUB12BB_RANGE12BB_TIGHTER_SAFE')
                _jam = _j12
        if isinstance(_jam, dict) and _jam.get('status') == 'ADVICE':
            if spot.get('callers'):
                _jam.setdefault('caveats', []).append('SQUEEZE_VIA_3BET_SHOVE_%dC' % spot['callers'])
            _jam.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
            result = _jam
        elif spot['spot'] in ('vs_open', 'vs_3bet', 'vs_open_shove'):
            result = self.advise(spot=spot['spot'], vs=(spot['opener'],), **base, **kwargs)
            # Faltou o nó validado da decisão vs shove -> sintetiza o call-off por
            # equity vs o range Nash do vilão. vs_3bet: abri e levei re-shove num
            # stack curto (só há nó em 25bb); em 12-20bb um 3bet é efetivamente
            # shove. vs_open_shove: enfrento open-shove mais fundo que 15bb (sem nó).
            # O call-off (equity até o showdown) só vale para all-in COMPROVADO:
            # vs_open_shove já é um jam por construção; vs_3bet só se `allin`.
            # vs_3bet CURTO (<20bb): um 3bet nesse stack é efetivamente COMMIT -> a
            # continuação é 4bet-JAM, então sintetiza o call-off por equity mesmo sem
            # allin explícito (não há nó vs_3bet <20bb). Regra: short + 3bet = jam/fold.
            # Zona de COMMIT vs 3bet: até ~25bb um 3bet é efetivamente all-in -> a
            # continuação é 4bet-JAM/call-off. Inclusivo no limite (20bb EXATO caía na
            # fresta: `< 20` é falso) e cobre 20-25 (o nó validado vs_3bet só existe a
            # 25bb; em pko/icm sem esse nó o bot ABSTINHA = morria). Lei de cobertura.
            _vs3b_short = (spot['spot'] == 'vs_3bet'
                           and isinstance(_stk, (int, float)) and _stk <= VS3BET_JAM_MAX_BB)
            if (isinstance(result, dict) and result.get('status') == 'ABSTAIN'
                    and result.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'
                    and (spot['spot'] == 'vs_open_shove'
                         or (spot['spot'] == 'vs_3bet' and (spot.get('allin') or _vs3b_short)))):
                shove_spot, villain_vs = (('3bet_shove', (positions['hero'],))
                                          if spot['spot'] == 'vs_3bet' else ('open_shove', ()))
                # PKO: escala o bounty base pelo bounty do vilão (alvo acumulado = caça
                # mais larga). bounties vêm da leitura por assento anexada em advise_table.
                bb_eff, bcav = scale_bounty_bb(bounty_bb, table_state.get('bounties'),
                                               spot['opener'], positions)
                # Exploit do HUD: stats do SHOVER (de state['hud'], via advise_table).
                hud = table_state.get('hud') or {}
                vseat = next((s for s, p in positions.items() if p == spot['opener']), None)
                _vh = hud.get(vseat) if (hud and vseat) else None
                # Só exploita com leitura CONFIÁVEL (confidence 'high').
                vstats = _vh['stats'] if (_vh and _vh.get('confidence') == 'high') else None
                co = self.advise_call_off(
                    hero_cards=hero_cards, hero_position=positions['hero'],
                    villain_position=spot['opener'], stack_bb=hero.get('stack_bb'),
                    to_call_bb=(table_state.get('to_call') or {}).get('to_call_bb'),
                    pot_bb=(table_state.get('pot') or {}).get('pot_bb'),
                    mode=kwargs.get('mode', 'chip_ev'), stage=kwargs.get('stage', 'mid'),
                    shove_spot=shove_spot, villain_vs=villain_vs, bounty_bb=bb_eff,
                    villain_stats=vstats,
                    villain_stack_bb=((table_state.get('seats') or {}).get(vseat) or {}).get('stack_bb'),
                    table_stacks=[(s or {}).get('stack_bb')
                                  for s in (table_state.get('seats') or {}).values()
                                  if isinstance((s or {}).get('stack_bb'), (int, float))
                                  and (s or {}).get('stack_bb') > 0])
                if isinstance(co, dict):
                    if bcav:
                        co.setdefault('caveats', []).append(bcav)
                    co.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
                    return co
            if isinstance(result, dict):
                result.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
                if spot.get('callers'):
                    # vs_open is heads-up vs the opener; with callers the pot is
                    # multiway and the pack has NO multiway node, so a HU range aqui é
                    # LARGA demais (leak executável). A4/A5: marca como NÃO-validado +
                    # multiway_approx -> o operador NÃO auto-executa a range HU (vira
                    # estudo/seguro; premium segue protegido pela blindagem). Direção
                    # correta multiway = mais apertado. Sem inventar range multiway.
                    result.setdefault('caveats', []).append('MULTIWAY_%d_CALLERS_APPROX_VS_OPEN' % spot['callers'])
                    if result.get('status') == 'ADVICE':
                        # Squeeze multiway deep (sem nó próprio): a range HU é larga demais
                        # p/ blefar, MAS o VALOR PURO (raise com freq ~1.0) squeeze com
                        # segurança. Mantém só o valor puro como validado; mistos/blefes
                        # viram piso seguro (não auto-executa). Assim premium NUNCA larga
                        # (sem fold de AA no squeeze) e não se blefa-squeeze multiway.
                        _rec = result.get('recommended')
                        _freq = 0.0
                        for _it in (result.get('mix') or []):
                            if isinstance(_it, dict) and _it.get('action') == _rec:
                                _freq = float(_it.get('frequency') or 0.0)
                                break
                        _aggr = _rec in ('three_bet', 'raise', 'all_in', 'bet', 'four_bet')
                        if _aggr and _freq >= 0.9:
                            result.setdefault('caveats', []).append('SQUEEZE_VALOR_PURO')
                        else:
                            result['validated'] = False
                            result['multiway_approx'] = True
        elif spot['spot'] == 'first_in':
            import sizing
            # O nó vs_limp do pack é BB vs limp do SB (batalha de blinds). Só roteia
            # nesse caso HU: hero no BB, SB completou (~1bb) e NENHUM limper fora do
            # blind. Limps de outras posições não têm nó validado -> first_in (iso
            # aproximado), e não o nó SB×BB errado.
            # BB enfrentando limp. DEEP: só o SB-limp HU puro usa o nó vs_limp (como
            # antes — limp de outra posição deep segue first_in/iso). ZONA DE SHOVE
            # (<20bb): QUALQUER limp (SB ou outra posição) usa a range vs_limp (nó BB-vs-
            # limp, vs=(), independe de quem limpou) — senão caía em open_shove|BB
            # (inexistente, o BB nunca "abre") e ABSTINHA. Eduardo 19/11: cobrir o
            # CONTEXTO da zona de shove (qualquer mão/limp no BB tem decisão).
            _sb_hu_limp = _sb_limped(table_state) and sizing.count_limpers(table_state) == 0
            _short = isinstance(base.get('stack_bb'), (int, float)) and base['stack_bb'] < SHOVE_ZONE_MAX_BB
            _short_any_limp = _short and (_sb_limped(table_state) or sizing.count_limpers(table_state) >= 1)
            if base['hero_position'] == 'BB' and (_sb_hu_limp or _short_any_limp):
                result = self.advise(spot='vs_limp', vs=(), **base, **kwargs)
                _rr = result if isinstance(result, dict) else {}
                # vs_limp só tem nó em 25bb. A batalha BB vs limp do SB é estável o
                # suficiente p/ usar a range de 25bb em QUALQUER stack (aproximacao
                # rotulada) sempre que o stack real não deu decisao validada (abstém OU
                # borra não-validado) -> sempre uma decisao (iso/check/fold), nunca buraco.
                if _rr.get('status') != 'ADVICE' or _rr.get('validated') is not True:
                    r25 = self.advise(spot='vs_limp', vs=(), **dict(base, stack_bb=25), **kwargs)
                    if isinstance(r25, dict) and r25.get('status') in ('ADVICE', 'OUT_OF_RANGE'):
                        r25.setdefault('caveats', []).append('VS_LIMP_RANGE25BB_APROX')
                        result = r25
                    elif _rr.get('status') != 'ABSTAIN':
                        pass                              # mantém o borrow (já é uma decisao)
                    else:
                        result = self.advise_first_in(**base, **kwargs)
                elif isinstance(result, dict):
                    result.setdefault('caveats', []).append('VS_LIMP_SB_BLIND_BATTLE')
            else:
                result = self.advise_first_in(**base, **kwargs)
        elif spot['spot'] == 'threebet_cold':
            # Enfrenta open + 3bet COLD, sem nó validado. ZONA DE SHOVE = jam/fold
            # TIGHT-SAFE (QQ+/AK): se o 3bet é all-in -> CALL-off (premium paga); senão
            # 4bet-JAM; resto FOLD. Decisão conservadora de ICM, nunca abstém no short
            # (Eduardo 19/11: cobrir o contexto). DEEP sem nó -> segue abstendo.
            if isinstance(_stk, (int, float)) and _stk < SHOVE_ZONE_MAX_BB:
                try:
                    hand = hand_key(hero_cards)
                except Blocked as exc:
                    return self._abstain(str(exc))
                _jam = hand in {'AA', 'KK', 'QQ', 'AKs', 'AKo'}
                if _jam and spot.get('allin'):
                    rec, flags = 'call', dict(safety_premium=True)      # call-off vs shove
                elif _jam:
                    rec, flags = 'all_in', dict(safety_premium_shove=True)  # 4bet-jam
                else:
                    rec, flags = 'fold', {}
                result = dict(status='ADVICE', recommended=rec, validated=False,
                              spot='threebet_cold', hero_position=base['hero_position'],
                              hand=hand, hero_cards=list(hero_cards), stack_bb=base.get('stack_bb'),
                              caveats=['COLD_3BET_PUSHFOLD_TIGHT_SAFE'], **flags)
            else:
                return self._abstain(spot.get('reason', 'MULTIWAY_OR_3BET_NOT_COVERED'))
        else:
            return self._abstain(spot.get('reason', 'SPOT_NOT_COVERED'))
        # ÚLTIMO RECURSO — CAMADA NASH SOMBRA: o fluxo normal ABSTEVE num spot de ZONA
        # DE SHOVE (tipicamente spread enviesado curtos_ini/curtos_fim ou PKO curto sem
        # nó). Re-tenta o spot de PUSH/FOLD correspondente com a sombra Nash LIGADA
        # (reusa a tabela Nash de um contexto vizinho — mesmo modo/stage spread 'iguais',
        # senão chip-EV — marcada validated=False). Só substitui uma ABSTENÇÃO, então
        # NUNCA rebaixa um nó validado/decisão melhor. Conselho/sombra até homologar.
        if (isinstance(result, dict) and result.get('status') == 'ABSTAIN'
                and isinstance(_stk, (int, float)) and _stk < SHOVE_ZONE_MAX_BB):
            # ZONA DE SHOVE = regime PUSH/FOLD: NUNCA abster (Eduardo 19/11, contexto do
            # range inteiro). Enfrenta um raise -> 3bet-shove (resteal/squeeze); senão
            # (first-in OU pote só limpado) -> open-shove. A Nash-sombra cobre o CONTEXTO
            # (empresta bucket vizinho), então vale p/ QUALQUER mão naquele spot.
            _opener = spot.get('opener')
            if _opener:
                _b = dict(base, stack_bb=max(_stk, 12))   # 3bet_shove mora em 12-25bb
                _sh = self.advise(spot='3bet_shove', vs=(_opener,), **_b, **kwargs,
                                  _nash_shadow_ok=True)
                if isinstance(_sh, dict) and _sh.get('status') == 'ADVICE':
                    if spot.get('callers'):
                        _sh.setdefault('caveats', []).append('SQUEEZE_VIA_3BET_SHOVE_%dC' % spot['callers'])
                    _sh.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % _opener)
                    if _stk < 12:
                        _sh.setdefault('caveats', []).append('JAM_CURTO_SUB12BB_RANGE12BB_TIGHTER_SAFE')
            else:
                _sh = self.advise(spot='open_shove', vs=(), **base, **kwargs, _nash_shadow_ok=True)
                if isinstance(_sh, dict) and _sh.get('status') == 'ADVICE' and spot.get('limpers'):
                    _sh.setdefault('caveats', []).append('SHOVE_OVER_LIMPERS')
            if isinstance(_sh, dict) and _sh.get('status') == 'ADVICE':
                result = _sh
        if isinstance(result, dict) and result.get('status') in ('ADVICE', 'OUT_OF_RANGE'):
            import sizing
            # The pack is 9-max only; a shorter table uses it as a reference. Flag it
            # honestly instead of abstaining (we have no 6-max ranges, and short
            # tables are most of ITM/short-handed play). Likewise a limper makes a
            # first-in open an isolation approximation (no vs_limp range off the SB).
            occupied = sum(1 for s in (table_state.get('seats') or {}).values() if s.get('occupied'))
            if occupied and occupied != 9:
                result.setdefault('caveats', []).append('TABLE_%dHANDED_USING_9MAX_REF' % occupied)
            if spot['spot'] == 'first_in' and sizing.count_limpers(table_state) > 0:
                result.setdefault('caveats', []).append('LIMPERS_PRESENT_OPEN_AS_ISO_APPROX')
                # CAP DO ISO: com limper, NÃO abrir a range larga de blind-battle (SB
                # 91%). Só iso VALOR (mão que abriria de UTG); senão FOLD. Mata o
                # iso de lixo (ex.: 85o SB com BTN limpando).
                if (result.get('recommended') == 'raise'
                        and not self._iso_worthy(result.get('hand'), result.get('stack_bucket'),
                                                 mode=kwargs.get('mode', 'chip_ev'),
                                                 stage=kwargs.get('stage', 'mid'),
                                                 players=kwargs.get('players', 9),
                                                 position=base.get('hero_position', 'UTG'))):
                    result['recommended'] = 'fold'
                    result['status'] = 'ADVICE'
                    result.setdefault('caveats', []).append('ISO_CAP_FOLD_FORA_DO_RANGE_TIGHT')
            # EXPLOIT PRÉ-FLOP (delta por cima do GTO, bounded): usa o perfil do OPENER
            # (HUD/DB, só com leitura CONFIÁVEL). ANTES do sizing -> o 3bet-blefe sai com
            # size. Só vs_open por ora (o opener é o vilão inequívoco); steal (perfil dos
            # blinds) fica p/ a próxima leva.
            _hud = table_state.get('hud') or {}

            def _stats_of(_pos):
                _s = next((ss for ss, pp in positions.items() if pp == _pos), None)
                _h = _hud.get(_s) if _s else None
                return _h['stats'] if (_h and _h.get('confidence') == 'high') else None
            if result.get('status') == 'ADVICE' and spot['spot'] == 'vs_open':
                _vstats = _stats_of(spot.get('opener'))
                if _vstats:
                    result = preflop_exploit.exploit_preflop(result, _vstats, spot='vs_open')
            elif (result.get('status') == 'ADVICE' and spot['spot'] in ('first_in', 'open_raise')
                  and positions.get('hero') in preflop_exploit.LATE):
                # STEAL: perfil dos BLINDS que defendem (SB/BB), só os com leitura confiável.
                _defs = [s for s in (_stats_of('SB'), _stats_of('BB')) if s]
                if _defs:
                    result = preflop_exploit.exploit_preflop(
                        result, None, spot='first_in', defenders=_defs,
                        hero_position=positions.get('hero'))
            if result.get('recommended'):
                result['sizing'] = sizing.size_from_reading(result['recommended'], table_state,
                                                            positions['hero'], spot.get('opener'),
                                                            stage=kwargs.get('stage'))
        return result

    def _shove_range_node(self, spot, shover, vs_tuple, bucket):
        """Nó de range de shove do vilão (`3bet_shove` ou `open_shove`) p/ o shover,
        com o `vs` casando (vazio no open_shove). O shover costuma estar curto, então
        usa o bucket solved MAIS PRÓXIMO do pedido (o range de shove muda pouco entre
        stacks vizinhos); prefere chip_ev/regular/mid (Nash). None se não há nenhum."""
        vs_tuple = tuple(vs_tuple or ())
        ck = (spot, shover, vs_tuple, bucket)
        if ck in self._shove_cache:
            return self._shove_cache[ck]
        best = None
        for n in self.nodes:
            if n['spot'] != spot or n['hero'] != shover:
                continue
            if tuple(n.get('vs') or ()) != vs_tuple:
                continue
            c = n['context']
            # ordena: stack mais próximo primeiro, depois chip_ev/regular/mid
            score = (-abs(c['stack'] - bucket), c['mode'] == 'chip_ev',
                     c['format'] == 'regular', c['stage'] == 'mid')
            if best is None or score > best[0]:
                best = (score, n)
        node = best[1] if best else None
        self._shove_cache[ck] = node
        return node

    def advise_call_off(self, *, hero_cards, hero_position, villain_position, stack_bb,
                        to_call_bb, pot_bb, mode='chip_ev', stage='mid', shove_spot='3bet_shove',
                        villain_vs=None, bounty_bb=None, villain_stats=None,
                        villain_stack_bb=None, table_stacks=None, iters=6000, seed=0):
        """Call-off SINTETIZADO por equity quando falta o nó validado da decisão.

        Pago se a equity da minha mão contra o range de shove (Nash) do vilão >=
        pot odds + risk premium (ICM) - overlay de bounty (PKO). `shove_spot`=
        '3bet_shove' (vilão re-shova meu open; range vs=meu assento) ou 'open_shove'
        (vilão deu open-shove; range vs=()). O RP vem de `_icm_risk_premium` (0 em chip
        EV; aproximação por fase em ICM).

        `bounty_bb` (opcional, PKO): valor do bounty em BB que o hero LEVA se ELIMINAR o
        vilão. Só é aplicado em modo pko/pko_icm E quando o hero COBRE o shove (stack >=
        a quantia a pagar, então vencer elimina). Conta como POTE EXTRA -> exige menos
        equity -> caça de bounty com range mais largo; quanto menor o shove, maior o
        peso do bounty (o "proporcional ao stack"). O valor NÃO é lido da mesa (entrada).

        Decisão call/fold (clique único). Não autoriza execução (gate externo). Abstém
        quando falta o range do vilão ou os dados de pot odds."""
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return self._abstain(why, stack_bb=stack_bb)
        try:
            hand = hand_key(hero_cards)
        except Blocked as exc:
            return self._abstain(str(exc))
        vs_tuple = (hero_position,) if villain_vs is None else tuple(villain_vs)
        node = self._shove_range_node(shove_spot, villain_position, vs_tuple, bucket)
        if node is None:
            return self._abstain('NO_SHOVE_RANGE_FOR_CONTEXT',
                                 context=dict(shove_spot=shove_spot, shover=villain_position,
                                              vs=vs_tuple, stack=bucket))
        req = required_equity(to_call_bb, pot_bb)
        if req is None:
            return self._abstain('CANNOT_COMPUTE_POT_ODDS', to_call_bb=to_call_bb, pot_bb=pot_bb)
        # Overlay de bounty (PKO): se o hero COBRE o shove (stack >= a quantia a pagar),
        # vencer ELIMINA o vilão e leva o bounty -> conta como POTE EXTRA -> exige menos
        # equity. `req` fica a pot odds crua (relatada); `req_eff` é a exigência efetiva.
        bounty = 0.0
        req_eff = req
        if (mode in ('pko', 'pko_icm') and isinstance(bounty_bb, (int, float)) and bounty_bb > 0
                and isinstance(stack_bb, (int, float)) and isinstance(to_call_bb, (int, float))
                and stack_bb >= to_call_bb):
            bounty = float(bounty_bb)
            req_eff = required_equity(to_call_bb, pot_bb + bounty)
        # Cache só da EQUITY bruta (determinística dado o seed), por nó+cartas+iters+
        # seed. O node_id carrega a fonte/versão do range (novo pack = novo advisor =
        # cache limpo). Pot odds, RP e elegibilidade são recalculados sempre, com os
        # valores atuais — nunca se guarda um conselho antigo.
        ekey = (node['id'], tuple(sorted(hero_cards)), iters, seed)
        if ekey in self._equity_cache:
            eq = self._equity_cache[ekey]
        else:
            combos = range_from_node(node, self.hands, actions=('all_in',))
            eq = equity_vs_range(hero_cards, combos, iters=iters, seed=seed)
            if eq is not None:
                if len(self._equity_cache) >= 4096:
                    self._equity_cache.clear()           # cap de memória simples
                self._equity_cache[ekey] = eq
        if eq is None:
            return self._abstain('EQUITY_UNAVAILABLE')
        # RP: com o stack do VILÃO conhecido, usa o modelo de RISK ADVANTAGE (quem cobre
        # tem RP menor — icm_rp, calibrado pela skill ICM); senão, o proxy antigo por fase.
        risk_adv = None
        if villain_stack_bb is not None and mode in ('icm', 'pko_icm'):
            import icm_rp
            rp = icm_rp.risk_premium(mode, stage, hero_stack=stack_bb,
                                     villain_stack=villain_stack_bb, to_call_bb=to_call_bb,
                                     table_stacks=table_stacks)
            risk_adv = icm_rp.risk_advantage(stage, stack_bb, villain_stack_bb)
        else:
            rp = _icm_risk_premium(mode, stage, to_call_bb, stack_bb)
        # Exploit do HUD: o shover loose-agressivo shova mais largo que o Nash -> paga
        # mais largo (delta −); passivo/nit shova valor -> folda mais (+). Bounded.
        profile = classify_villain(villain_stats) if villain_stats else None
        ex_delta = shove_calloff_delta(profile) if profile else 0.0
        req_icm = min(0.99, max(0.02, req_eff + rp + ex_delta))
        action = 'call' if eq >= req_icm else 'fold'
        caveats = ['EXPLORATORY_NOT_FOR_EXECUTION', 'CALLOFF_SYNTH_VS_%s' % shove_spot.upper(),
                   'VILLAIN_RANGE_NASH_%s_%sBB' % (shove_spot.upper(), node['context']['stack'])]
        if shove_spot == '3bet_shove':
            caveats.append('SHORT_STACK_3BET_TREATED_AS_SHOVE')
        if rp > 0:
            caveats.append('ICM_RP_APPROX_BY_STAGE_%s_%dPCT' % (stage, round(rp * 100)))
        if risk_adv is not None:
            caveats.append('ICM_RISK_ADV_%+dPCT_%s' % (
                round(risk_adv['advantage'] * 100),
                'HERO_COBRE_PRESSIONA' if risk_adv['advantage'] > 0 else 'HERO_COBERTO_APERTA'))
        if bounty > 0:
            caveats += ['PKO_BOUNTY_OVERLAY_%gBB' % bounty, 'BOUNTY_VALUE_IS_INPUT_NOT_READ',
                        'HERO_COVERS_SHOVE_CAN_ELIMINATE']
        if profile and profile['category'] != 'unknown':
            caveats += exploit_caveats(profile)
            if ex_delta:
                caveats.append('SHOVE_CALLOFF_DELTA_%+.2f' % ex_delta)
        return dict(status='ADVICE', spot='call_off_vs_%s' % shove_spot, hero_position=hero_position,
                    hand=hand, recommended=action, mix=[dict(action=action, frequency=1.0)],
                    equity=round(eq, 4), required_equity=round(req, 4),
                    required_equity_effective=round(req_eff, 4), bounty_bb=round(bounty, 2),
                    risk_premium=rp, risk_advantage=risk_adv, required_equity_icm=round(req_icm, 4),
                    villain_shove_node=node['id'], villain_position=villain_position,
                    stack_bb=stack_bb, stack_bucket=bucket, exploratory=True,
                    execution_allowed=False, validated=False, caveats=caveats)

    def _caveats(self, bucket, stack_bb, players, mode, spread=None):
        out = ['EXPLORATORY_NOT_FOR_EXECUTION', 'NVT_REFERENCE_SHORT_STACK_ONLY']
        if bucket != stack_bb:
            out.append('STACK_BUCKETED_%s_TO_%sBB' % (stack_bb, bucket))
        if isinstance(stack_bb, (int, float)) and stack_bb > self.STACK_BUCKETS[-1]:
            # Beyond the deepest solved stack: the top-bucket range is a reference,
            # not a solution. Report the ACTUAL top bucket so the flag never lies.
            out.append('STACK_ABOVE_SOLVED_DEPTH_%sBB_REFERENCE' % self.STACK_BUCKETS[-1])
        if players != 9:
            out.append('TABLE_IS_9MAX_REFERENCE')
        if mode != 'chip_ev':
            out.append('ICM_PKO_NEEDS_TOURNAMENT_INPUTS')
        if mode in ('icm', 'pko_icm'):
            # Report the stack spread actually used; 'iguais' may be the default
            # (equal stacks assumed) or the nearest match to the real table.
            out.append('ICM_SPREAD_%s' % (spread or 'iguais').upper())
        return out

    @staticmethod
    def _abstain(reason, **extra):
        return dict(status='ABSTAIN', reason=reason, exploratory=True, execution_allowed=False, **extra)
