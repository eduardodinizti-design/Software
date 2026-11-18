"""Testes da percepção de FT/ICM (mtt_rank), ancorados em snapshots REAIS capturados
ao vivo via hook_mtt.js em 17/11/2026."""
from mtt_rank import (MttRankInfo, PHASE_FINAL_TABLE, PHASE_ITM, PHASE_FT_SHORT,
                      PHASE_HEADS_UP, PHASE_WINNER, PHASE_EARLY, PHASE_BUBBLE,
                      PHASE_NEAR_MONEY)


def _snap(**kw):
    return MttRankInfo.from_fields(**kw)


# ---- snapshots reais (hook_mtt_out.txt) ----
def test_ft_real_rank3_8alive_9itm():
    """rank=3 itm=9 total=58 alive=8 reward=14640 → mesa final, no dinheiro."""
    i = _snap(rank=3, itm_player_num=9, total_player_num=58, alive_player_num=8,
              current_reward_ppcoins=14640)
    assert i.at_final_table is True
    assert i.phase == PHASE_FINAL_TABLE
    assert i.itm is True
    assert i.players_to_ft == 0
    assert i.has_reward is True


def test_deep_run_6alive_122total():
    """alive=6 total=122 itm=20 reward=59700 → mesa final (6-handed), bem no dinheiro."""
    i = _snap(rank=0, itm_player_num=20, total_player_num=122, alive_player_num=6,
              current_reward_ppcoins=59700)
    assert i.at_final_table is True
    assert i.phase == PHASE_FINAL_TABLE   # 6 vivos = FT cheia; curta só <=4
    assert i.itm is True


def test_far_from_ft_23alive_8itm():
    """alive=23 itm=8 total=34 → ainda longe/early, fora do dinheiro."""
    i = _snap(rank=7, itm_player_num=8, total_player_num=34, alive_player_num=23)
    assert i.at_final_table is False
    assert i.itm is False
    assert i.players_to_ft == 14
    assert i.players_to_bubble == 15
    assert i.phase in (PHASE_EARLY,)


# ---- fases sintéticas ----
def test_bubble_exact():
    i = _snap(itm_player_num=18, total_player_num=100, alive_player_num=19)
    assert i.on_bubble is True
    assert i.players_to_bubble == 1
    assert i.phase == PHASE_BUBBLE


def test_itm_multitable():
    i = _snap(itm_player_num=18, total_player_num=100, alive_player_num=15)
    assert i.itm is True
    assert i.at_final_table is False
    assert i.phase == PHASE_ITM


def test_near_money():
    i = _snap(itm_player_num=18, total_player_num=100, alive_player_num=20)
    assert i.on_bubble is False
    assert i.phase == PHASE_NEAR_MONEY


def test_heads_up():
    i = _snap(itm_player_num=9, total_player_num=58, alive_player_num=2, rank=1)
    assert i.phase == PHASE_HEADS_UP
    assert i.at_final_table is True


def test_winner():
    i = _snap(itm_player_num=9, total_player_num=58, alive_player_num=1, rank=1)
    assert i.phase == PHASE_WINNER


def test_ft_size_8max():
    """FT 8-max: alive=8 vira final_table só se ft_size=8 (aqui 8<=9 já é FT de qualquer forma)."""
    i = _snap(itm_player_num=8, total_player_num=40, alive_player_num=8, ft_size=8)
    assert i.at_final_table is True
    assert i.players_to_ft == 0


def test_unknown_when_empty():
    i = _snap()
    assert i.phase == 'unknown'
    assert i.players_to_ft is None
    assert i.players_to_bubble is None


def test_summary_renders():
    i = _snap(rank=3, itm_player_num=9, total_player_num=58, alive_player_num=8,
              current_reward_ppcoins=14640)
    s = i.summary()
    assert 'final_table' in s and 'vivos=8' in s and 'premio=14640' in s
