"""Auditor NATIVO de leaks pós-flop a partir do histórico (.txt) do PPPoker.

Substitui a auditoria por IA (Gemini) do estudo VisualPilot 2.0 pelo NOSSO próprio
cérebro: para cada decisão pós-flop do hero (reconstruída por `hand_history.py`),
chama `advise_postflop` e compara a ação REAL do hero com a recomendação do cérebro.
Quando o cérebro dá uma recomendação confiante (status ADVICE) e o hero fez o
contrário num sentido que custa fichas, registra um LEAK, classifica por categoria /
street / gravidade, dá um exemplo e a correção. Agrega num relatório estruturado.

Vantagens vs a versão com IA: roda offline, determinístico, NÃO manda os seus
históricos de mão para um serviço externo (privacidade) e não depende de chave/modelo.
PURO: só leitura de texto + matemática do cérebro; não captura tela nem clica. Quando
o cérebro ABSTÉM (precisa de leitura do vilão), a decisão NÃO é graduada (honesto).
"""
from hand_history import parse_hand_histories
from postflop_advisor import advise_postflop
from postflop_eval import classify_board
from postflop_adjustments import scare_from_transition

_ONE_PAIR = ('top_pair', 'second_pair', 'third_pair', 'low_pair', 'overpair', 'underpair')
_WEAK = ('air', 'overcards', 'board_pair_only', 'plays_board')
# Mãos de VALOR FEITO: só aqui "dar check" é leak de valor não extraído (dar check com
# draw/ar é jogada legítima, não leak — não marcamos).
_VALUE_MADE = ('set', 'trips', 'two_pair', 'overpair', 'straight', 'flush',
               'full_house', 'quads', 'straight_flush', 'top_pair')
_SEV_WEIGHT = dict(alta=3, media=2, baixa=1)

# Correções canônicas por categoria (referenciam a regra do cérebro pós-flop).
_FIXES = {
    'Hero Call no River (pool underbluff)':
        'O cérebro folda: equity < pot odds e a linha passivo->agressivo no pool da '
        'Evolution é sub-blefada. Não pague bluffcatcher de 1 par contra aposta/raise '
        'grande no river sem leitura (hud_exploit) que justifique.',
    'Pagada indevida (call sem equity vs range)':
        'Equity do hero contra o range que continua apostando fica abaixo das pot odds '
        '(+ deságio). Foldar 1 par/mão marginal em vez de pagar por categoria.',
    'Continua sem equity (spew)':
        'Mão sem feito nem draw com equity suficiente; o cérebro folda. Desistir em vez '
        'de pagar por teimosia.',
    'C-Bet de ar multi-way':
        'Blefe de c-bet com 3+ na mão: a fold equity colapsa (multiway_equity bloqueia '
        'blefe >2 oponentes). Dar check com ar em pote multiway.',
    'C-Bet de ar (sem equity/fold equity)':
        'Blefe sem equity nem backup; o cérebro dá check/give-up. Reservar o blefe para '
        'quando houver draw (semi-blefe) ou leitura folds_to_cbet.',
    'Raise sem valor/fold equity':
        'Raise sem equity de valor (>=60% vs range) nem fold equity; o cérebro paga ou '
        'folda em vez de aumentar.',
    'Fold indevido (desiste de valor)':
        'O cérebro aumentaria por valor aqui; foldar larga equity/valor. Revisar o medo '
        'excessivo do board.',
    'Fold marginal (desiste de equity)':
        'O cérebro pagaria pelas pot odds/implied; o fold perde EV marginal.',
    'Valor não apostado (missed value)':
        'Mão de valor passou a vez; o cérebro apostaria (size por vantagem de range/nuts). '
        'Extrair valor em vez de dar check.',
}


def _grade(decision, hero_cards):
    """Devolve (leak|None, graded_bool). Leak é um dict com categoria/street/gravidade/
    exemplo/correção. graded=False quando o cérebro abstém (não dá p/ graduar)."""
    if not hero_cards or len(hero_cards) != 2:
        return None, False
    board = decision['board']
    if len(board) < 3:
        return None, False
    opp = decision['opponents']
    ts = dict(pot=dict(pot_bb=decision['pot_bb']),
              to_call=dict(to_call_bb=decision['to_call_bb']),
              seats=dict(hero=dict(stack_bb=decision['hero_stack_bb'], occupied=True)),
              positions=dict(hero='BTN'))
    try:
        adv = advise_postflop(ts, hero_cards, board, street=decision['street'],
                              aggressor=decision['aggressor'], pot_type=decision['pot_type'],
                              villains=opp if isinstance(opp, int) and opp > 0 else None,
                              villain_line=decision['villain_line'])
    except (ValueError, KeyError, TypeError):
        return None, False
    if adv.get('status') != 'ADVICE':
        return None, False
    rec = adv.get('recommended')
    if not rec:
        return None, False

    made = adv.get('made')
    act = decision['hero_action']
    to_call = decision['to_call_bb']
    pot = decision['pot_bb']
    big_bet = bool(to_call and pot and (to_call / (pot + to_call)) > 0.40)
    scare_kind = scare_from_transition(board[:-1], board) if len(board) > 3 else 'brick'
    scare = scare_kind not in (None, 'brick')
    try:
        bcls = classify_board(board)
    except (ValueError, KeyError, TypeError):
        bcls = {}

    cat = sev = None
    # A) Pagou onde o cérebro folda.
    if act == 'call' and rec == 'fold':
        if decision['street'] == 'RIVER' and (big_bet or scare or
                                              decision['villain_line'] == 'passive_turned_aggressive'):
            cat, sev = 'Hero Call no River (pool underbluff)', 'alta'
        elif made in _ONE_PAIR:
            cat, sev = 'Pagada indevida (call sem equity vs range)', ('alta' if big_bet else 'media')
        else:
            cat, sev = 'Continua sem equity (spew)', 'media'
    # B) Aumentou onde o cérebro não aumenta.
    elif act == 'raise' and rec in ('fold', 'call', 'check'):
        cat, sev = 'Raise sem valor/fold equity', ('alta' if opp and opp >= 2 else 'media')
    # C) Apostou de ar onde o cérebro dá check.
    elif act == 'bet' and rec == 'check' and made in _WEAK:
        if opp and opp >= 2:
            cat, sev = 'C-Bet de ar multi-way', 'alta'
        else:
            cat, sev = 'C-Bet de ar (sem equity/fold equity)', 'media'
    # D) Foldou onde o cérebro pagaria/aumentaria.
    elif act == 'fold' and rec in ('call', 'raise'):
        if rec == 'raise':
            cat, sev = 'Fold indevido (desiste de valor)', 'media'
        else:
            cat, sev = 'Fold marginal (desiste de equity)', 'baixa'
    # E) Deu check com VALOR FEITO onde o cérebro apostaria (check de draw/ar não é leak).
    elif act == 'check' and rec == 'bet' and made in _VALUE_MADE:
        cat, sev = 'Valor não apostado (missed value)', 'media'

    if not cat:
        return None, True      # graduada e alinhada (sem leak)

    spot = ('%s [%s] Hero[%s] pote %.1f BB, pagar %.1f BB — hero %s; cérebro: %s (mão=%s%s)'
            % (decision['street'], ' '.join(board), ' '.join(hero_cards), pot, to_call,
               act.upper(), rec.upper(), made, ', scare=%s' % scare_kind if scare else ''))
    return dict(category=cat, severity=sev, street=decision['street'].capitalize(),
                hero_action=act, brain_recommended=rec, made=made,
                example_spot=spot, recommended_fix=_FIXES.get(cat, '')), True


def _grade_scale(grade_ratio):
    if grade_ratio == 0:
        return 'A'
    if grade_ratio <= 0.2:
        return 'B'
    if grade_ratio <= 0.4:
        return 'C+'
    if grade_ratio <= 0.7:
        return 'C'
    return 'D'


def audit_text(raw_text, hero_name=None):
    """Audita um texto de histórico e devolve o relatório estruturado (dict)."""
    hands = parse_hand_histories(raw_text, hero_name)
    leaks = []
    decisions_reviewed = 0
    postflop_hands = 0
    for h in hands:
        if not h.has_postflop or not h.hero_cards:
            continue
        hand_had_decision = False
        for d in h.hero_decisions:
            leak, graded = _grade(d, h.hero_cards)
            if graded:
                decisions_reviewed += 1
                hand_had_decision = True
            if leak:
                leak = dict(leak, hand_id=h.id)
                leaks.append(leak)
        if hand_had_decision:
            postflop_hands += 1
    return _aggregate(len(hands), postflop_hands, decisions_reviewed, leaks)


def audit_file(path, hero_name=None):
    with open(path, encoding='utf-8', errors='replace') as f:
        return audit_text(f.read(), hero_name)


def _aggregate(total_hands, postflop_hands, decisions_reviewed, leaks):
    by_cat = {}
    for lk in leaks:
        c = lk['category']
        g = by_cat.setdefault(c, dict(category=c, occurrences=0, severities=[], streets=[],
                                      example_spot=lk['example_spot'],
                                      recommended_fix=lk['recommended_fix']))
        g['occurrences'] += 1
        g['severities'].append(lk['severity'])
        g['streets'].append(lk['street'])

    total_leaks = len(leaks)
    top = []
    for g in by_cat.values():
        sev = max(g['severities'], key=lambda s: _SEV_WEIGHT.get(s, 0))
        street = max(set(g['streets']), key=g['streets'].count)
        top.append(dict(category=g['category'], occurrences=g['occurrences'],
                        frequency_pct=round(g['occurrences'] / total_leaks * 100, 1) if total_leaks else 0.0,
                        severity=sev, affected_street=street,
                        example_spot=g['example_spot'], recommended_fix=g['recommended_fix']))
    top.sort(key=lambda t: (_SEV_WEIGHT.get(t['severity'], 0), t['occurrences']), reverse=True)

    weighted = sum(_SEV_WEIGHT.get(lk['severity'], 0) for lk in leaks)
    ratio = (weighted / decisions_reviewed) if decisions_reviewed else 0.0
    # Zero decisão elegível NÃO é nota 'A' (perfeito) — é SEM AVALIAÇÃO. Dar 'A' a um
    # histórico sem decisões pós-flop revisadas mente cobertura (contrato da auditoria).
    grade = _grade_scale(ratio) if decisions_reviewed else 'UNASSESSED'

    spew = sum(1 for lk in leaks if lk['category'] in (
        'Hero Call no River (pool underbluff)', 'Pagada indevida (call sem equity vs range)',
        'Continua sem equity (spew)', 'C-Bet de ar multi-way',
        'C-Bet de ar (sem equity/fold equity)', 'Raise sem valor/fold equity'))
    passive = sum(1 for lk in leaks if lk['category'] in (
        'Fold indevido (desiste de valor)', 'Fold marginal (desiste de equity)',
        'Valor não apostado (missed value)'))
    if spew > passive:
        profile, reason = 'tight', ('Predominam leaks de AGRESSÃO/pagadas indevidas (%d) — '
                                    'apertar: foldar mais marginais, blefar menos multiway.' % spew)
    elif passive > spew:
        profile, reason = 'loose', ('Predominam leaks PASSIVOS (%d: folds indevidos / valor não '
                                    'apostado) — abrir: pagar/apostar valor com mais frequência.' % passive)
    else:
        profile, reason = 'balanced', 'Sem viés dominante entre spew e passividade.'

    summary = ('%d mão(s) lida(s), %d pós-flop auditada(s), %d decisão(ões) graduada(s) contra o '
               'cérebro. %d leak(s) encontrado(s). Nota pós-flop: %s.'
               % (total_hands, postflop_hands, decisions_reviewed, total_leaks, grade))

    return dict(source='native_brain_no_ai',
                total_hands_detected=total_hands,
                postflop_hands_reviewed=postflop_hands,
                decisions_reviewed=decisions_reviewed,
                total_mistakes_found=total_leaks,
                overall_grade=grade,
                executive_summary=summary,
                recommended_profile=profile,
                profile_adjustment_reason=reason,
                top_mistakes=top)
