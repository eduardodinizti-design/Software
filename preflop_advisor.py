"""Exploratory live preflop advisor over the NVT range reference.

Separate from preflop_study.py: that module is a strict, exact-match SIMULATION
validator; this one turns the live table reading into a usable recommendation by
consulting the validated range pack at the nearest stack bucket. It is labelled
EXPLORATORY and never authorises execution.

The NVT pack is a reference, optimised for short stacks: it covers discrete
stacks 5-25bb, 9-max, chip EV + ICM + PKO. Deep stacks (>25bb) and post-flop are
out of coverage and abstain here, to be developed into the bot's own engine.

No capture, no clicks. Stack bucketing and the 9-max table are explicit
approximations, reported in every answer.
"""
import hashlib
import json
from pathlib import Path

from preflop_study import hand_key, Blocked
from preflop_equity import range_from_node, equity_vs_range, required_equity
from hud_exploit import classify_villain, shove_calloff_delta, exploit_caveats
from strategy.scenarios import classify as classify_scenario, from_table_state

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
PUSHFOLD_MAX_BB = 12   # <= isso, first-in tenta SHOVE antes de open-raise
# ZONA DE SHOVE: abaixo disso o hero está em regime de push/fold. NÃO se pega range
# emprestada por proximidade de stack para spots de RAISE (open_raise/vs_open/
# vs_limp) — emprestar uma range de open aqui produz MINI-RAISES SUICIDAS. Só
# tabelas puras de push/fold (open_shove/vs_open_shove) valem. Além disso, o
# first-in tenta o SHOVE antes do open-raise nessa zona.
SHOVE_ZONE_MAX_BB = 20


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
    if isinstance(remaining, (int, float)):
        return remaining <= SHOVE_REMAINING_BB
    return opener_bet >= SHOVE_SIZE_FALLBACK_BB


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
        return dict(spot='abstain', opener=None, reason='MULTIWAY_OR_3BET_NOT_COVERED')
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
    # Short stacks (5-25) come from the validated NVT pack; 40/100 from the deep
    # reference pack (not HRC-validated, flagged in every answer).
    STACK_BUCKETS = (5, 8, 10, 12, 15, 20, 25, 30, 40)

    def __init__(self, pack, *, sources=None, strict=True):
        if pack.get('format') != 'nvt-range-export' or pack.get('version') != 1:
            raise Blocked('UNSUPPORTED_RANGE_FORMAT')
        self.hands = pack['hands']
        if len(self.hands) != 169:
            raise Blocked('INVALID_HAND_INDEX')
        self.nodes = list(pack['nodes'])   # includes unvalidated reference (deep) nodes
        self.engine_commit = pack.get('engineCommit')
        self.sources = list(sources or [])  # B01: origem(ns) por sha256 (ver manifest())
        self.strict = strict
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
        for node in pack['nodes']:node['_source_sha256']=hashlib.sha256(raw).hexdigest()
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
            for node in pack['nodes']:node['_source_sha256']=hashlib.sha256(raw).hexdigest()
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

        The HRC solutions top out at 100bb, but real tournaments play deeper,
        especially early. Preflop open/3bet ranges change little above 100bb, so
        a stack at or beyond the top bucket uses the 100bb range as the best
        available reference (the extrapolation is flagged in the caveats), rather
        than abstaining and leaving a common deep table without advice."""
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

    def advise(self, *, hero_cards, hero_position, stack_bb, mode='chip_ev',
               table_format=None, stage='mid', players=9, spot='open_raise', vs=(), spread=None):
        """An exploratory recommendation for one preflop spot, or an abstention.

        Returns status ADVICE | ABSTAIN | OUT_OF_RANGE with the action mix, EVs,
        the recommended (most frequent) action, and the approximations made. ICM/
        PKO nodes carry a stack spread; absent one, equal stacks ('iguais') are
        assumed and flagged."""
        bucket, why = self.bucket_stack(stack_bb)
        if bucket is None:
            return self._abstain(why, stack_bb=stack_bb)
        try:
            hand = hand_key(hero_cards)
        except Blocked as exc:
            return self._abstain(str(exc))
        spread = spread if spread is not None else ('iguais' if mode in ('icm', 'pko_icm') else None)
        if table_format is None:
            table_format = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, table_format, stage, players, bucket, spot, hero_position, tuple(vs), spread))
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
        if node is None:
            reason = 'SHOVE_ZONE_PUSHFOLD_ONLY_NO_BORROW' if blocked_borrow \
                else 'NO_VALIDATED_NODE_FOR_CONTEXT'
            return self._abstain(reason,
                                 context=dict(mode=mode, stage=stage, stack=bucket, spot=spot,
                                              hero=hero_position, players=players))
        i = self.hands.index(hand)
        raw_validated = bool(node.get('validated'))
        validated = raw_validated and borrowed_from is None   # stack emprestado não auto-executa
        caveats = self._caveats(bucket, stack_bb, players, mode, spread)
        if not raw_validated:
            caveats.append('UNVALIDATED_REFERENCE_RANGE')
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
        return result

    def _iso_worthy(self, hand, bucket, *, mode='chip_ev', stage='mid', players=9):
        """Mão vale um ISO sobre limper? O range de 'open' do SB é de BLIND BATTLE
        (~91%, certo só quando folda pro SB). Com limper NÃO é blind battle: iso tem
        que ser VALOR/apertado. Cap conservador: só iso se a mão abriria de uma posição
        TIGHT (UTG). Folda o lixo (85o/T5o) e mantém valor (ATs/99/KQ...). HEURÍSTICA
        afinável (trocar a posição/range de referência do iso). Sem referência -> não
        bloqueia."""
        tf = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
        node = self._index.get((mode, tf, stage, players, bucket, 'open_raise', 'UTG', (), None))
        if node is None or hand not in self.hands:
            return True
        i = self.hands.index(hand)
        if i in (node.get('outOfRange') or []):
            return False
        freq = node['freq'].get('raise') or []
        return i < len(freq) and freq[i] > 0

    def advise_from_reading(self, table_state, hero_cards, **kwargs):
        """Pull hero's position/stack from a read_table_state result, infer the
        spot from the bets (first_in or vs_open), advise, and attach a founded
        raise size for the recommended action. The spot inference is approximate
        (it rides on the nearest-seat bet attribution)."""
        positions = table_state.get('positions') or {}
        hero = table_state.get('seats', {}).get('hero', {})
        if 'hero' not in positions:
            return self._abstain('HERO_POSITION_UNKNOWN')
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
        if spot['spot'] in ('vs_open', 'vs_3bet', 'vs_open_shove'):
            result = self.advise(spot=spot['spot'], vs=(spot['opener'],), **base, **kwargs)
            # Faltou o nó validado da decisão vs shove -> sintetiza o call-off por
            # equity vs o range Nash do vilão. vs_3bet: abri e levei re-shove num
            # stack curto (só há nó em 25bb); em 12-20bb um 3bet é efetivamente
            # shove. vs_open_shove: enfrento open-shove mais fundo que 15bb (sem nó).
            # O call-off (equity até o showdown) só vale para all-in COMPROVADO:
            # vs_open_shove já é um jam por construção; vs_3bet só se `allin`.
            if (isinstance(result, dict) and result.get('status') == 'ABSTAIN'
                    and result.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'
                    and (spot['spot'] == 'vs_open_shove'
                         or (spot['spot'] == 'vs_3bet' and spot.get('allin')))):
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
                    villain_stats=vstats)
                if isinstance(co, dict):
                    if bcav:
                        co.setdefault('caveats', []).append(bcav)
                    co.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
                    return co
            if isinstance(result, dict):
                result.setdefault('caveats', []).append('AGGRESSOR_INFERRED_%s' % spot['opener'])
                if spot.get('callers'):
                    # vs_open is heads-up vs the opener; with callers the pot is
                    # multiway and the pack has no multiway node, so this is an
                    # approximation (usually tighter in reality), flagged as such.
                    result.setdefault('caveats', []).append('MULTIWAY_%d_CALLERS_APPROX_VS_OPEN' % spot['callers'])
        elif spot['spot'] == 'first_in':
            import sizing
            # O nó vs_limp do pack é BB vs limp do SB (batalha de blinds). Só roteia
            # nesse caso HU: hero no BB, SB completou (~1bb) e NENHUM limper fora do
            # blind. Limps de outras posições não têm nó validado -> first_in (iso
            # aproximado), e não o nó SB×BB errado.
            if (base['hero_position'] == 'BB' and _sb_limped(table_state)
                    and sizing.count_limpers(table_state) == 0):
                result = self.advise(spot='vs_limp', vs=(), **base, **kwargs)
                if (isinstance(result, dict) and result.get('status') == 'ABSTAIN'
                        and result.get('reason') == 'NO_VALIDATED_NODE_FOR_CONTEXT'):
                    result = self.advise_first_in(**base, **kwargs)
                elif isinstance(result, dict):
                    result.setdefault('caveats', []).append('VS_LIMP_SB_BLIND_BATTLE')
            else:
                result = self.advise_first_in(**base, **kwargs)
        else:
            return self._abstain(spot.get('reason', 'SPOT_NOT_COVERED'))
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
                                                 players=kwargs.get('players', 9))):
                    result['recommended'] = 'fold'
                    result['status'] = 'ADVICE'
                    result.setdefault('caveats', []).append('ISO_CAP_FOLD_FORA_DO_RANGE_TIGHT')
            if result.get('recommended'):
                result['sizing'] = sizing.size_from_reading(result['recommended'], table_state,
                                                            positions['hero'], spot.get('opener'))
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
                        villain_vs=None, bounty_bb=None, villain_stats=None, iters=6000, seed=0):
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
                    risk_premium=rp, required_equity_icm=round(req_icm, 4),
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
