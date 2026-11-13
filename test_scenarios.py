"""B08 — classificador único de cenário pré-flop. Invariantes do plano viram testes.

Cenários obrigatórios: dois limps NÃO viram pote não aberto; open + dois calls
preserva os callers; limp+iso; 3bet/4bet; sequência ambígua fica pendente."""
import unittest

from strategy.scenarios import classify, from_table_state


def P(position, bet, stack=40.0, hero=False):
    return dict(position=position, bet_bb=bet, stack_bb=stack, is_hero=hero)


def obs(players, hero='BTN'):
    return dict(hero=hero, blinds=dict(sb=0.5, bb=1.0), players=players)


BLINDS = [P('SB', 0.5), P('BB', 1.0)]


class UnopenedVsLimpedTests(unittest.TestCase):
    def test_only_blinds_is_unopened(self):
        c = classify(obs(BLINDS + [P('BTN', 0.0, hero=True)]))
        self.assertEqual(c['scenario'], 'unopened')
        self.assertEqual(c['n_limpers'], 0)

    def test_two_limps_is_NOT_unopened(self):
        # O bug central: dois limps viravam first_in. Agora é 'limped', 2 limpers.
        c = classify(obs(BLINDS + [P('UTG', 1.0), P('CO', 1.0), P('BTN', 0.0, hero=True)]))
        self.assertEqual(c['scenario'], 'limped')
        self.assertEqual((c['n_limpers'], c['limpers']), (2, ['UTG', 'CO']))
        self.assertIn('iso_raise', c['hero_options'])
        self.assertNotIn('open_raise', c['hero_options'])   # pote NÃO está aberto p/ open

    def test_sb_complete_is_a_limp_bb_post_is_not(self):
        c = classify(obs([P('SB', 1.0), P('BB', 1.0), P('BTN', 0.0, hero=True)]))
        self.assertEqual((c['scenario'], c['limpers']), ('limped', ['SB']))


class OpenAndCallersTests(unittest.TestCase):
    def test_open_no_callers(self):
        c = classify(obs(BLINDS + [P('UTG', 2.5), P('BTN', 0.0, hero=True)]))
        self.assertEqual((c['scenario'], c['aggressor'], c['n_callers']), ('open', 'UTG', 0))

    def test_open_with_two_callers_preserved(self):
        # UTG open 2.5 + HJ call + CO call, hero BTN: callers NÃO somem.
        c = classify(obs(BLINDS + [P('UTG', 2.5), P('HJ', 2.5), P('CO', 2.5),
                                   P('BTN', 0.0, hero=True)]))
        self.assertEqual(c['scenario'], 'open_with_callers')
        self.assertEqual(c['aggressor'], 'UTG')
        self.assertEqual((c['n_callers'], sorted(c['callers'])), (2, ['CO', 'HJ']))
        self.assertIn('squeeze', c['hero_options'])

    def test_limp_then_iso_keeps_limpers(self):
        c = classify(obs(BLINDS + [P('UTG', 1.0), P('CO', 3.0), P('BTN', 0.0, hero=True)]))
        self.assertEqual((c['scenario'], c['aggressor'], c['limpers']),
                         ('limp_then_iso', 'CO', ['UTG']))


class ReraiseTests(unittest.TestCase):
    def test_cold_3bet_is_explicit_and_limited(self):
        c = classify(obs(BLINDS + [P('UTG', 2.5), P('CO', 8.0), P('BTN', 0.0, hero=True)]))
        self.assertEqual((c['scenario'], c['aggressor']), ('threebet_cold', 'CO'))
        self.assertFalse(c['supported'])
        self.assertEqual(c['reason'], 'COLD_RERAISED_POT')

    def test_hero_opened_faces_3bet(self):
        c = classify(obs(BLINDS + [P('CO', 2.5, hero=True), P('BTN', 8.0)], hero='CO'))
        self.assertEqual((c['scenario'], c['aggressor']), ('vs_3bet', 'BTN'))
        self.assertTrue(c['supported'])

    def test_hero_opened_faces_4bet_is_limited(self):
        c = classify(obs(BLINDS + [P('CO', 2.5, hero=True), P('BTN', 8.0), P('SB', 20.0)],
                         hero='CO'))
        self.assertEqual(c['scenario'], 'vs_4bet_or_more')
        self.assertFalse(c['supported'])

    def test_hero_raised_but_no_reraise_is_pending(self):
        c = classify(obs(BLINDS + [P('CO', 2.5, hero=True), P('BTN', 2.5)], hero='CO'))
        self.assertEqual((c['scenario'], c['supported']), ('pending', False))


class AdapterTests(unittest.TestCase):
    def test_from_table_state_two_limps(self):
        ts = dict(positions={'hero': 'BTN', 's1': 'UTG', 's2': 'CO', 'sb': 'SB', 'bb': 'BB'},
                  bets=[{'seat': 's1', 'bet_bb': 1.0}, {'seat': 's2', 'bet_bb': 1.0},
                        {'seat': 'sb', 'bet_bb': 0.5}, {'seat': 'bb', 'bet_bb': 1.0}],
                  seats={'hero': {'stack_bb': 40.0}})
        c = classify(from_table_state(ts))
        self.assertEqual((c['scenario'], c['n_limpers']), ('limped', 2))
        self.assertEqual(c['hero_position'], 'BTN')


if __name__ == '__main__':
    unittest.main()
