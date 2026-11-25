"""A1 — testes do módulo de antecipação (fold/check preparado + invalidadores).

Tudo offline: o estado e os botões são dicts, como o operador os teria lido. Cada
teste trava UM invariante de segurança do adendo A1. Rodar no laboratório antes de
qualquer sessão ao vivo (AGENTS.md)."""
import unittest

import anticipation as A


# ---- fixtures mínimas (formato real de table_state / botões) ---------------
def _state(hero_pos='CO', to_call=2.5, bets=((1, 2.5),)):
    return dict(positions={'hero': hero_pos},
                to_call_bb=to_call,
                bets=[dict(seat=s, bet_bb=b) for s, b in bets])


def _buttons(*actions):
    return [dict(action=a) for a in actions]


def _advice(recommended='fold', status='ADVICE', phase='preflop', validated=True, node_id='n1'):
    return dict(recommended=recommended, status=status, phase=phase,
                validated=validated, node_id=node_id)


def _premium(cards):
    return tuple(sorted(c[0] for c in cards)) in (('A', 'A'), ('A', 'K'), ('K', 'K'))


class FingerprintTests(unittest.TestCase):
    def test_estavel_sob_jitter_de_ocr(self):
        a = A.decision_fingerprint(_state(to_call=3.49, bets=((1, 3.51),)))
        b = A.decision_fingerprint(_state(to_call=3.51, bets=((1, 3.49),)))
        self.assertEqual(a, b)                       # quantização em 0.5BB absorve o jitter

    def test_muda_com_nova_aposta(self):
        base = A.decision_fingerprint(_state(bets=((1, 2.5),)))
        reraise = A.decision_fingerprint(_state(to_call=8.0, bets=((1, 2.5), (3, 8.0))))
        self.assertNotEqual(base, reraise)           # 3-bet no meio invalida

    def test_ignora_bet_zero_ou_ilegivel(self):
        com = A.decision_fingerprint(_state(bets=((1, 2.5), (4, 0.0))))
        sem = A.decision_fingerprint(_state(bets=((1, 2.5),)))
        self.assertEqual(com, sem)

    def test_available_actions_so_conta_acao_resolvida(self):
        acts = A.available_actions([dict(action='FOLD'), dict(action=None), dict(label='??')])
        self.assertEqual(acts, frozenset({'FOLD'}))


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.st = A.AnticipationStore()
        self.fp = A.decision_fingerprint(_state())

    def test_prepara_fold_seguro(self):
        self.assertTrue(self.st.prepare('m1', 'h1', _advice('fold'), self.fp, ['Ah', '7d'], is_premium=_premium))
        self.assertEqual(self.st.stats['prepared'], 1)

    def test_prepara_check_seguro(self):
        fp = A.decision_fingerprint(_state(to_call=0.0, bets=()))
        self.assertTrue(self.st.prepare('m1', 'h1', _advice('check'), fp, ['9c', '4s']))

    def test_nunca_prepara_call(self):
        self.assertFalse(self.st.prepare('m1', 'h1', _advice('call'), self.fp, ['Ah', 'Kh']))
        self.assertEqual(self.st.stats['rejected_unsafe'], 1)

    def test_nunca_prepara_raise(self):
        self.assertFalse(self.st.prepare('m1', 'h1', _advice('raise'), self.fp, ['Ah', 'Kh']))

    def test_nao_prepara_abstencao_nem_pos_flop(self):
        self.assertFalse(self.st.prepare('m1', 'h1', _advice('fold', status='ABSTAIN'), self.fp, ['2c', '7d']))
        self.assertFalse(self.st.prepare('m1', 'h2', _advice('check', phase='postflop'), self.fp, ['2c', '7d']))

    def test_blindagem_nunca_prepara_fold_de_premium(self):
        self.assertFalse(self.st.prepare('m1', 'h1', _advice('fold'), self.fp, ['Ah', 'As'], is_premium=_premium))
        self.assertEqual(self.st.stats['rejected_premium'], 1)

    def test_mao_sem_id_nunca_entra(self):
        self.assertFalse(self.st.prepare('m1', None, _advice('fold'), self.fp, ['Ah', '7d'], is_premium=_premium))


class TakeTests(unittest.TestCase):
    def setUp(self):
        self.st = A.AnticipationStore()
        self.fp = A.decision_fingerprint(_state())

    def _prep_fold(self, table='m1', hand='h1', cards=('Ah', '7d'), node_id='nX', validated=True):
        self.st.prepare(table, hand, _advice('fold', node_id=node_id, validated=validated),
                        self.fp, list(cards), is_premium=_premium)

    def test_hit_quando_tudo_bate(self):
        self._prep_fold()
        got = self.st.take('m1', 'h1', self.fp, A.available_actions(_buttons('FOLD', 'CALL', 'RAISE')), ['Ah', '7d'])
        self.assertEqual(got, dict(action='fold', source='anticipated', validated=True, node_id='nX'))
        self.assertEqual(self.st.stats['hits'], 1)

    def test_miss_quando_fingerprint_muda_mas_mantem_prep(self):
        self._prep_fold()
        fp2 = A.decision_fingerprint(_state(to_call=8.0, bets=((1, 2.5), (3, 8.0))))
        self.assertIsNone(self.st.take('m1', 'h1', fp2, {'FOLD'}, ['Ah', '7d']))   # 3-bet: recomputa
        self.assertEqual(self.st.stats['miss_state'], 1)
        self.assertIsNotNone(self.st.take('m1', 'h1', self.fp, {'FOLD'}, ['Ah', '7d']))  # estado volta: ainda vale

    def test_discarda_quando_cartas_divergem(self):
        self._prep_fold()
        self.assertIsNone(self.st.take('m1', 'h1', self.fp, {'FOLD'}, ['Kc', 'Kd']))     # mão nova
        self.assertEqual(self.st.stats['discarded_hand'], 1)
        self.assertEqual(len(self.st), 0)                                                # apagada de vez

    def test_check_preparado_nao_dispara_sem_botao_check(self):
        fp = A.decision_fingerprint(_state(to_call=0.0, bets=()))
        self.st.prepare('m1', 'h1', _advice('check'), fp, ['9c', '4s'])
        self.assertIsNone(self.st.take('m1', 'h1', fp, {'FOLD', 'CALL', 'RAISE'}, ['9c', '4s']))
        self.assertEqual(self.st.stats['miss_not_offered'], 1)

    def test_fold_preparado_exige_botao_fold(self):
        self._prep_fold()
        self.assertIsNone(self.st.take('m1', 'h1', self.fp, {'CHECK'}, ['Ah', '7d']))

    def test_take_aceita_lista_crua_de_botoes(self):
        self._prep_fold()
        got = self.st.take('m1', 'h1', self.fp, _buttons('FOLD', 'CALL'), ['Ah', '7d'])
        self.assertTrue(got and got['action'] == 'fold')

    def test_mao_sem_id_nao_aproveita(self):
        self.assertIsNone(self.st.take('m1', None, self.fp, {'FOLD'}, ['Ah', '7d']))

    def test_hero_cards_ausente_na_chegada_nao_bloqueia(self):
        # Chegada sem leitura de cartas (None) não é prova de mão nova: fingerprint +
        # oferta de botão ainda guardam o disparo.
        self._prep_fold()
        self.assertIsNotNone(self.st.take('m1', 'h1', self.fp, {'FOLD'}, None))


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.fp = A.decision_fingerprint(_state())

    def test_invalidate_por_mao_e_por_mesa(self):
        st = A.AnticipationStore()
        st.prepare('m1', 'h1', _advice('fold'), self.fp, ['Ah', '7d'], is_premium=_premium)
        st.prepare('m1', 'h2', _advice('fold'), self.fp, ['2c', '7d'], is_premium=_premium)
        st.prepare('m2', 'h9', _advice('fold'), self.fp, ['3c', '8d'], is_premium=_premium)
        st.invalidate('m1', 'h1')
        self.assertIsNone(st.take('m1', 'h1', self.fp, {'FOLD'}, ['Ah', '7d']))
        self.assertIsNotNone(st.take('m1', 'h2', self.fp, {'FOLD'}, ['2c', '7d']))
        st.invalidate('m1')                       # mesa inteira
        self.assertIsNone(st.take('m1', 'h2', self.fp, {'FOLD'}, ['2c', '7d']))
        self.assertIsNotNone(st.take('m2', 'h9', self.fp, {'FOLD'}, ['3c', '8d']))  # outra mesa intacta

    def test_loja_limitada_lru(self):
        st = A.AnticipationStore(limit=3)
        for i in range(5):
            st.prepare('m1', 'h%d' % i, _advice('fold'), self.fp, ['2c', '7d'], is_premium=_premium)
        self.assertEqual(len(st), 3)
        self.assertIsNone(st.take('m1', 'h0', self.fp, {'FOLD'}, ['2c', '7d']))      # mais antiga saiu
        self.assertIsNotNone(st.take('m1', 'h4', self.fp, {'FOLD'}, ['2c', '7d']))   # recente fica


class TurnEpochTrackerTests(unittest.TestCase):
    def test_pisca_isolado_nao_fecha_a_epoca(self):
        t = A.TurnEpochTracker(debounce=3)
        e1 = t.on_turn('m1', 'h1')          # vez chega -> época 1
        self.assertEqual(e1, 1)
        self.assertFalse(t.on_nonturn('m1'))  # 1 pisca: não fecha
        e2 = t.on_turn('m1', 'h1')          # vez volta: MESMA época (sem recomputar)
        self.assertEqual(e2, 1)

    def test_fim_real_da_vez_fecha_e_nova_vez_incrementa(self):
        t = A.TurnEpochTracker(debounce=3)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)
        self.assertFalse(t.on_nonturn('m1'))
        self.assertFalse(t.on_nonturn('m1'))
        self.assertTrue(t.on_nonturn('m1'))   # 3ª consecutiva: fecha
        self.assertEqual(t.on_turn('m1', 'h2'), 2)  # próxima vez: nova época

    def test_troca_de_mao_incrementa_epoca_mesmo_sem_gap(self):
        t = A.TurnEpochTracker(debounce=3)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)
        self.assertEqual(t.on_turn('m1', 'h2'), 2)   # mão nova na vez seguinte

    def test_mesma_mao_sem_gap_nao_incrementa(self):
        t = A.TurnEpochTracker(debounce=3)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)   # mesmo frame/vez contínua

    def test_streak_reseta_ao_voltar_a_vez(self):
        t = A.TurnEpochTracker(debounce=3)
        t.on_turn('m1', 'h1')
        t.on_nonturn('m1'); t.on_nonturn('m1')       # 2 piscas
        t.on_turn('m1', 'h1')                        # vez volta -> reseta streak
        self.assertFalse(t.on_nonturn('m1'))         # agora 1 pisca de novo, não fecha
        self.assertEqual(t.epoch('m1'), 1)           # continua na época 1

    def test_close_forca_encerramento(self):
        t = A.TurnEpochTracker(debounce=3)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)
        t.close('m1')
        self.assertFalse(t.in_turn('m1'))
        self.assertEqual(t.on_turn('m1', 'h1'), 2)   # reabre como nova época

    def test_mesas_independentes(self):
        t = A.TurnEpochTracker(debounce=3)
        self.assertEqual(t.on_turn('m1', 'h1'), 1)
        self.assertEqual(t.on_turn('m2', 'h1'), 1)   # outra mesa, época própria
        t.on_nonturn('m1'); t.on_nonturn('m1'); t.on_nonturn('m1')
        self.assertFalse(t.in_turn('m1'))
        self.assertTrue(t.in_turn('m2'))             # m2 intacta


if __name__ == '__main__':
    unittest.main()
