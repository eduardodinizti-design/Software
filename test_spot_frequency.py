"""Testes do cruzamento frequência×cobertura."""
from spot_frequency import stack_bucket, pot_class, is_covered, spot_key


def test_stack_buckets():
    assert stack_bucket(8) == '<15bb'
    assert stack_bucket(22) == '15-25bb'
    assert stack_bucket(30) == '25-40bb'
    assert stack_bucket(50) == '40-60bb'
    assert stack_bucket(120) == '60bb+'
    assert stack_bucket(None) == '?'


def test_pot_class():
    assert pot_class(None) == 'SRP'
    assert pot_class('three_bet') == '3bet'
    assert pot_class('multiway') == 'multiway'


def test_coverage_rule():
    # coberto: SRP, HU, flop, 25-40bb
    assert is_covered('SRP', True, '25-40bb', 'FLOP') is True
    # descoberto: multiway
    assert is_covered('multiway', False, '25-40bb', 'FLOP') is False
    # descoberto: turn
    assert is_covered('SRP', True, '25-40bb', 'TURN') is False
    # descoberto: 3bet
    assert is_covered('3bet', True, '25-40bb', 'FLOP') is False
    # descoberto: stack fora de faixa
    assert is_covered('SRP', True, '60bb+', 'FLOP') is False


def test_spot_key():
    d = {'pot_type': None, 'opponents': 1, 'hero_stack_bb': 30, 'street': 'FLOP'}
    assert spot_key(d) == ('SRP', 'HU', '25-40bb', 'FLOP')
    d2 = {'pot_type': 'multiway', 'opponents': 3, 'hero_stack_bb': 12, 'street': 'TURN'}
    assert spot_key(d2) == ('multiway', 'MW', '<15bb', 'TURN')
