"""SQUEEZE escala por nº de CALLERS (Eduardo 24/11): o 3bet sobre open + caller(es) infla +1
open por caller (dinheiro morto). 3bet normal (0 caller) inalterado (3x IP / 4x OOP)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import sizing
import auditar_cobertura_preflop as aud


def _sz(state, hero, opener):
    return sizing.size_from_reading('three_bet', state, hero, opener)['size_bb']


def test_3bet_normal_inalterado():
    assert _sz(aud.st_vs_open('BTN', 'UTG', 40), 'BTN', 'UTG') == 6.0   # 3x IP
    assert _sz(aud.st_vs_open('SB', 'UTG', 40), 'SB', 'UTG') == 8.0     # 4x OOP


def test_squeeze_infla_por_caller_ip():
    assert _sz(aud.st_squeeze('BTN', 'UTG', 'CO', 40), 'BTN', 'UTG') == 8.0            # 4x (1 caller)
    assert _sz(aud.st_squeeze2('BTN', 'UTG', 'LJ', 'HJ', 40), 'BTN', 'UTG') == 10.0    # 5x (2 callers)


def test_squeeze_infla_por_caller_oop():
    assert _sz(aud.st_squeeze('SB', 'UTG', 'CO', 40), 'SB', 'UTG') == 10.0             # 5x (1 caller)


def test_squeeze_cresce_com_jogadores():
    ip0 = _sz(aud.st_vs_open('BTN', 'UTG', 40), 'BTN', 'UTG')
    ip1 = _sz(aud.st_squeeze('BTN', 'UTG', 'CO', 40), 'BTN', 'UTG')
    ip2 = _sz(aud.st_squeeze2('BTN', 'UTG', 'LJ', 'HJ', 40), 'BTN', 'UTG')
    assert ip0 < ip1 < ip2      # monotônico: mais callers = maior squeeze


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n](); print('OK', n)
    print('TODOS PASSARAM')
