# -*- coding: utf-8 -*-
"""Scorecard: advise_postflop  x  corpus do guia pos-flop do Eduardo (1826 ex).

Mede a taxa de concordancia entre o `advise_postflop` (postflop_advisor.py) e a
acao ENSINADA no guia, por categoria, para quantificar a PASSIVIDADE do advisor
e servir de regua ANTES/DEPOIS dos fixes de agressao. Roda offline, nao executa
nada, nao arma: so le o corpus e chama o advisor.

Uso (da raiz do repo, SEM -I pois precisa do cwd no sys.path):
    python scorecard_guia_posflop.py

===========================================================================
SCHEMA REAL DO CORPUS (fixtures/guia_posflop_fixtures.json) -- lista de 1826 dicts
===========================================================================
Cada exemplo:
    section    : familia do spot. 12 valores:
                 cbet_ip, cbet_oop, cbet_vs_sb, bluff_catch, float, triple_barrel,
                 multiway, probe, delayed_cbet, bet_check_bet, squeeze, blind_war
    scenario   : texto da situacao. 13 valores. Ou "Situacao: ..." (explicito,
                 ~1329 ex) ou "SOLVER 40bb ..." (dump de solver, ~497 ex).
    stack_bb   : 40 em 1786 ex; 2 em 40 ex -- o '2' e LIXO de parsing do "abre 2bb"
                 (o scenario desses diz "stack 25bb"). => derivo stack do TEXTO.
    street     : FLOP (1044) / TURN (399) / RIVER (383)
    board      : lista de cartas (3=flop, 4=turn, 5=river), ex ["As","Qd","Jc"]
    hand       : 2 cartas do heroi, ex ["9c","8c"]
    hand_class : rotulo textual da forca (muitas vezes None). NAO uso: a forca da
                 mao (made/draws/outs) vem do PROPRIO advisor (hand_strength).
    action     : acao ENSINADA. 9 valores: bet, check, call, check_call, check_fold,
                 fold, raise, check_raise, all_in. (o alvo que comparo)
    size_pct   : tamanho da aposta % do pote (quando bet), senao None. NAO afeta a
                 familia de acao; so o advisor sugere size proprio.
    note       : explicacao em PT (usada so para contexto no relatorio).

O corpus NAO tras pot/to_call/posicoes/agressor diretos -> reconstruo o ESTADO do
spot a partir de (section, scenario, street). Abaixo, o mapeamento e as suposicoes.

===========================================================================
COMO MAPEIO CADA FIXTURE -> argumentos de advise_postflop
===========================================================================
advise_postflop(table_state, hero, board, street, aggressor, pot_type, villains, ...)
table_state usado pelo advisor:
    table_state['pot']['pot_bb']            -> pote (JA inclui a aposta do vilao)
    table_state['to_call']['to_call_bb']    -> quanto falta pagar (0 = passaram a vez)
    table_state['seats']['hero']['stack_bb']-> stack do heroi (proxy de SPR)
    table_state['positions']                -> {'hero': POS, 'v1': POS} (IP/OOP e vs SB)
    count_opponents(table_state)            -> nro de oponentes (conto pelos seats)

hero=fixture['hand'], board=fixture['board'], street=fixture['street'].

-- POSICAO / AGRESSOR / FACING (quem enfrenta aposta) por spot --
O TEXTO "voce BTN" dos scenarios e um template generico e as vezes conflita com a
secao; a SECTION e autoritativa para posicao. Spots (S#) dos scenarios "Situacao:":

 S1  "...voce BTN...BB da check" FLOP (leader, to_call=0, agressor=heroi):
       cbet_ip    -> heroi PFR IP     (hero=BTN, vilao=BB)        [vs-BB: c-bet range]
       cbet_oop   -> heroi PFR OOP    (hero=CO,  vilao=BTN)       [dispara gate c-bet OOP]
       cbet_vs_sb -> heroi PFR IP vs SB cold-caller (hero=BTN, vilao=SB) [dispara vs-SB]
       bluff_catch-> heroi IP decide check-back/bet (hero=BTN, vilao=BB)
 S8  igual a S1 porem 25bb (cbet_ip), stack=25.
 S2  "...voce BB...BTN c-beta 55%" FLOP (FACING, agressor=vilao, hero OOP=BB):
       bet 55% do pote. [float, triple_barrel]
 S2b "...voce BB...BTN c-beta 35%" FLOP (FACING): bet 35%. [float]
 S9  "...c-betou 35%...BB da check-raise 4x" FLOP (FACING um check-raise de 4x). [bluff_catch]
 S3  "Voce BTN c-betou 55% e BB pagou -> turn, BB check" TURN (leader, agressor=heroi):
       barril de turn. [triple_barrel, bet_check_bet]
 S4  "Voce BTN c-betou 35% e BB pagou -> turn, BB check" TURN/RIVER (leader, agressor=heroi):
       bet_check_bet: no TURN o heroi CHECA (villain_line=None); no RIVER ele ja checou
       o turn -> villain_line='checked_turn' (dispara valor fino de river). [bet_check_bet, triple_barrel]
 S5  "Voce BTN pagou o donk -> BB da check no turn" TURN (leader IP, to_call=0):
       heroi floatou um donk e lidera o turn. agressor=None (o BB mostrou a agressao no flop). [float]
 S6  "Flop check-check -> voce BB fala no turn" TURN (leader OOP, to_call=0):
       PROBE. agressor=None, villain_line='checked_back'. [probe, multiway]
 S7  "Voce BTN deu check no flop -> BB da check no turn" TURN (leader IP, to_call=0):
       DELAYED c-bet. agressor=heroi, villain_line='delayed'. [delayed_cbet, probe]

Scenarios "SOLVER ..." (section e autoritativa):
   bluff_catch   -> FACING (defende um barril), agressor=vilao. "a arvore nao tem raise".
   triple_barrel -> FACING (defende o barril TURN/RIVER), agressor=vilao.  (<- difere do
                    triple_barrel de "Situacao:", onde o heroi BARRELA)
   float         -> FACING um donk em posicao (hero=BTN IP, vilao=BB donk). agressor=vilao.
   probe         -> leader turn (villain_line='checked_back').
   squeeze       -> pote de 3BET (pot_type='three_bet', SPR~1.2 pelo guia). facing/lead
                    decidido pela ACAO (call/fold/check_fold = facing; bet/all_in/check = lead).
   blind_war     -> SB vs BB. hero=BB (IP pos-flop), vilao=SB. facing/lead pela ACAO.
   multiway      -> pot_type='multiway', villains=2. facing/lead pela ACAO.

-- SUPOSICOES (escolhidas pelo mapeamento MAIS FIEL; documentadas) --
A1 stack: 40bb (ou 25 quando o texto diz 25bb); o campo stack_bb=2 e lixo, ignorado.
A2 Potes por rua (single-raised 40bb): flop S=5.5bb, turn S=11bb, river S=24bb (open
   2.5, c-bet ~50%). So o leader usa S como pote; o facing usa pote=S+apostavilao.
   Como as pot odds dependem so da FRACAO da aposta (invariante de escala) e o SPR so
   mexe em sizing/3bet-commit, o valor absoluto do pote quase nao muda a FAMILIA.
A3 Sem villain_range (baseline honesto = o que roda ao vivo sem HUD/range). O caminho
   sem-range do advisor e justamente onde a passividade aparece (marginal/ar foldam por
   default) -> e o que queremos medir. Passar ranges fica para um 2o run futuro.
A4 Secao manda na posicao quando conflita com o texto do scenario (cbet_oop=OOP,
   cbet_vs_sb=vilao SB).
A5 Fracao da aposta enfrentada por spot: S2=55%, S2b=35%, SOLVER bluff_catch=60%,
   SOLVER triple_barrel=66%, SOLVER float(donk)=40%, blind_war=40%, multiway=50%,
   squeeze(3bet, SPR baixo)=100%. S9 = check-raise 4x do c-bet de 35%.
A6 pot_type: squeeze->three_bet; multiway->multiway; senao single_raised.

===========================================================================
NORMALIZACAO E COMPARACAO
===========================================================================
Acao do guia e `recommended` do advisor viram FAMILIA (6): BET, RAISE, CHECK, CALL,
FOLD, ALL_IN -- vocabulario alinhado a suprema_act._rec_family (bet/raise->agressao,
etc). As acoes COMPOSTAS do guia (check_call/check_fold/check_raise) sao decididas no
NO do spot:
  - no LEADER (to_call=0) a acao imediata do heroi e o CHECK -> familia CHECK (o
    advisor ali so pode BET ou CHECK). bet->BET, all_in->ALL_IN(jam de lead).
  - no FACING (to_call>0) a reacao e a 2a parte: check_call->CALL, check_fold->FOLD,
    check_raise->RAISE; call->CALL, fold->FOLD, raise->RAISE, all_in->ALL_IN.

Para a concordancia HEADLINE uso 4 BALDES (o advisor nao distingue bet de raise, e a
pergunta e agressao-vs-passividade):
    AGGRO = {BET, RAISE, ALL_IN}   CHECK   CALL   FOLD
Concordancia = mesmo balde. Leaks-chave:
    guia=AGGRO & advisor in {CHECK,FOLD}  -> PASSIVIDADE
    guia=CALL  & advisor=FOLD             -> OVERFOLD
Tambem imprimo a matriz de confusao 6x6 e a 4x4.
"""
import json
import os
import sys
import collections

import postflop_advisor
from multiway_equity import count_opponents  # (usado indiretamente pelo advisor)

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, 'fixtures', 'guia_posflop_fixtures.json')

# ---- potes de rua (A2) ----
LEAD_POT = {'FLOP': 5.5, 'TURN': 11.0, 'RIVER': 24.0}
POT_3BET = {'FLOP': 18.0, 'TURN': 34.0, 'RIVER': 60.0}

# ---- fracao da aposta enfrentada por spot (A5) ----
FACE_FRAC_DEFAULT = 0.6

# ===========================================================================
# normalizacao de acao -> familia
# ===========================================================================
_FAM = {'bet': 'BET', 'raise': 'RAISE', 'check': 'CHECK', 'call': 'CALL',
        'fold': 'FOLD', 'all_in': 'ALL_IN', 'allin': 'ALL_IN'}


def adv_family(rec):
    """`recommended` do advisor -> familia de 6."""
    r = (rec or '').lower().replace('-', '_')
    return _FAM.get(r, 'OTHER:' + r)


def guia_family(action, facing):
    """Acao do guia -> familia de 6, sensivel ao no (facing=True/False)."""
    a = (action or '').lower()
    if a in ('bet', 'check', 'call', 'fold', 'raise', 'all_in'):
        return _FAM[a]
    # compostas check_*
    if a == 'check_call':
        return 'CALL' if facing else 'CHECK'
    if a == 'check_fold':
        return 'FOLD' if facing else 'CHECK'
    if a == 'check_raise':
        return 'RAISE' if facing else 'CHECK'
    return 'OTHER:' + a


_BUCKET = {'BET': 'AGGRO', 'RAISE': 'AGGRO', 'ALL_IN': 'AGGRO',
           'CHECK': 'CHECK', 'CALL': 'CALL', 'FOLD': 'FOLD'}


def bucket(fam):
    return _BUCKET.get(fam, fam)


# ===========================================================================
# reconstrucao do spot
# ===========================================================================
def _stack_of(fx):
    return 25.0 if '25bb' in fx['scenario'] else 40.0


def _is_solver(fx):
    return fx['scenario'].startswith('SOLVER')


# FACING (heroi enfrenta aposta) e inferido da ACAO DO GUIA, universalmente: so se
# call/fold/raise vs uma aposta. bet/check/all_in(jam) e check_* sao decisao de LEADER
# (to_call=0; a acao imediata e apostar/checar). Isso resolve os scenarios SOLVER, que
# misturam no mesmo dump spots de lider (bet/check) e de defesa (call/fold).
_FACING_ACTIONS = frozenset({'call', 'fold', 'raise'})


def _scenario_profile(fx):
    """Perfil do spot que NAO depende do no (posicoes, pot_type, villains) + os
    atributos do LADO LIDER (lead_aggressor, lead_line) e a FRACAO da aposta
    enfrentada (face_frac). O no (facing/leader) vem da acao."""
    sec = fx['section']
    scn = fx['scenario']
    st = fx['street']
    p = dict(hero_pos='BTN', villain_pos='BB', pot_type='single_raised', villains=1,
             lead_aggressor='hero', lead_line=None, face_frac=FACE_FRAC_DEFAULT,
             xraise=False)

    if _is_solver(fx):
        if sec == 'squeeze':
            p.update(pot_type='three_bet', face_frac=1.0)
        elif sec == 'blind_war':
            p.update(hero_pos='BB', villain_pos='SB', face_frac=0.4)
        elif sec == 'multiway':
            p.update(pot_type='multiway', villains=2, face_frac=0.5)
        elif sec == 'triple_barrel':
            p.update(hero_pos='BB', villain_pos='BTN', face_frac=0.66)  # defende barril OOP
        elif sec == 'bluff_catch':
            p.update(hero_pos='BB', villain_pos='BTN', face_frac=0.6)   # defende OOP
        elif sec == 'float':
            p.update(face_frac=0.4, lead_aggressor=None)   # float: donk pequeno / stab
        elif sec == 'probe':
            p.update(lead_aggressor=None, lead_line='checked_back')
        return p

    # ---- scenarios "Situacao:" ----
    if 'c-beta 55%' in scn:                      # S2 (voce BB enfrenta c-bet 55%)
        p.update(hero_pos='BB', villain_pos='BTN', face_frac=0.55)
    elif 'c-beta 35%' in scn:                    # S2b
        p.update(hero_pos='BB', villain_pos='BTN', face_frac=0.35)
    elif 'check-raise 4x' in scn:                # S9 (enfrenta um check-raise 4x)
        p.update(hero_pos='BTN', villain_pos='BB', xraise=True)
    elif 'turn, BB check' in scn:                # S3 / S4 (barril de turn, heroi lidera)
        p.update(hero_pos='BTN', villain_pos='BB', lead_aggressor='hero')
        if sec == 'bet_check_bet' and st == 'RIVER':
            p['lead_line'] = 'checked_turn'
    elif 'pagou o donk' in scn:                  # S5 (float lidera turn IP)
        p.update(hero_pos='BTN', villain_pos='BB', lead_aggressor=None)
    elif 'Flop check-check' in scn:              # S6 (probe)
        p.update(hero_pos='BB', villain_pos='BTN', lead_aggressor=None,
                 lead_line='checked_back')
        if sec == 'multiway':
            p.update(pot_type='multiway', villains=2)
    elif 'deu check no flop' in scn:             # S7 (delayed c-bet)
        p.update(hero_pos='BTN', villain_pos='BB', lead_aggressor='hero',
                 lead_line='delayed')
    else:                                        # S1 / S8 (c-bet flop, heroi lidera)
        if sec == 'cbet_oop':
            p.update(hero_pos='CO', villain_pos='BTN')    # heroi PFR OOP (A4)
        elif sec == 'cbet_vs_sb':
            p.update(hero_pos='BTN', villain_pos='SB')    # vilao SB cold-call (A4)
        else:
            p.update(hero_pos='BTN', villain_pos='BB')
    return p


def classify_spot(fx):
    """Devolve dict do spot: facing(bool), face_frac, aggressor, villain_line,
    pot_type, villains, hero_pos, villain_pos, stack. O NO (facing/leader) vem da
    acao do guia; o resto, do perfil do scenario."""
    p = _scenario_profile(fx)
    facing = fx['action'] in _FACING_ACTIONS or p['xraise']
    spot = dict(facing=facing, face_frac=p['face_frac'], pot_type=p['pot_type'],
                villains=p['villains'], hero_pos=p['hero_pos'],
                villain_pos=p['villain_pos'], stack=_stack_of(fx),
                _xraise=p['xraise'])
    if facing:
        spot['aggressor'] = 'v1'                  # quem aposta tem a iniciativa
        spot['villain_line'] = None
    else:
        spot['aggressor'] = p['lead_aggressor']
        spot['villain_line'] = p['lead_line']
    return spot


def build_state(fx, spot):
    """Monta (table_state, kwargs) para advise_postflop a partir do spot."""
    st = fx['street']
    stack = spot['stack']
    base = POT_3BET if spot['pot_type'] == 'three_bet' else LEAD_POT
    S = base.get(st, 5.5)
    if spot['pot_type'] == 'three_bet':
        stack = round(1.2 * S, 1)                 # SPR ~1.2 (guia)

    if spot['facing']:
        if spot.get('_xraise'):
            cbet = 0.35 * LEAD_POT['FLOP']
            raise_to = 4 * cbet
            pot = LEAD_POT['FLOP'] + cbet + raise_to
            to_call = raise_to - cbet
        else:
            B = spot['face_frac'] * S
            pot = S + B
            to_call = B
    else:
        pot = S
        to_call = 0.0

    table_state = {
        'pot': {'pot_bb': round(pot, 3)},
        'to_call': {'to_call_bb': round(to_call, 3)},
        'seats': {'hero': {'stack_bb': stack},
                  'v1': {'stack_bb': stack, 'in_hand': True}},
        'positions': {'hero': spot['hero_pos'], 'v1': spot['villain_pos']},
    }
    if spot['villains'] >= 2:
        table_state['seats']['v2'] = {'stack_bb': stack, 'in_hand': True}
        table_state['positions']['v2'] = 'SB'

    kwargs = dict(street=st, aggressor=spot['aggressor'], pot_type=spot['pot_type'],
                  villain_line=spot['villain_line'])
    if spot['villains'] >= 2:
        kwargs['villains'] = spot['villains']
    return table_state, kwargs


# ===========================================================================
# run
# ===========================================================================
def run():
    with open(CORPUS, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    errors = collections.Counter()
    for fx in data:
        spot = classify_spot(fx)
        ts, kw = build_state(fx, spot)
        try:
            adv = postflop_advisor.advise_postflop(ts, fx['hand'], fx['board'], **kw)
        except Exception as e:                    # noqa: BLE001 - diagnostico
            errors['EXC:' + type(e).__name__] += 1
            continue
        status = adv.get('status')
        rec = adv.get('recommended')
        gfam = guia_family(fx['action'], spot['facing'])
        if status != 'ADVICE' or rec is None:
            afam = 'ABSTAIN'
            abucket = 'ABSTAIN'
        else:
            afam = adv_family(rec)
            abucket = bucket(afam)
        gbucket = bucket(gfam)
        rows.append(dict(fx=fx, spot=spot, gfam=gfam, afam=afam,
                         gbucket=gbucket, abucket=abucket, rec=rec, status=status,
                         made=adv.get('made'), caveats=adv.get('caveats') or []))
    return rows, errors


def pct(n, d):
    return (100.0 * n / d) if d else 0.0


def _agree(r):
    return r['gbucket'] == r['abucket']


def report(rows, errors):
    out = []
    w = out.append
    n = len(rows)
    agree = sum(1 for r in rows if _agree(r))
    scored = n  # ABSTAIN conta como desacordo (o guia sempre age)

    w('=' * 78)
    w('SCORECARD advise_postflop  x  guia pos-flop (baseline, sem villain_range)')
    w('=' * 78)
    w('fixtures carregados: %d   |   avaliados: %d   |   erros: %s'
      % (n + sum(errors.values()), n, dict(errors) or '{}'))
    w('')
    w('CONCORDANCIA GERAL (4 baldes AGGRO/CHECK/CALL/FOLD): %d/%d = %.1f%%'
      % (agree, scored, pct(agree, scored)))
    abst = sum(1 for r in rows if r['abucket'] == 'ABSTAIN')
    w('(advisor ABSTAIN/ sem rec: %d = %.1f%%, contados como desacordo)'
      % (abst, pct(abst, n)))
    w('')

    # ---- leaks-chave ----
    pass_check = [r for r in rows if r['gbucket'] == 'AGGRO' and r['abucket'] == 'CHECK']
    pass_fold = [r for r in rows if r['gbucket'] == 'AGGRO' and r['abucket'] == 'FOLD']
    pass_abst = [r for r in rows if r['gbucket'] == 'AGGRO' and r['abucket'] == 'ABSTAIN']
    overfold = [r for r in rows if r['gbucket'] == 'CALL' and r['abucket'] == 'FOLD']
    guia_aggro = [r for r in rows if r['gbucket'] == 'AGGRO']
    guia_call = [r for r in rows if r['gbucket'] == 'CALL']
    w('-' * 78)
    w('LEAKS-CHAVE (passividade)')
    w('-' * 78)
    w('guia=AGGRO(bet/raise) & advisor=CHECK : %d   (de %d AGGRO = %.1f%%)'
      % (len(pass_check), len(guia_aggro), pct(len(pass_check), len(guia_aggro))))
    w('guia=AGGRO(bet/raise) & advisor=FOLD  : %d   (de %d AGGRO = %.1f%%)'
      % (len(pass_fold), len(guia_aggro), pct(len(pass_fold), len(guia_aggro))))
    w('guia=AGGRO & advisor=ABSTAIN          : %d   (de %d AGGRO = %.1f%%)'
      % (len(pass_abst), len(guia_aggro), pct(len(pass_abst), len(guia_aggro))))
    tot_pass = len(pass_check) + len(pass_fold) + len(pass_abst)
    w('  => passividade TOTAL (AGGRO virou check/fold/abstain): %d de %d = %.1f%%'
      % (tot_pass, len(guia_aggro), pct(tot_pass, len(guia_aggro))))
    w('guia=CALL & advisor=FOLD (overfold)   : %d   (de %d CALL = %.1f%%)'
      % (len(overfold), len(guia_call), pct(len(overfold), len(guia_call))))
    w('')

    # ---- por categoria ----
    def table_by(keyfn, title):
        w('-' * 78)
        w('CONCORDANCIA POR %s' % title)
        w('-' * 78)
        agg = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            k = keyfn(r)
            agg[k][1] += 1
            if _agree(r):
                agg[k][0] += 1
        w('%-28s %6s %6s %7s' % ('', 'ok', 'tot', '%'))
        for k in sorted(agg, key=lambda x: -agg[x][1]):
            ok, tot = agg[k]
            w('%-28s %6d %6d %6.1f%%' % (str(k)[:28], ok, tot, pct(ok, tot)))
        w('')

    table_by(lambda r: r['fx']['section'], 'SECTION')
    table_by(lambda r: r['fx']['street'], 'STREET')
    table_by(lambda r: r['fx']['action'], 'ACAO DO GUIA')
    table_by(lambda r: r['gbucket'], 'BALDE DO GUIA')

    # ---- matriz de confusao 4x4 (baldes) ----
    w('-' * 78)
    w('MATRIZ DE CONFUSAO (linha=GUIA, coluna=ADVISOR) -- baldes')
    w('-' * 78)
    cols = ['AGGRO', 'CHECK', 'CALL', 'FOLD', 'ABSTAIN']
    rowsk = ['AGGRO', 'CHECK', 'CALL', 'FOLD']
    cm = collections.defaultdict(int)
    for r in rows:
        cm[(r['gbucket'], r['abucket'])] += 1
    w('%-8s %s' % ('guia\\adv', ' '.join('%8s' % c for c in cols)))
    for gk in rowsk:
        w('%-8s %s' % (gk, ' '.join('%8d' % cm[(gk, c)] for c in cols)))
    w('')

    # ---- matriz 6x6 (familias) ----
    w('-' * 78)
    w('MATRIZ DE CONFUSAO (linha=GUIA, coluna=ADVISOR) -- familias 6')
    w('-' * 78)
    fcols = ['BET', 'RAISE', 'ALL_IN', 'CHECK', 'CALL', 'FOLD', 'ABSTAIN']
    frows = ['BET', 'RAISE', 'ALL_IN', 'CHECK', 'CALL', 'FOLD']
    fm = collections.defaultdict(int)
    for r in rows:
        fm[(r['gfam'], r['afam'])] += 1
    w('%-8s %s' % ('guia\\adv', ' '.join('%7s' % c for c in fcols)))
    for gk in frows:
        w('%-8s %s' % (gk, ' '.join('%7d' % fm[(gk, c)] for c in fcols)))
    w('')

    # ---- 20 piores desacordos (prioriza leaks de passividade/overfold) ----
    w('-' * 78)
    w('20 PIORES DESACORDOS (prioriza guia=AGGRO->check/fold/abstain e CALL->fold)')
    w('-' * 78)

    def sev(r):
        g, a = r['gbucket'], r['abucket']
        if g == 'AGGRO' and a in ('FOLD', 'ABSTAIN'):
            return 0
        if g == 'AGGRO' and a == 'CHECK':
            return 1
        if g == 'CALL' and a == 'FOLD':
            return 2
        if g == 'CALL' and a == 'ABSTAIN':
            return 3
        return 4
    dis = [r for r in rows if not _agree(r)]
    dis.sort(key=lambda r: (sev(r), r['fx']['section']))
    for r in dis[:20]:
        fx = r['fx']
        cav = [c for c in r['caveats'] if c not in postflop_advisor.BASE_CAVEATS][:3]
        w('[%s->%s] %-13s %-5s %-10s board=%-10s hero=%-5s'
          % (r['gbucket'], r['abucket'], fx['section'], fx['street'], fx['action'],
             ''.join(fx['board']), ''.join(fx['hand'])))
        w('      guia=%s  advisor=%s(%s)  made=%s  frac=%.2f  note=%s'
          % (fx['action'], r['rec'], r['status'], r['made'],
             (r['spot']['face_frac'] or 0) if r['spot']['facing'] else 0.0,
             (fx['note'] or '')[:50]))
        if cav:
            w('      caveats: %s' % ', '.join(cav))
    w('')
    return '\n'.join(out)


if __name__ == '__main__':
    rows, errors = run()
    text = report(rows, errors)
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(text)
