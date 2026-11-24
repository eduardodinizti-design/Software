"""Política da tag NVT (parceiro do time) — [[nvt-exploit-anti-bot-pppoker]].

Objetivo (Eduardo, 23/11): EVITAR o confronto com jogadores do time para NÃO INTERFERIR
nos ESTUDOS deles. NÃO é soft-play/colusão — a única ação permitida é RETIRAR-SE da mão:

  • NVT é o AGRESSOR INICIAL (abriu / limp-raiseou) e estamos reagindo -> FOLD 100% do range
    (nem defende o BB). Se estiver de GRAÇA (to_call<=0) -> CHECK ([[nvt-regra-nunca-foldar-com-check]]).
  • NÓS é que fomos o agressor e o NVT continuou (call/3bet) -> jogar o mais HONESTO possível:
    a base GTO, SEM nenhum desvio exploratório.

Nunca cede pote ativamente, nunca dumpa fichas, nunca sinaliza carta. Puro: não lê tela,
não clica. SHADOW / validated=False.
"""

_EXPLOIT_KEYS = ('exploit', 'exploit_bot', 'exploit_preflop', 'exploit_postflop')


def apply(advice, *, hero_was_first_aggressor, to_call=None):
    """Advice base + quem iniciou a agressão -> advice ajustada pela política NVT.
    `hero_was_first_aggressor`: True se NÓS abrimos/agredimos primeiro e o NVT só reagiu."""
    if not isinstance(advice, dict) or advice.get('status') != 'ADVICE':
        return advice
    if hero_was_first_aggressor:
        # nós abrimos e o NVT pagou/3betou: joga HONESTO = base GTO, sem exploit algum
        out = dict(advice)
        for k in _EXPLOIT_KEYS:
            out.pop(k, None)
        out['nvt'] = dict(policy='play_honest')
        out['caveats'] = list(advice.get('caveats') or []) + ['NVT_PLAY_HONEST']
        return out
    # NVT iniciou a agressão e estamos reagindo -> SAIR da mão (sem foldar de graça)
    tc = to_call if to_call is not None else advice.get('to_call')
    free = isinstance(tc, (int, float)) and tc <= 0
    action = 'check' if free else 'fold'
    return dict(advice, recommended=action,
                nvt=dict(policy='avoid', free=free),
                caveats=list(advice.get('caveats') or []) + ['NVT_AVOID_%s' % action.upper()])
