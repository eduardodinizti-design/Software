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

    # --- BB iso sobre LIMPERS: executavel via referencia BTN (corrige AQ/AA nao-clicando) ---
    def test_bb_iso_sobre_limpers_executavel(self):
        st = {'positions': {'s0': 'HJ', 's1': 'CO', 's2': 'UTG+1', 's3': 'SB', 'hero': 'BB'},
              'seats': {k: {'stack_bb': 25, 'occupied': True} for k in ('s0', 's1', 's2', 's3', 'hero')},
              'bets': [{'seat': 's0', 'bet_bb': 1.0}, {'seat': 's1', 'bet_bb': 1.0},
                       {'seat': 's2', 'bet_bb': 1.0}, {'seat': 's3', 'bet_bb': 0.5},
                       {'seat': 'hero', 'bet_bb': 1.0}],
              'to_call': {'to_call_bb': None}, 'pot': {'pot_bb': 4.5}}
        aq = self.adv.advise_from_reading(st, ['Ad', 'Qc'], mode='chip_ev', stage='mid')
        self.assertEqual(aq.get('recommended'), 'raise')
        self.assertFalse(any('GAP_APROX' in c for c in (aq.get('caveats') or [])))  # tem nó
        self.assertTrue(any('ISO_REF_BTN' in c for c in (aq.get('caveats') or [])))
        trash = self.adv.advise_from_reading(st, ['7d', '2c'], mode='chip_ev', stage='mid')
        self.assertEqual(trash.get('recommended'), 'check')   # BB foldar grátis -> check

    # --- vs_3bet alcancavel (deep usa o no; curto cai no call-off) ---
    def test_vs_3bet_reachable_deep(self):
        r = self._spot(aud.st_vs_3bet('CO', 'BTN', 25))
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertIn(r.get('spot'), ('vs_3bet',) )

    # --- FALLBACK DE SPREAD (fecha os 63 gaps vs_3bet pko_icm/curtos_fim @40bb, 20/11):
    #     sem no no spread especifico, reusa o 'iguais' do MESMO modo/stage/bucket como
    #     REFERENCIA executavel (node_id setado). So p/ spots nao-shove. ---
    def test_spread_fallback_vs_3bet_executavel(self):
        deep = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
        if not os.path.exists(deep):
            self.skipTest('pack deep ausente')
        adv = PreflopAdvisor.from_files(PACK, deep)   # Henrique AO VIVO usa os dois
        st = aud.st_vs_3bet('BTN', 'SB', 40, 'curtos_fim')
        r = adv.advise_from_reading(st, ['Ad', 'Ac'], mode='pko_icm', stage='bubble',
                                    bounty_bb=10.0)
        self.assertEqual(r.get('status'), 'ADVICE')
        self.assertTrue(r.get('node_id'))                                   # tem NO -> executavel
        self.assertFalse(r.get('validated'))                                # mas e aproximacao
        self.assertTrue(any('SPREAD_REF_IGUAIS' in c for c in (r.get('caveats') or [])))


class FacingAllInRobusto(unittest.TestCase):
    """Detecção de facing-all-in que NÃO depende de ler o stack do abridor (que falhou ao
    vivo e fez o KK vs 3bet-shove virar four_bet). Unit test — não precisa do pack."""

    def test_shove_pelo_stack_do_hero(self):
        from preflop_advisor import _opener_is_shove
        # BTN aposta 127.5bb; stack ATRÁS do BTN lido GRANDE (50bb, não ~0) -> check antigo falha.
        # Hero tem 100bb -> não dá p/ raisar (127.5 >= 100) -> facing-all-in via stack do hero.
        st = {'positions': {'s_btn': 'BTN', 'hero': 'LJ'},
              'seats': {'s_btn': {'stack_bb': 50.0}, 'hero': {'stack_bb': 100.0}}}
        self.assertTrue(_opener_is_shove(st, 'BTN', 127.5))

    def test_3bet_normal_nao_e_shove(self):
        from preflop_advisor import _opener_is_shove
        # 3bet normal de 11bb com hero 100bb e BTN com stack atrás -> NÃO é shove.
        st = {'positions': {'s_btn': 'BTN', 'hero': 'LJ'},
              'seats': {'s_btn': {'stack_bb': 89.0}, 'hero': {'stack_bb': 100.0}}}
        self.assertFalse(_opener_is_shove(st, 'BTN', 11.0))

    def test_stack_do_abridor_zero_ainda_detecta(self):
        from preflop_advisor import _opener_is_shove
        # comportamento original preservado: stack atrás do abridor ~0 -> shove.
        st = {'positions': {'s_btn': 'BTN', 'hero': 'LJ'},
              'seats': {'s_btn': {'stack_bb': 0.3}, 'hero': {'stack_bb': 100.0}}}
        self.assertTrue(_opener_is_shove(st, 'BTN', 12.0))


class DeriveToCall(unittest.TestCase):
    """to_call=None do OCR -> deriva dos bets (evita o 0.0 enganoso facing-a-bet)."""

    def test_facing_raise_deriva(self):
        from preflop_advisor import PreflopAdvisor
        st = {'bets': [{'seat': 's0', 'bet_bb': 9.0}, {'seat': 'hero', 'bet_bb': 1.0}],
              'to_call': {'to_call_bb': None}}
        out = PreflopAdvisor._derive_to_call(st)
        self.assertEqual(out['to_call']['to_call_bb'], 8.0)
        self.assertTrue(out['to_call']['derived'])

    def test_limped_deriva_zero(self):
        from preflop_advisor import PreflopAdvisor
        st = {'bets': [{'seat': 's0', 'bet_bb': 1.0}, {'seat': 'hero', 'bet_bb': 1.0}],
              'to_call': {'to_call_bb': None}}
        self.assertEqual(PreflopAdvisor._derive_to_call(st)['to_call']['to_call_bb'], 0.0)

    def test_leitura_real_intocada(self):
        from preflop_advisor import PreflopAdvisor
        st = {'bets': [{'seat': 's0', 'bet_bb': 9.0}], 'to_call': {'to_call_bb': 8.0}}
        out = PreflopAdvisor._derive_to_call(st)
        self.assertEqual(out['to_call']['to_call_bb'], 8.0)
        self.assertNotIn('derived', out['to_call'])


if __name__ == '__main__':
    unittest.main()
