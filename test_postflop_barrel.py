"""BARRIL DE OVERCARD gated por CAMPO (guia Reg-Life cap.8 + Eduardo 24/11): em turn que é
OVERCARD (muda o board, favorece o agressor), ar/overcards BARRILA como blefe NO CAMPO DURO
(FT/ICM, fold equity); no CAMPO MOLE (station) DESISTE (sem spew). Draw forte segue o
semi-blefe; valor forte já apostou. Não barrila vs vilão passivo."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from postflop_advisor import advise_postflop

BOARD = ['9h', '6d', '2c', 'Ks']   # turn Ks = overcard ao flop 9-6-2
AR = ['Qd', 'Jc']                  # ar COM equidade (gutshot ao T) — o barril de overcard quer equidade
PASSIVE = {'vpip': 55, 'pfr': 8, 'cbet': 20, 'foldcbet': 25, 'threebet': 1, 'fold3bet': 80, 'steal': 10, 'cr': 2}


def _st():
    return dict(positions={'hero': 'BTN', 'v': 'BB'},
                seats={'hero': {'stack_bb': 40, 'occupied': True}, 'v': {'stack_bb': 40, 'occupied': True}},
                bets=[], to_call={'to_call_bb': 0.0}, pot={'pot_bb': 6.0}, phase='mid')


def _rec(soft, stats=None):
    r = advise_postflop(_st(), AR, BOARD, street='TURN', aggressor='hero',
                        pot_type='single_raised', soft_field=soft, villain_stats=stats)
    return r.get('recommended')


def test_overcard_barrel_campo_duro_aposta():
    assert _rec(soft=False) == 'bet'


def test_overcard_barrel_campo_mole_desiste():
    assert _rec(soft=True) == 'check'


def test_overcard_barrel_nao_vs_passivo():
    # campo duro MAS vilão passivo/station -> ar desiste (barril de blefe não lucra)
    assert _rec(soft=False, stats=PASSIVE) == 'check'


# ---- #1 3º BARRIL DE RIVER (blefe sem showdown, gated por campo) ----
def _river(cards, board, soft=False, stats=None):
    r = advise_postflop(_st(), cards, board, street='RIVER', aggressor='hero',
                        pot_type='single_raised', soft_field=soft, villain_stats=stats)
    return r.get('recommended')


RIVER_SECO = ['Ac', '9d', '4s', 'Kh', '2c']   # sem sequência no board


def test_river_3barril_campo_duro_blefa():
    assert _river(['Qs', 'Jd'], RIVER_SECO, soft=False) == 'bet'       # QJ ar -> blefa


def test_river_3barril_campo_mole_desiste():
    assert _river(['Qs', 'Jd'], RIVER_SECO, soft=True) == 'check'


def test_river_3barril_nao_vs_passivo():
    assert _river(['Qs', 'Jd'], RIVER_SECO, soft=False, stats=PASSIVE) == 'check'


# ---- #3 VALOR FINO DE RIVER (extrai valor; NÃO blefe) ----
def test_river_valor_fino_top_pair_aposta():
    assert _river(['Ad', 'Qc'], ['As', '7d', '3h', '9c', '2s']) == 'bet'   # top pair seco


def test_river_valor_fino_nao_aposta_2o_par_dominado():
    # 2º par em A-alto: perde pro range que paga -> CHECA (não é valor fino)
    assert _river(['Ks', '9d'], ['Ac', '9h', '4s', '2c', '7d']) == 'check'


# ---- #5 BLEFE DE RIVER em BOARD PAREADO (joga o board, sem showdown) ----
PAIRED = ['Ks', 'Kd', '7c', '4h', '2s']   # K pareado; QJ = board_pair_only (hero não pareou)


def test_river_bluff_board_pareado_campo_duro():
    assert _river(['Qh', 'Jd'], PAIRED, soft=False) == 'bet'


def test_river_bluff_board_pareado_campo_mole_desiste():
    assert _river(['Qh', 'Jd'], PAIRED, soft=True) == 'check'


def test_river_bluff_board_pareado_nao_vs_passivo():
    assert _river(['Qh', 'Jd'], PAIRED, soft=False, stats=PASSIVE) == 'check'


# ---- #6 CHECK-RAISE POR BLEFE (defensor, draw fraco + fold equity) ----
def _facing(cards, board, pos_hero='BB', aggr='BTN', to_call=3.0, pot=6.0, soft=False, stats=None):
    s = dict(positions={'hero': pos_hero, 'v': aggr},
             seats={'hero': {'stack_bb': 40, 'occupied': True}, 'v': {'stack_bb': 40, 'occupied': True}},
             bets=[{'seat': 'v', 'bet_bb': to_call}], to_call={'to_call_bb': to_call},
             pot={'pot_bb': pot}, phase='mid')
    r = advise_postflop(s, cards, board, street='FLOP', aggressor=aggr,
                        pot_type='single_raised', soft_field=soft, villain_stats=stats)
    return r.get('recommended')


LOWCON = ['6c', '5d', '2s']   # baixo conectado = vantagem de nuts do defensor


def test_checkraise_bluff_campo_duro():
    assert _facing(['9h', '8h'], LOWCON, soft=False) == 'raise'       # gutshot (7)


def test_checkraise_bluff_campo_mole_nao_raise():
    assert _facing(['9h', '8h'], LOWCON, soft=True) != 'raise'


def test_checkraise_bluff_nao_vs_passivo():
    assert _facing(['9h', '8h'], LOWCON, soft=False, stats=PASSIVE) != 'raise'


# ---- #7 FLOAT (IP, overcards, campo duro) ----
def test_float_ip_campo_duro_paga():
    assert _facing(['Ah', 'Kd'], ['7c', '5d', '2s'], pos_hero='BTN', aggr='CO',
                   to_call=2.0, soft=False) == 'call'


def test_float_campo_mole_folda():
    assert _facing(['Ah', 'Kd'], ['7c', '5d', '2s'], pos_hero='BTN', aggr='CO',
                   to_call=2.0, soft=True) == 'fold'


def test_float_oop_nao_floata():
    assert _facing(['Ah', 'Kd'], ['7c', '5d', '2s'], pos_hero='SB', aggr='CO',
                   to_call=2.0, soft=False) == 'fold'


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n](); print('OK', n)
    print('TODOS PASSARAM')
