"""Testes da política NVT (evitar o parceiro, sem soft-play)."""
from nvt_policy import apply


def _adv(rec='call', **kw):
    return dict(status='ADVICE', recommended=rec, **kw)


def test_nvt_opener_we_fold_when_facing_bet():
    out = apply(_adv('call'), hero_was_first_aggressor=False, to_call=300)
    assert out['recommended'] == 'fold'
    assert out['nvt']['policy'] == 'avoid' and out['nvt']['free'] is False
    assert 'NVT_AVOID_FOLD' in out['caveats']


def test_nvt_opener_we_check_when_free():
    out = apply(_adv('raise'), hero_was_first_aggressor=False, to_call=0)
    assert out['recommended'] == 'check'           # nunca foldar de graça
    assert out['nvt']['free'] is True and 'NVT_AVOID_CHECK' in out['caveats']


def test_to_call_from_advice_when_not_passed():
    out = apply(_adv('call', to_call=500), hero_was_first_aggressor=False)
    assert out['recommended'] == 'fold'


def test_hero_aggressor_plays_honest_and_strips_exploit():
    adv = _adv('bet', exploit_bot={'x': 1}, exploit_postflop={'y': 2},
               caveats=['EXPLOIT_BOT_FOO'])
    out = apply(adv, hero_was_first_aggressor=True)
    assert out['recommended'] == 'bet'             # mantém a decisão honesta
    assert 'exploit_bot' not in out and 'exploit_postflop' not in out
    assert out['nvt']['policy'] == 'play_honest' and 'NVT_PLAY_HONEST' in out['caveats']


def test_not_advice_passthrough():
    adv = dict(status='ABSTAIN', recommended=None)
    assert apply(adv, hero_was_first_aggressor=False, to_call=100) == adv


def test_avoid_does_not_mutate_input():
    adv = _adv('call', caveats=['BASE'])
    apply(adv, hero_was_first_aggressor=False, to_call=100)
    assert adv['recommended'] == 'call' and adv['caveats'] == ['BASE']
