"""HERO-CALL de river vs campo que SOBRE-blefa (Eduardo 24/11): "river bem protegido e ser herói em
determinados runouts". No CAMPO MOLE (play money ruim, sobre-blefa) o top pair PAGA a aposta grande
de river (não over-folda) e, em RUNOUT DE BLEFE (flush-draw do turn MORREU), paga até um overbet
moderado. CAMPO DURO (FT/ICM, pool underbluffa o river) -> fold seguro. Teto anti-callstation: jam
gigante folda sempre. Underpair NUNCA é herói (leak de 50k, H2N #61)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from postflop_advisor import advise_postflop


def _st(pot, to_call, stack=80):
    return dict(positions={'hero': 'BB', 'v': 'BTN'},
                seats={'hero': {'stack_bb': stack, 'occupied': True},
                       'v': {'stack_bb': stack, 'occupied': True}},
                bets=[{'seat': 'v', 'bet_bb': to_call}], to_call={'to_call_bb': to_call},
                pot={'pot_bb': pot}, phase='mid')


def _rec(cards, board, to_call, soft):
    r = advise_postflop(_st(12.0, to_call), cards, board, street='RIVER', aggressor='BTN',
                        pot_type='single_raised', soft_field=soft)
    return r.get('recommended')


# MISS: turn As-9h-4c-Kd era two-tone (2 copas: 9h + ... ), river 2s não fechou = flush-draw MORTO.
MISS = ['Ah', '9h', '4c', 'Kd', '2s']     # 2 copas no turn (Ah,9h) bricaram
DRY = ['As', '9d', '4c', 'Kh', '2s']       # turn rainbow (4 naipes) = sem flush-draw vivo
AQ = ['Ad', 'Qc']                          # top pair de ás
UNDER = ['7s', '7d']                       # underpair (overcards A,K no board)

POT_BET = 8.0     # ~2/3 pote = barril normal (pot_odds 0.40)
OVERBET = 16.0    # overbet / aposta grande de river (pot_odds ~0.57)
JAM = 30.0        # jam gigante (pot_odds ~0.71) — acima do teto do herói


# ---- top pair: river bem PROTEGIDO no campo mole ----
def test_top_pair_paga_barril_normal_ambos_campos():
    assert _rec(AQ, MISS, POT_BET, soft=True) == 'call'
    assert _rec(AQ, MISS, POT_BET, soft=False) == 'call'


def test_top_pair_heroi_overbet_runout_blefe_campo_mole():
    # flush-draw morto + campo mole -> HERÓI paga o overbet
    assert _rec(AQ, MISS, OVERBET, soft=True) == 'call'


def test_top_pair_nao_heroi_overbet_board_seco():
    # turn rainbow (sem draw p/ morrer) -> NÃO paga overbet nem no campo mole (sem spew)
    assert _rec(AQ, DRY, OVERBET, soft=True) == 'fold'


def test_top_pair_campo_duro_folda_overbet_river():
    # campo duro (pool underbluffa o river) -> folda overbet mesmo em runout de blefe
    assert _rec(AQ, MISS, OVERBET, soft=False) == 'fold'


def test_top_pair_folda_jam_gigante_mesmo_heroi():
    # teto anti-callstation: jam 2x+ pote folda mesmo no campo mole + runout de blefe
    assert _rec(AQ, MISS, JAM, soft=True) == 'fold'


# ---- underpair: NUNCA é herói (protege o leak de 50k) ----
def test_underpair_nunca_heroi_campo_mole():
    assert _rec(UNDER, MISS, OVERBET, soft=True) == 'fold'
    assert _rec(UNDER, MISS, POT_BET, soft=True) == 'fold'


# ---- CHECK-RAISE DE BLEFE NO RIVER (nut-blocker, campo duro) ----
FLUSH = ['9h', '4h', '2h', 'Kd', '7s']     # 3 copas = flush FEITO no board
BLOCKER = ['Ah', 'Qd']                     # AR que segura o Ás de copas (bloqueia a nut flush)
NO_BLOCKER = ['Ac', 'Qd']                  # AR sem o Ás de copas (não representa nada)
BLUFFCATCH = ['Ks', 'Qd']                  # par de K = bluff-catcher (deve PAGAR, não blefar)


def test_checkraise_bluff_river_nut_blocker_campo_duro():
    r = advise_postflop(_st(12.0, 8.0), BLOCKER, FLUSH, street='RIVER', aggressor='BTN',
                        soft_field=False)
    assert r.get('recommended') == 'raise'
    assert 'CHECK_RAISE_BLUFF_RIVER_NUT_BLOCKER_CAMPO_DURO' in r.get('caveats', [])


def test_checkraise_bluff_river_nao_campo_mole():
    # campo mole (station paga o raise) -> não blefa-raise
    assert advise_postflop(_st(12.0, 8.0), BLOCKER, FLUSH, street='RIVER', aggressor='BTN',
                           soft_field=True).get('recommended') != 'raise'


def test_checkraise_bluff_river_exige_blocker():
    # sem o Ás de copas não representa a nut -> NÃO blefa (sem spew)
    assert advise_postflop(_st(12.0, 8.0), NO_BLOCKER, FLUSH, street='RIVER', aggressor='BTN',
                           soft_field=False).get('recommended') != 'raise'


def test_bluffcatcher_nao_vira_checkraise_bluff():
    # par (bluff-catcher) PAGA, nunca vira blefe de check-raise
    assert advise_postflop(_st(12.0, 8.0), BLUFFCATCH, FLUSH, street='RIVER', aggressor='BTN',
                           soft_field=False).get('recommended') == 'call'


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
