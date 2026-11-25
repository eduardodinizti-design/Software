"""TRAVA FIM-A-FIM do SIZE de open/iso pelo ADVISOR (achado pos-mortem #4, 25/11).

No log da sessao viva dois opens first-in sairam [3X] (preset snapado pelo executor):
  UTG+2 ['Ah','Js'] to_call=1.0bb  -> raise [3X]
  BB    ['Ah','9s'] to_call=0.0bb  -> raise [3X]
Investigacao: NAO era bug. O size final que o executor consome vem de
`sizing.size_from_reading` (preflop_advisor.advise_from_reading, override no fim do
`advise`). Os dois casos sao ISO LEGITIMO sobre 1 limper / complete do SB = 2X + 1bb =
3X (regra Eduardo 23/11). test_open_size_regressao.py ja pina isso no nivel de
sizing.py; AQUI pinamos o caminho REAL do advisor (advise_from_reading), que e o que
o executor usa, para garantir que:
  - first-in LIMPO (sem limper) continua 2X (LEI open=2x INTACTA);
  - iso com N limpers = 2X + N (cap 4X);
  - os dois opens [3X] da sessao reproduzem como iso legitimo, nao como open limpo.
Se alguem quebrar a LEI (open limpo saindo 3X) ou o iso (N errado), a SUITE FALHA.
"""
import os
import unittest

import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor, infer_live_spot

_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'


class TestPreflopIsoSizeE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
            raise unittest.SkipTest('pacotes de range nao encontrados nesta maquina')
        cls.adv = PreflopAdvisor.from_files(_VAL, _DEEP)   # os DOIS, como o operador

    def _advise(self, st, cards):
        return self.adv.advise_from_reading(st, cards, mode='chip_ev', stage='mid')

    # ---- LEI open=2x: first-in LIMPO (sem limper) SEMPRE 2X pelo advisor --------------
    def test_first_in_limpo_e_2x(self):
        # stacks DEEP (>=20bb) p/ o iso/open ficar RAISE e nao virar shove da zona curta.
        casos = [('ATo', 'BTN', 40), ('AJo', 'CO', 40), ('AJo', 'UTG+2', 40),
                 ('99', 'HJ', 40), ('ATo', 'BTN', 100)]
        falhas = []
        for hand, pos, stk in casos:
            st = aud.st_first_in(pos, stk)
            r = self._advise(st, self._cards(hand))
            if r.get('recommended') != 'raise':
                falhas.append(f'{hand} {pos} {stk}bb: esperava raise, veio {r.get("recommended")}')
                continue
            sz = (r.get('sizing') or {}).get('size_bb')
            if sz != 2.0:
                falhas.append(f'{hand} {pos} {stk}bb LIMPO: esperava 2.0bb (2X), veio {sz}')
        self.assertEqual(falhas, [], 'LEI open=2x QUEBROU no advisor:\n  ' + '\n  '.join(falhas))

    # ---- ISO = 2X + 1bb/limper (cap 4X) pelo advisor ---------------------------------
    def test_iso_n_limpers_infla_corretamente(self):
        # UTG+2 AJo, deep 40bb, N limpers antes -> 2X + N (cap 4X).
        esperado = {0: 2.0, 1: 3.0, 2: 4.0, 3: 4.0}
        limpers_por_n = {0: [], 1: ['UTG'], 2: ['UTG', 'UTG+1'], 3: ['LJ', 'UTG', 'UTG+1']}
        falhas = []
        for n, exp in esperado.items():
            st = aud._table_vs_limpers('UTG+2', 40, limpers_por_n[n])
            r = self._advise(st, self._cards('AJo'))
            if r.get('recommended') != 'raise':
                falhas.append(f'{n} limper(s): esperava raise, veio {r.get("recommended")}')
                continue
            sz = (r.get('sizing') or {}).get('size_bb')
            if sz != exp:
                falhas.append(f'{n} limper(s): esperava {exp}bb, veio {sz}')
        self.assertEqual(falhas, [], 'ISO vs limpers com size errado:\n  ' + '\n  '.join(falhas))

    # ---- Reproducao EXATA dos dois opens [3X] da sessao (nao-bug) ---------------------
    def test_sessao_ajo_utg2_3x_e_iso_de_1_limper(self):
        # [3X] da sessao = iso legitimo sobre 1 limper (NAO open limpo). Open limpo = 2X.
        st_limp = aud._table_vs_limpers('UTG+2', 40, ['UTG'])
        self.assertEqual(infer_live_spot(st_limp).get('limpers'), 1)
        r = self._advise(st_limp, self._cards('AJo'))
        self.assertEqual(r.get('recommended'), 'raise')
        self.assertEqual((r.get('sizing') or {}).get('size_bb'), 3.0)   # 2X + 1bb = 3X iso

        st_clean = aud.st_first_in('UTG+2', 40)
        r2 = self._advise(st_clean, self._cards('AJo'))
        self.assertEqual((r2.get('sizing') or {}).get('size_bb'), 2.0)  # LIMPO = 2X (lei)

    def test_sessao_a9s_bb_vs_sb_complete_3x(self):
        # BB com to_call=0 (opcao) e SB que COMPLETOU -> iso do complete = 1 limper = 3X.
        st = aud.st_vs_limp(40)                 # SB posta 1.0 (completou)
        st['to_call'] = dict(to_call_bb=0.0)    # BB tem opcao (checked-to)
        r = self._advise(st, self._cards('A9s'))
        if r.get('recommended') == 'raise':
            self.assertEqual((r.get('sizing') or {}).get('size_bb'), 3.0,
                             'BB isolando complete do SB tem que ser 3X (Eduardo 23/11)')

    @staticmethod
    def _cards(h):
        if len(h) == 2:                        # par, ex '99'
            return [h[0] + 'h', h[1] + 'd']
        return [h[0] + 'h', h[1] + ('h' if h[2] == 's' else 'd')]


if __name__ == '__main__':
    unittest.main()
