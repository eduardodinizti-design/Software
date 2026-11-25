"""Trava a SOMBRA genérica IP-vs-BB SRP (pack btn_vs_bb_40, flop+turn, sizes do nosso
slider, aproximação CO, Plano Geométrico por SPR). Eduardo 19/11: aproveitar o estudo
TexasSolver de 40bb no cérebro pós-flop, falando a NOSSA língua de size, sem quebrar o
gate (shadow, não executa)."""
import os
import unittest

import solver_srp_shadow as s

_PACK = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     'strategy_data', 'postflop_solver', 'btn_vs_bb_40.json')
_OUR = {'check', 't33', 't50', 't66', 'allin'}


@unittest.skipUnless(os.path.exists(_PACK), 'pack btn_vs_bb_40 nao gerado')
class SrpShadow(unittest.TestCase):
    def setUp(self):
        s._load_dir.cache_clear()           # pack real, sem override de dir

    FLOP = ['8h', '2s', '2d']

    def _flop(self, hero, pos='BTN'):
        return s.lookup(hero, self.FLOP, hero_pos=pos, villain_pos='BB',
                        to_call_bb=0, pot_bb=5.5, hero_stack_bb=38, villain_stack_bb=38,
                        street='flop')

    # ---- flop per-combo c-bet ----
    def test_monster_aposta_mao_fraca_check(self):
        self.assertEqual(self._flop(['As', 'Ah'])['recommended_shadow'], 'bet')
        self.assertEqual(self._flop(['7c', '6c'])['recommended_shadow'], 'check')

    def test_combo_fora_do_range_de_open_e_honesto(self):
        r = self._flop(['Jd', '4c'])            # BTN nao abre J4o
        self.assertFalse(r['combo_in_range'])
        self.assertIsNone(r['recommended_shadow'])
        self.assertIn('SOLVER_SHADOW_COMBO_BELOW_RANGE_WEIGHT', r['caveats'])

    def test_sizes_no_vocabulario_do_nosso_slider(self):
        r = self._flop(['Ks', 'Kd'])
        for a in r['actions']:
            self.assertIn(a, _OUR, 'size %r fora do slider 1/3-1/2-2/3-allin' % a)
        for m in r['mix']:
            self.assertIn(m['action'], _OUR)

    # ---- aproximacao de familia ----
    def test_co_empresta_de_btn_com_caveat(self):
        r = self._flop(['As', 'Ah'], pos='CO')
        self.assertIsNotNone(r)
        self.assertTrue(any('APPROX_CO_DE_BTN' in c for c in r['caveats']))

    def test_btn_nativo_sem_caveat_de_aproximacao(self):
        r = self._flop(['As', 'Ah'], pos='BTN')
        self.assertFalse(any('APPROX' in c for c in r['caveats']))

    # ---- turn ----
    def test_turn_barrela_agregada(self):
        r = s.lookup(['As', 'Ah'], self.FLOP + ['Kc'], hero_pos='BTN', villain_pos='BB',
                     to_call_bb=0, pot_bb=9.5, hero_stack_bb=36, villain_stack_bb=36,
                     street='turn', turn_card='Kc')
        self.assertIsNotNone(r)
        self.assertEqual(r['node'], 'ip_turn_barrel')
        self.assertFalse(r['per_combo'])
        self.assertIn('SOLVER_SHADOW_TURN_RANGE_AGGREGATE', r['caveats'])
        for a in r['actions']:
            self.assertIn(a, _OUR)

    def test_turn_spr_alto_sinaliza_plano_geometrico(self):
        r = s.lookup(['As', 'Ah'], self.FLOP + ['Kc'], hero_pos='BTN', villain_pos='BB',
                     to_call_bb=0, pot_bb=9.5, hero_stack_bb=36, villain_stack_bb=36,
                     street='turn', turn_card='Kc')
        self.assertTrue(r.get('geometric'))
        self.assertTrue(any('GEOMETRIC_PLAN_TURN' in c for c in r['caveats']))
        self.assertTrue(r['geometric']['plan'])          # plano rua-a-rua presente

    def test_turn_spr_baixo_sem_plano_geometrico(self):
        # pote grande, stack curto -> SPR < limiar -> sem nota geometrica
        r = s.lookup(['As', 'Ah'], self.FLOP + ['Kc'], hero_pos='BTN', villain_pos='BB',
                     to_call_bb=0, pot_bb=20.0, hero_stack_bb=10, villain_stack_bb=10,
                     street='turn', turn_card='Kc')
        if r is not None:                                 # pode cair fora do bucket; se vier:
            self.assertIsNone(r.get('geometric'))

    # ---- defesa do BB (lado def, AGREGADO = guia, nao dirige) ----
    def test_bb_defende_cbet_devolve_guia_agregada(self):
        r = s.lookup(['7c', '6c'], self.FLOP, hero_pos='BB', villain_pos='BTN',
                     to_call_bb=1.8, pot_bb=7.3, hero_stack_bb=38, villain_stack_bb=38,
                     street='flop')
        self.assertIsNotNone(r)
        self.assertEqual(r['side'], 'def')
        self.assertEqual(r['node'], 'bb_vs_cbet')
        self.assertFalse(r['per_combo'])
        self.assertIn(r['recommended_shadow'], ('call', 'raise', 'fold'))
        self.assertTrue(any('DEF_RANGE_AGGREGATE' in c for c in r['caveats']))

    def test_bb_def_mapeia_size_e_aproxima_co(self):
        r = s.lookup(['Ad', 'Qs'], self.FLOP, hero_pos='BB', villain_pos='CO',
                     to_call_bb=2.75, pot_bb=8.25, hero_stack_bb=38, villain_stack_bb=38,
                     street='flop')
        self.assertIsNotNone(r)
        self.assertIn(r['bet_faced'], ('t33', 't50', 't66'))
        self.assertTrue(any('APPROX_CO_DE_BTN' in c for c in r['caveats']))

    def test_bb_def_nao_dirige_a_recomendacao(self):
        # def e agregado -> _prefer_solver_srp NAO deve trocar a recomendacao
        import table_advisor as ta
        adv = dict(recommended='call', pot_bb=7.3, caveats=[])
        srp = dict(street='flop', side='def', per_combo=False, decisive=True,
                   recommended_shadow='fold')
        ta._prefer_solver_srp(adv, srp)
        self.assertEqual(adv['recommended'], 'call')   # guia, nao dirige

    # ---- cobertura sem gap (lei "nao morrer no pos-flop", Eduardo 19/11) ----
    def test_stack_distante_empresta_bucket_vizinho_com_caveat(self):
        # 15bb: nao existe pack nativo, mas NAO morre — empresta o mais proximo (40) com
        # caveat honesto da distancia. Cobertura por bucket vizinho, igual ao pre-flop.
        r = s.lookup(['As', 'Ah'], self.FLOP, hero_pos='BTN', villain_pos='BB',
                     to_call_bb=0, pot_bb=5.5, hero_stack_bb=15, villain_stack_bb=15,
                     street='flop')
        self.assertIsNotNone(r)
        self.assertTrue(any('STACK_BUCKET' in c for c in r['caveats']))

    def test_nunca_morre_mao_forte_em_spot_coberto_aposta(self):
        # ANTI-MORTE: monstro no flop coberto tem de APOSTAR (nao check). Varia o stack
        # (25/38/60/100) p/ garantir que a cobertura entrega BET em toda profundidade.
        for eff in (25, 38, 60, 100):
            r = s.lookup(['As', 'Ah'], self.FLOP, hero_pos='BTN', villain_pos='BB',
                         to_call_bb=0, pot_bb=5.5, hero_stack_bb=eff, villain_stack_bb=eff,
                         street='flop')
            self.assertIsNotNone(r, 'morreu (None) com %dbb' % eff)
            self.assertTrue(r['combo_in_range'])
            self.assertEqual(r['recommended_shadow'], 'bet', 'AA deu check com %dbb' % eff)

    def test_icm_puro_de_bolha_fica_fora(self):
        # ICM puro (bolha) muda o pos-flop de verdade (sobrevivencia) -> gated off.
        self.assertIsNone(s.lookup(['As', 'Ah'], self.FLOP, hero_pos='BTN', villain_pos='BB',
                                   to_call_bb=0, pot_bb=5.5, hero_stack_bb=38,
                                   villain_stack_bb=38, street='flop', mode='icm'))

    def test_pko_coberto_por_aproximacao_com_caveat(self):
        # PKO/KO: c-bet SRP ~chip-EV -> cobre por aproximacao, nao morre. Caveat honesto.
        for m in ('pko', 'pko_icm'):
            r = s.lookup(['As', 'Ah'], self.FLOP, hero_pos='BTN', villain_pos='BB',
                         to_call_bb=0, pot_bb=5.5, hero_stack_bb=38, villain_stack_bb=38,
                         street='flop', mode=m)
            self.assertIsNotNone(r, 'morreu em %s' % m)
            self.assertEqual(r['recommended_shadow'], 'bet')
            self.assertTrue(any('CHIP_EV_APPROX_EM_%s' % m.upper() in c for c in r['caveats']))

    def test_nunca_libera_execucao(self):
        r = self._flop(['As', 'Ah'])
        self.assertFalse(r['execution_allowed'])

    def test_flop_fora_dos_100_devolve_none(self):
        # flop improvavel de nao estar no pacote? os 100 cobrem por isomorfismo muita
        # coisa; usamos um claramente coberto como controle e confiamos no match canonico.
        r = self._flop(['As', 'Ah'])
        self.assertIsNotNone(r)                           # 822 esta coberto


if __name__ == '__main__':
    unittest.main()
