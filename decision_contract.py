"""Contrato de validade de decisão (B04 do plano de evolução do cérebro).

Decompõe a pergunta "esta decisão pode COMPROMETER fichas automaticamente?" em
requisitos EXPLÍCITOS e SEPARADOS, em vez de um único booleano `validated` que
band-aids conseguiam fabricar. A autorização de execução é derivada desses
requisitos — e NENHUM rótulo (premium) ou margem (call-off) substitui os demais.

Critério do plano (B04): "O operador não pode transformar ABSTAIN em decisão
validada; margem de call-off ou rótulo premium não substituem os demais
requisitos." Seção 7: "fallback promovido a validado: nenhum caso aceito."

Campos do contrato:
  source_validated      nó de FONTE validada, do contexto exato (não emprestado,
                        não referência/deep, não band-aid) — a única base para a
                        autoridade VALIDATED.
  context_match         o contexto consultado casa com o da fonte (EXACT): sem
                        stack emprestado e sem rótulo de fallback/premium.
  observation_confirmed a percepção que alimenta a decisão está confirmada
                        (cartas do hero lidas). Exigido p/ COMPROMETER ficha.
  action_legal          a ação está disponível (botão presente) no estado atual.
  sizing_supported      a ação não precisa de size, ou o size é do caminho
                        single-click (fold/check/call). Raise/bet/all-in saem
                        pelo sequenciador (fora deste caminho).

Autoridades de execução (uma, explícita, separada):
  VALIDATED        commit autorizado por nó validado + contexto exato.
  CALL_OFF         call-off com MARGEM de equity (equity-req >= call_margin). A
                   margem NÃO dispensa observação/legalidade/sizing.
  SAFETY_PREMIUM   premium sem nó validado ainda PAGA (honra "nunca foldar
                   premium"), mas como autoridade SEPARADA e NÃO-validada —
                   decisão explícita do usuário (Opção A), marcada como lacuna
                   de cobertura a resolver (P1 do plano). Nunca é 'validated'.
  SAFETY_NONCOMMIT fold/check: piso de segurança, nunca arrisca ficha; exige só
                   legalidade. NUNCA é rotulado 'validated'.
  NONE             sem autoridade -> não executa (estuda/abstém).

PURO: sem captura, sem clique, sem estado. Testável offline.
"""
import re

_CARD = re.compile(r'^[AKQJT2-9][cdhs]$')
_COMMIT = ('CALL', 'RAISE', 'BET', 'ALL_IN')
_NONCOMMIT = ('FOLD', 'CHECK')
_SINGLE_CLICK = ('FOLD', 'CHECK', 'CALL')


def _cards_ok(cards):
    return (isinstance(cards, (list, tuple)) and len(cards) == 2
            and all(isinstance(c, str) and _CARD.match(c) for c in cards)
            and cards[0] != cards[1])


# A13: SAFETY_PREMIUM é a ÚNICA autoridade que comita ficha sem nó validado (Opção A
# do usuário: nunca foldar premium). Restringido p/ não virar porta larga: só paga
# (CALL, nunca agride) e só mãos PREMIUM de verdade (I1: TT+/AK/AQ) — defesa em
# profundidade contra flag setado por engano em mão fraca.
_RANKS = 'AKQJT98765432'
_PREMIUM_PAIRS = frozenset({'TT', 'JJ', 'QQ', 'KK', 'AA'})
_PREMIUM_OFFPAIR = frozenset({'AK', 'AQ'})


def _is_premium_cards(cards):
    if not _cards_ok(cards):
        return False
    r0, r1 = cards[0][0], cards[1][0]
    if r0 == r1:
        return (r0 + r1) in _PREMIUM_PAIRS
    hi, lo = sorted((r0, r1), key=_RANKS.index)
    return (hi + lo) in _PREMIUM_OFFPAIR


def evaluate(advice, *, action, hero_cards=None, action_available=True,
             call_margin=0.04):
    """Avalia o contrato de validade de uma ação. Devolve os campos do contrato +
    `authority` + `execution_allowed` + `blockers` (motivos do que faltou).

    `action` em maiúsculas (FOLD/CHECK/CALL/RAISE/BET/ALL_IN). `hero_cards` é a
    leitura das cartas do hero (p/ observation_confirmed). `action_available` diz
    se o botão da ação existe no estado atual (legalidade)."""
    advice = advice or {}
    action = (action or '').upper()

    borrowed = advice.get('stack_borrowed_from') is not None
    is_fallback = bool(advice.get('fallback') or advice.get('deep_guard'))
    is_premium = advice.get('safety_premium') is True

    source_validated = (advice.get('validated') is True and not borrowed
                        and not is_fallback and not is_premium)
    context_match = (advice.get('status') == 'ADVICE' and not borrowed
                     and not is_fallback and not is_premium)
    observation_confirmed = _cards_ok(hero_cards)
    action_legal = bool(action_available)
    sizing_supported = action in _SINGLE_CLICK

    fields = dict(source_validated=source_validated, context_match=context_match,
                  observation_confirmed=observation_confirmed, action_legal=action_legal,
                  sizing_supported=sizing_supported)
    blockers = []
    if not action_legal:
        blockers.append('ACAO_ILEGAL')

    # Piso de segurança: fold/check nunca arriscam ficha. Autorizados só por
    # legalidade — e JAMAIS rotulados 'validated'. Não exigem observação (um
    # fold/check é a saída segura; o operador guarda cartas no fallback à parte).
    if action in _NONCOMMIT:
        allowed = action_legal and sizing_supported
        return dict(fields, authority='SAFETY_NONCOMMIT',
                    execution_allowed=allowed, blockers=blockers)

    if action not in _COMMIT:
        return dict(fields, authority='NONE', execution_allowed=False,
                    blockers=blockers + ['ACAO_DESCONHECIDA'])

    # COMMIT (arrisca ficha): precisa de UMA autoridade de commit E de TODOS os
    # demais requisitos (observação, legalidade, sizing). Margem/rótulo entram só
    # como AUTORIDADE — não substituem os requisitos abaixo.
    if not observation_confirmed:
        blockers.append('SEM_LEITURA')
    if not sizing_supported:
        blockers.append('SIZING_NAO_SUPORTADO')   # raise/bet/all-in: sai pelo sequenciador

    spot = str(advice.get('spot') or '')
    is_calloff = spot.startswith('call_off_')
    calloff_authority = False
    if is_calloff:
        eq = advice.get('equity')
        req = advice.get('required_equity_icm', advice.get('required_equity'))
        if not isinstance(eq, (int, float)) or not isinstance(req, (int, float)):
            blockers.append('CALLOFF_SEM_MARGEM')
        elif (eq - req) < call_margin:
            blockers.append('CALLOFF_NA_FRONTEIRA')
        else:
            calloff_authority = True

    if source_validated and context_match:
        authority = 'VALIDATED'
    elif calloff_authority:
        authority = 'CALL_OFF'
    elif is_premium and action == 'CALL' and _is_premium_cards(hero_cards):
        # A13: premium sem nó PAGA (honra I1), mas só com CALL e mão premium real.
        authority = 'SAFETY_PREMIUM'
    else:
        authority = 'NONE'
        if is_premium and action != 'CALL':
            blockers.append('PREMIUM_SO_PAGA_NAO_AGRIDE')   # premium nunca inicia agressão sem nó
        elif is_premium and observation_confirmed and not _is_premium_cards(hero_cards):
            blockers.append('PREMIUM_FLAG_SEM_MAO_PREMIUM')  # flag setado em mão não-premium
        elif not is_calloff:
            blockers.append('SEM_AUTORIDADE_VALIDADA')

    allowed = (authority != 'NONE' and observation_confirmed
               and action_legal and sizing_supported)
    return dict(fields, authority=authority, execution_allowed=allowed, blockers=blockers)
