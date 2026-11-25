"""Testes do enum de ações/stage, ancorados nas linhas REAIS de hook_sequence_out.txt (18/11)."""
from ppp_actions import (to_hh_action, stage_name, is_post, ACTION_TYPES)


def test_stage_map():
    assert stage_name(1) == 'preflop'
    assert stage_name(2) == 'flop'
    assert stage_name(3) == 'turn'
    assert stage_name(4) == 'river'


def test_posts_are_posts():
    assert is_post(8) and is_post(9) and is_post(10)
    assert not is_post(1)
    # posts não viram "ação"
    assert to_hh_action(8, 500000, street_has_aggression=False) is None
    assert to_hh_action(9, 1000000, street_has_aggression=False) is None
    assert to_hh_action(10, 150000, street_has_aggression=False) is None


def test_fold_real_line27():
    # linha 27: seat2 actionType=1 chips=0 encarando aposta
    assert to_hh_action(1, 0, street_has_aggression=True) == {'action': 'folds'}


def test_check_real_line47():
    # linha 47: seat6 actionType=2 chips=0 com callNeed=0
    assert to_hh_action(2, 0, street_has_aggression=False) == {'action': 'checks'}


def test_call_real_line37():
    # linha 37: seat6 actionType=3 chips=1200000 = callNeedChips
    assert to_hh_action(3, 1200000, street_has_aggression=True) == {'action': 'calls', 'amount': 1200000}


def test_bet_first_aggression_line51():
    # linha 51: seat0 actionType=7 chips=2133300 abrindo aposta no flop
    assert to_hh_action(7, 2133300, street_has_aggression=False) == {'action': 'bets', 'amount': 2133300}


def test_raise_when_prior_aggression():
    assert to_hh_action(7, 5000000, street_has_aggression=True) == {'action': 'raises', 'to': 5000000}


def test_all_in_flag():
    assert to_hh_action(3, 7980000, street_has_aggression=True, is_all_in=True)['action'] == 'all-in'
    assert to_hh_action(7, 32000000, street_has_aggression=False, is_all_in=True)['action'] == 'all-in'


def test_unknown_action_preserved():
    r = to_hh_action(99, 123, street_has_aggression=False)
    assert r['action'] == 'action99' and r['amount'] == 123
