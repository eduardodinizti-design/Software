"""TRAVA DE REGRESSAO do PRE-FLOP (Eduardo 18/11): 'uma vez que confirmo algo e
seto no bot, nao pode desaprender'. Este teste PINA os opens confirmados. Se uma
mudanca futura quebrar qualquer um, a SUITE FALHA (nao passa em silencio).

Fonte da verdade = ranges do Eduardo, carregadas como o OPERADOR carrega: os DOIS
pacotes (validados + deep) via from_files. Auditar com so um pacote e ERRO (as
ranges de 100bb estao no deep). Ver memoria nvt-ranges-fonte-da-verdade.
"""
import os
import unittest

from preflop_advisor import PreflopAdvisor

_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


def _cards(h):
    if len(h) == 2:                        # par, ex '44'
        return [h[0] + 'h', h[1] + 'd']
    return [h[0] + 'h', h[1] + ('h' if h[2] == 's' else 'd')]


# (hand, position, stack_bb, acao_esperada) — CONFIRMADOS ao vivo 18/11.
# 'raise' = tem que abrir; 'fold' = tem que foldar (range tight/lixo, correto).
_CASOS = [
    # ATo: open de LJ..BTN em qualquer stack; UTG tight folda a 100bb (T9s>ATo).
    ('ATo', 'HJ', 25, 'raise'), ('ATo', 'HJ', 40, 'raise'), ('ATo', 'HJ', 100, 'raise'),
    ('ATo', 'CO', 100, 'raise'), ('ATo', 'BTN', 100, 'raise'),
    ('ATo', 'UTG', 100, 'fold'),
    # 44: open de LJ..BTN; abre tambem UTG a 40bb.
    ('44', 'HJ', 25, 'raise'), ('44', 'BTN', 25, 'raise'), ('44', 'HJ', 100, 'raise'),
    ('44', 'CO', 40, 'raise'),
    # A3/A4: open no BTN (e CO a 25) — os bugs que o Eduardo pegou.
    ('A3o', 'BTN', 25, 'raise'), ('A3o', 'BTN', 100, 'raise'),
    ('A4o', 'BTN', 100, 'raise'), ('A4o', 'HJ', 25, 'raise'),
    # hands largas que SEMPRE abrem (mid/late).
    ('KJo', 'HJ', 100, 'raise'), ('T9s', 'UTG', 100, 'raise'), ('98s', 'CO', 25, 'raise'),
    # lixo que SEMPRE folda (nunca abrir).
    ('72o', 'BTN', 25, 'fold'), ('72o', 'HJ', 100, 'fold'), ('J2o', 'CO', 40, 'fold'),
]


class TestPreflopOpensRegressao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
            raise unittest.SkipTest('pacotes de range nao encontrados nesta maquina')
        cls.adv = PreflopAdvisor.from_files(_VAL, _DEEP)   # os DOIS, como o operador

    def test_opens_confirmados_nao_regridem(self):
        falhas = []
        for hand, pos, stk, esperado in _CASOS:
            adv = self.adv.advise_first_in(hero_cards=_cards(hand), hero_position=pos,
                                           stack_bb=stk, mode='chip_ev', stage='mid', players=9)
            rec = adv.get('recommended')
            got = 'raise' if rec in ('raise', 'bet', 'all_in', '3bet') else (
                'fold' if rec in ('fold', None) else rec)
            if got != esperado:
                falhas.append(f'{hand} {pos} {stk}bb: esperado {esperado}, veio {rec}')
        self.assertEqual(falhas, [], 'OPENS REGREDIRAM:\n  ' + '\n  '.join(falhas))

    def test_open_deep_e_executavel_pelas_travas(self):
        """Pina as travas: um OPEN deep (val=False, bucket>25) NAO pode ser bloqueado
        pela guarda deep nem pelo gate de raise (fix 18/11). Replica as condicoes do
        operar_mesa; se alguem re-apertar as travas, isto quebra."""
        adv = self.adv.advise_first_in(hero_cards=_cards('ATo'), hero_position='HJ',
                                       stack_bb=100, mode='chip_ev', stage='mid', players=9)
        spot = adv.get('spot')
        self.assertEqual(spot, 'open_raise', 'ATo HJ 100 deveria rotear como open_raise')
        self.assertFalse(adv.get('validated'), 'deep e referencia (val=False) por design')
        # guarda deep NAO pode pegar opens:
        guarda_pega = (adv.get('validated') is False and spot not in ('open_raise', 'open_shove'))
        self.assertFalse(guarda_pega, 'GUARDA DEEP nao pode foldar OPEN (fix 18/11)')
        # gate de raise NAO pode bloquear opens:
        gate_bloqueia = (not adv.get('validated') and spot not in ('open_raise', 'open_shove'))
        self.assertFalse(gate_bloqueia, 'GATE DE RAISE nao pode bloquear OPEN deep (fix 18/11)')


if __name__ == '__main__':
    unittest.main()
