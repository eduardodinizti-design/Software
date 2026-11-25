"""Memória de board: acumula cartas por posição (imutável/monotônico na mão),
preenche um frame de leitura falha, cresce com a street, nunca inventa nem
devolve board inválido (1-2 cartas), e não cruza fronteira de mão."""
import unittest

from board_memory import BoardMemory

FLOP = ['3d', 'Td', '7s']
TURN = FLOP + ['8s']


class BoardMemoryTest(unittest.TestCase):
    def test_two_votes_accept_flop(self):
        bm = BoardMemory(votes=2)
        self.assertEqual(bm.observe('t', 'H1', FLOP), [])     # 1 voto: ainda não
        self.assertEqual(bm.observe('t', 'H1', FLOP), FLOP)   # 2 votos: aceita

    def test_single_frame_gap_is_filled(self):
        bm = BoardMemory(votes=2)
        bm.observe('t', 'H1', FLOP)
        bm.observe('t', 'H1', FLOP)                           # flop aceito
        self.assertEqual(bm.observe('t', 'H1', []), FLOP)     # frame sem leitura -> segura

    def test_board_grows_flop_to_turn(self):
        bm = BoardMemory(votes=2)
        bm.observe('t', 'H1', FLOP); bm.observe('t', 'H1', FLOP)
        bm.observe('t', 'H1', TURN)                           # turn: 1 voto na pos 3
        self.assertEqual(bm.observe('t', 'H1', TURN), TURN)   # 2 votos: cresce p/ 4

    def test_turn_held_even_if_frame_reads_only_flop(self):
        bm = BoardMemory(votes=2)
        for _ in range(2):
            bm.observe('t', 'H1', TURN)                       # turn aceito (4 cartas)
        self.assertEqual(bm.observe('t', 'H1', FLOP), TURN)   # regressão de leitura não encolhe

    def test_partial_prefix_below_three_is_not_a_board(self):
        bm = BoardMemory(votes=2)
        # só a 1ª carta lê repetidamente; 2 não bastam p/ um board
        bm.observe('t', 'H1', ['3d']);
        self.assertEqual(bm.observe('t', 'H1', ['3d']), [])   # 1 carta aceita != board

    def test_gap_in_middle_breaks_prefix(self):
        bm = BoardMemory(votes=2)
        # posições 0,1 confirmam; 2 nunca confirma -> prefixo < 3 -> []
        for _ in range(2):
            bm.observe('t', 'H1', ['3d', 'Td', None])
        self.assertEqual(bm.board('t', 'H1'), [])

    def test_new_hand_does_not_inherit(self):
        bm = BoardMemory(votes=2)
        bm.observe('t', 'H1', FLOP); bm.observe('t', 'H1', FLOP)
        self.assertEqual(bm.observe('t', 'H2', []), [])       # H2 começa limpo

    def test_accepted_card_is_immutable_conflict_counted(self):
        bm = BoardMemory(votes=2)
        bm.observe('t', 'H1', FLOP); bm.observe('t', 'H1', FLOP)
        out = bm.observe('t', 'H1', ['9c', 'Td', '7s'])       # pos0 diverge do aceito
        self.assertEqual(out, FLOP)                           # não troca a carta aceita
        self.assertGreaterEqual(bm.stats['conflicts'], 1)

    def test_none_hand_id_returns_current(self):
        bm = BoardMemory(votes=2)
        bm.observe('t', 'H1', FLOP); bm.observe('t', 'H1', FLOP)
        self.assertEqual(bm.observe('t', None, FLOP), [])     # hand_id None não acumula

    def test_tables_independent(self):
        bm = BoardMemory(votes=2)
        bm.observe('t1', 'H1', FLOP); bm.observe('t1', 'H1', FLOP)
        self.assertEqual(bm.board('t2', 'H1'), [])

    def test_lru_eviction(self):
        bm = BoardMemory(limit=2, votes=1)
        bm.observe('t', 'A', FLOP)
        bm.observe('t', 'B', FLOP)
        bm.observe('t', 'C', FLOP)                            # evicta A
        self.assertEqual(bm.board('t', 'A'), [])
        self.assertEqual(bm.board('t', 'C'), FLOP)


if __name__ == '__main__':
    unittest.main()
