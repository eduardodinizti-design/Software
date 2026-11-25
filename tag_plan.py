"""TAG -> PLANO: o que fazer contra cada etiqueta — [[nvt-exploit-anti-bot-pppoker]].

"Mediante as tags que o Henrique criar, a gente traça um plano para cada um" (Eduardo, 23/11).
A tag MANUAL (`player_tags`) manda; a sugestão automática (`bot_exploit.detect_bot`) só
acompanha. SHADOW / validated=False — descreve a intenção; o enforce no fluxo de decisão
pluga depois de homologar.

Planos iniciais (ajustáveis — o Eduardo pode criar tags novas; tag sem plano = NEUTRO +
needs_definition, ele define depois):
  • bote    -> EXPLORAÇÃO MÁXIMA (range face-up/capado): overfold à linha, JAM valor. (bot_exploit)
  • station -> só VALOR (grande), ZERO blefe (não dobra no river). (villain_strategy/postflop_exploit)
  • bom     -> SÓLIDO perto do GTO: respeitar a agressão, não doar, evitar guerra marginal OOP.
  • nvt     -> TIME NOSSO: não explorar hostil; evitar confronto grande marginal (plano amigável).
"""

# aliases -> tag canônica (o Eduardo escreve como quiser; aqui normaliza o conhecido)
_ALIASES = {
    'bote': 'bote', 'bot': 'bote', 'robo': 'bote', 'robô': 'bote',
    'station': 'station', 'calling_station': 'station', 'paga_tudo': 'station',
    'bom': 'bom', 'reg': 'bom', 'bom_jogador': 'bom', 'forte': 'bom',
    'nvt': 'nvt', 'time': 'nvt', 'time_nvt': 'nvt', 'parceiro': 'nvt',
}

PLANS = {
    'bote': dict(
        label='Bote (bot)', aggression='max', hostile=True,
        apply='bot_exploit.exploit_vs_bot',
        apply_postflop='bot_exploit.exploit_vs_bot_postflop',
        summary='Range FACE-UP/capado, estático. Explorar sem dó: PRÉ overfold marginais à '
                'linha limp-reraise e JAM valor forte. PÓS overfold bluffcatchers vs a aposta '
                'de valor dele; atacar quando o board capa o range premium e ele passa.',
        notes=['linha-chave: limp-reraise (premium)', 'JAM valor: QQ+/AK (homologar)',
               'pós: ele aposta=valor -> overfold; board s/ A/K/Q + check dele -> blefar']),
    'station': dict(
        label='Station (paga tudo)', aggression='value', hostile=True,
        apply='postflop_exploit.exploit_postflop',
        summary='Paga demais: value bet MAIOR e mais fino; ZERO blefe; não dobrar no river.',
        notes=['size de valor sobe um degrau do slider', 'sem c-bet blefe']),
    'bom': dict(
        label='Bom jogador (respeitar)', aggression='solid', hostile=False,
        apply=None,
        summary='Jogar SÓLIDO perto do GTO: não doar, respeitar a agressão dele, evitar '
                'guerra de blefe marginal fora de posição. Sem exploit arriscado.',
        notes=['perto da base GTO', 'reduzir confronto marginal OOP']),
    'nvt': dict(
        label='Time NVT (parceiro)', aggression='avoid', hostile=False,
        apply='nvt_policy.apply',
        summary='EVITAR o confronto p/ não interferir nos ESTUDOS do parceiro. Se o NVT abre '
                '/agride primeiro -> FOLD 100% (nem defende BB; check se de graça). Se NÓS '
                'abrimos e ele continua -> jogar o mais HONESTO (base GTO, zero exploit). '
                'Nunca ceder pote/dumpar fichas (não é soft-play).',
        notes=['NVT agressor inicial -> fold tudo', 'nós agressores -> honesto/base',
               'só retirada passiva; sem colusão']),
}


def canonical(tag):
    """Tag (livre) -> tag canônica conhecida, ou a própria (minúscula) se for custom."""
    if tag is None:
        return None
    t = str(tag).strip().lower()
    return _ALIASES.get(t, t)


def plan_for_tag(tag):
    """Plano de uma etiqueta. Conhecida -> plano; custom sem plano -> NEUTRO +
    needs_definition=True (o Eduardo define). None -> None."""
    if tag is None:
        return None
    canon = canonical(tag)
    p = PLANS.get(canon)
    if p:
        return dict(p, tag=canon, known=True, needs_definition=False)
    return dict(tag=canon, known=False, needs_definition=True, aggression='neutral',
                hostile=False, apply=None,
                label=str(tag), summary='Tag sem plano definido — jogar a base GTO até o '
                                        'Eduardo traçar o plano desta etiqueta.', notes=[])


def resolve(uid, store, *, stats=None, club_is_bot=False):
    """Decisão final de perfil p/ um uid: TAG MANUAL (autoridade) + SUGESTÃO automática.
    Devolve dict(uid, tag, plan, suggestion). `store`=player_tags.TagStore; `stats` liga a
    auto-detecção de bote. Tag manual ausente -> plan=None e segue só a sugestão."""
    manual = store.tag_of(uid) if store else None
    plan = plan_for_tag(manual) if manual else None
    suggestion = None
    if stats is not None:
        from bot_exploit import detect_bot
        sug = detect_bot(stats, club_is_bot=club_is_bot)
        if sug.get('is_bot_suspect'):
            # só sugere se ainda NÃO está marcado como bote
            suggestion = dict(sug, suggest_tag='bote',
                              already_tagged=(canonical(manual) == 'bote') if manual else False)
    return dict(uid=_s(uid), tag=canonical(manual) if manual else None,
                plan=plan, suggestion=suggestion)


def _s(x):
    return str(x).strip()
