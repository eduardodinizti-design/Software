"""TRAVA DE ROTEAMENTO PRE-FLOP (robustez): bloqueia regressoes que ESTRANDARIAM
ranges validadas ou re-introduziriam o risco de usar range de 3bet-JAM para PAGAR
um all-in. Roda advise_from_reading (o MESMO caminho ao vivo) contra o pack real e
exige que cada spot seja alcancado no bucket certo. Pula se o pack real nao existe."""
import os
import unittest

import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'


def _facing_allin(hero, opener, bucket, spread='iguais'):
    """Mesa com o abridor ALL-IN (stack atras ~0) — facing-jam real."""
    st = aud._table(hero, bucket, spread, [(opener, bucket)])
    st['seats'][opener]['stack_bb'] = 0.3
    st['to_call'] = {'to_call_bb': bucket}
    st['pot'] = {'pot_bb': bucket + 1.5}
    return st


@unittest.skipUnless(os.path.exists(PACK), 'pack validado real ausente')
class Roteamento(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adv = PreflopAdvisor.from_file(PACK)

    def _spot(self, state, mode='chip_ev', stage='mid', **kw):
        r = self.adv.advise_from_reading(state, ['Ad', 'Ac'], mode=mode, stage=stage, **kw)
        return r

    # --- fronteira de regime: first-in ---
    def test_first_in_shove_zone_jams(self):
        r = self._spot(aud.st_first_in('BTN', 10))
        self.assertEqual(r['spot'], 'open_shove')

    def test_first_in_deep_opens(self):
        r = self._spot(aud.st_first_in('BTN', 30))
        self.assertEqual(r['spot'], 'open_raise')

    # --- fronteira de regime: enfrentando um OPEN (nao all-in) ---
    def test_vs_open_shove_zone_3bet_jams(self):
        r = self._spot(aud.st_vs_open('BB', 'BTN', 12))
        self.assertEqual(r['spot'], '3bet_shove')

    def test_vs_open_deep_flats_or_3bets(self):
        r = self._spot(aud.st_vs_open('BB', 'BTN', 30))
        self.assertEqual(r['spot'], 'vs_open')

    # --- INVARIANTE DE SEGURANCA (dinheiro): enfrentando um ALL-IN, NAO usar a range
    #     de 3bet-JAM (jam com fold equity pagaria largo demais). Tem que ser call-off
    #     por equity (ou o no vs_open_shove), sempre com decisao EXECUTAVEL. ---
    def test_facing_allin_uses_calloff_not_jam_range(self):
        for mode, stage in [('chip_ev', 'mid'), ('icm', 'bubble'), ('pko_icm', 'bubble')]:
            for stk in (12, 20):
                kw = {'bounty_bb': 10.0} if mode in ('pko', 'pko_icm') else {}
                r = self._spot(_facing_allin('BB', 'BTN', stk), mode=mode, stage=stage, **kw)
                self.assertEqual(r.get('status'), 'ADVICE',
                                 '%s %dbb facing all-in abstido' % (mode, stk))
                self.assertIn(r.get('spot'), ('vs_open_shove', 'call_off_vs_open_shove'),
                              '%s %dbb facing all-in roteou para %s (nao pode ser jam-range)'
                              % (mode, stk, r.get('spot')))
                self.assertNotEqual(r.get('spot'), '3bet_shove')

    # --- squeeze 20-25bb usa 3bet_shove (resteal/jam) ---
    def test_squeeze_2025_3bet_jams(self):
        r = self._spot(aud.st_squeeze('SB', 'BTN', 'CO', 22))
        self.assertEqual(r['spot'], '3bet_shove')

    # --- vs_3bet alcancavel (deep usa o no; curto cai no call-off) ---
    def test_vs_3bet_reachable_deep(self):
        r = self._spot(aud.st_vs_3bet('CO', 'BTN', 25))
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('spot'), ('vs_3bet',) )


if __name__ == '__main__':
    unittest.main()
