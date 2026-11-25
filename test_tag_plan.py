"""Testes do roteador tag -> plano, e da resolução manual + sugestão."""
from player_tags import TagStore
from tag_plan import canonical, plan_for_tag, resolve


def test_aliases():
    assert canonical('bot') == 'bote' and canonical('Bote') == 'bote'
    assert canonical('time') == 'nvt' and canonical('parceiro') == 'nvt'
    assert canonical('reg') == 'bom'
    assert canonical('station') == 'station'
    assert canonical('xyz') == 'xyz'        # custom passa reto (minúscula)
    assert canonical(None) is None


def test_known_plans():
    p = plan_for_tag('bote')
    assert p['known'] and p['aggression'] == 'max' and p['hostile'] is True
    assert p['apply'] == 'bot_exploit.exploit_vs_bot'
    assert plan_for_tag('station')['aggression'] == 'value'
    assert plan_for_tag('bom')['hostile'] is False
    assert plan_for_tag('nvt')['hostile'] is False and plan_for_tag('nvt')['aggression'] == 'avoid'
    assert plan_for_tag('nvt')['apply'] == 'nvt_policy.apply'


def test_custom_tag_needs_definition():
    p = plan_for_tag('agressivo_demais')
    assert p['known'] is False and p['needs_definition'] is True
    assert p['aggression'] == 'neutral' and p['apply'] is None


def test_resolve_manual_tag_wins():
    s = TagStore(); s.set('1', 'bote')
    bot_stats = {'limp_reraise': 50.0, 'limp_reraise_opp': 8}
    r = resolve('1', s, stats=bot_stats, club_is_bot=True)
    assert r['tag'] == 'bote' and r['plan']['aggression'] == 'max'
    # já marcado como bote -> a sugestão reconhece
    assert r['suggestion']['already_tagged'] is True


def test_resolve_suggests_when_unmarked():
    s = TagStore()                          # ninguém marcado
    bot_stats = {'limp_reraise': 50.0, 'limp_reraise_opp': 8}
    r = resolve('1', s, stats=bot_stats)
    assert r['tag'] is None and r['plan'] is None
    assert r['suggestion']['suggest_tag'] == 'bote'
    assert r['suggestion']['already_tagged'] is False


def test_resolve_no_stats_no_suggestion():
    s = TagStore(); s.set('1', 'station')
    r = resolve('1', s)
    assert r['plan']['aggression'] == 'value' and r['suggestion'] is None


def test_resolve_clean_player_no_plan_no_suggestion():
    s = TagStore()
    r = resolve('ghost', s, stats={'limp_reraise': 0.0, 'limp_reraise_opp': 5})
    assert r['tag'] is None and r['plan'] is None and r['suggestion'] is None
