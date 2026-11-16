"""Testes da sombra de turn dos 24 boards (`solver_turn_shadow`) e da homologação do
TURN que lê o pacote destilado (`postflop_homologation.run_turn_pack`).

Garante: cobertura por board + isomorfismo de naipe; API semântica de turn (lead/barrel
por linha e carta); e, acima de tudo, o GATE — a sombra NUNCA libera execução e sempre
carimba os caveats de não-execução."""
import unittest

import solver_turn_shadow as sts

# As7d2c está nos 24 boards resolvidos (A-alto, rainbow). Usado como âncora dos testes.
FLOP = ['As', '7d', '2c']


class PackLoadTests(unittest.TestCase):
    def test_pacote_carrega_e_tem_estrutura(self):
        pack = sts.load_pack()
        self.assertIsNotNone(pack, 'pacote turn_pack_24boards.json.gz ausente')
        self.assertEqual(pack['format'], 'nvt_turn_pack_v1')
        self.assertFalse(pack['execution_allowed'])
        self.assertEqual(len(pack['boards']), 24)
        self.assertIn('As7d2c', pack['boards'])
        self.assertIn('nodes', pack)
        self.assertIn('lines', pack)


class FlopCbetTests(unittest.TestCase):
    def test_flop_cbet_board_coberto_per_combo(self):
        r = sts.flop_cbet(['Ah', 'Kd'], FLOP)
        self.assertIsNotNone(r)
        self.assertEqual(r['street'], 'FLOP')
        self.assertEqual(r['actor_pos'], 'BTN')
        self.assertFalse(r['execution_allowed'])          # GATE
        self.assertIn('POSTFLOP_SOLVER_SHADOW', r['caveats'])
        if r['combo_in_range']:
            self.assertIn(r['recommended_shadow'], r['actions'])
            self.assertAlmostEqual(sum(r['freq']), 1.0, places=2)

    def test_board_nao_coberto_retorna_none(self):
        # 9-8-5 com dois naipes repetidos não é isomórfico a nenhum dos 24.
        self.assertIsNone(sts.flop_cbet(['Ah', 'Kd'], ['9h', '8h', '5c']))

    def test_isomorfismo_de_naipe_casa_e_marca_iso(self):
        # Permuta de As7d2c: s->h, d->s, c->d  => Ah7s2d (mesmo A72 rainbow).
        r = sts.flop_cbet(['Kh', 'Qs'], ['Ah', '7s', '2d'])
        self.assertIsNotNone(r)
        self.assertTrue(r['iso'])
        self.assertFalse(r['execution_allowed'])          # GATE

    def test_tamanho_do_flop_invalido(self):
        self.assertIsNone(sts.flop_cbet(['Ah', 'Kd'], ['As', '7d']))


class TurnApiTests(unittest.TestCase):
    def _a_turn_card(self, line='checkthrough'):
        pack = sts.load_pack()
        cards = list(pack['lines']['As7d2c'][line].keys())
        # escolhe uma carta de turn que não seja do flop
        return next(c for c in cards if c not in FLOP)

    def test_turn_lead_bb_na_linha_checkthrough(self):
        t = self._a_turn_card('checkthrough')
        r = sts.turn_lead(['Kh', 'Qd'], FLOP + [t], 'checkthrough')
        self.assertIsNotNone(r)
        self.assertEqual(r['street'], 'TURN')
        self.assertEqual(r['actor_pos'], 'BB')
        self.assertEqual(r['line'], 'checkthrough')
        self.assertIn('check', r['actions'])              # to_call=0 -> tem check no menu
        self.assertFalse(r['execution_allowed'])          # GATE
        self.assertIn('SOLVER_SHADOW_TURN_LIVE_MATCH_NEEDS_POSTFLOP_HISTORY', r['caveats'])

    def test_turn_barrel_btn_na_linha_betcall(self):
        t = self._a_turn_card('betcall')
        r = sts.turn_barrel(['Kh', 'Qd'], FLOP + [t], 'betcall')
        self.assertIsNotNone(r)
        self.assertEqual(r['actor_pos'], 'BTN')
        self.assertEqual(r['line'], 'betcall')
        self.assertFalse(r['execution_allowed'])          # GATE

    def test_turn_exige_4_cartas(self):
        self.assertIsNone(sts.turn_lead(['Kh', 'Qd'], FLOP, 'checkthrough'))

    def test_turn_board_nao_coberto_none(self):
        self.assertIsNone(sts.turn_lead(['Ah', 'Kd'], ['9h', '8h', '5c', '2d'], 'checkthrough'))


class GateInvariantTests(unittest.TestCase):
    def test_nenhum_resultado_libera_execucao(self):
        pack = sts.load_pack()
        t = next(c for c in pack['lines']['As7d2c']['checkthrough'] if c not in FLOP)
        for r in (sts.flop_cbet(['Ah', 'Kd'], FLOP),
                  sts.turn_lead(['Kh', 'Qd'], FLOP + [t], 'checkthrough'),
                  sts.turn_barrel(['Kh', 'Qd'], FLOP + [t], 'betcall')):
            self.assertIsNotNone(r)
            self.assertFalse(r['execution_allowed'])
            self.assertIn('SOLVER_SHADOW_NOT_FOR_EXECUTION', r['caveats'])


class TurnPackHomologTests(unittest.TestCase):
    def test_homologacao_do_pacote_roda_e_tem_estrutura(self):
        import postflop_homologation as homolog
        # amostra pequena de nós p/ rapidez; valida o mecanismo, não a estatística cheia.
        rep = homolog.run_turn_pack(max_nodes=40, max_combos_per_node=12)
        self.assertGreater(rep['total'], 100)
        self.assertGreater(rep['boards'], 0)
        self.assertTrue(0.0 <= rep['agreement_pct'] <= 100.0)
        self.assertIsNotNone(rep['decisive_agreement_pct'])
        self.assertTrue(rep['leak_passivo_heur_check_solver_bet']
                        or rep['leak_agressivo_heur_bet_solver_check'])


if __name__ == '__main__':
    unittest.main()
