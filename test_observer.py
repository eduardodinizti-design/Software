"""B09 — observação contínua leve: rastreia o cenário por mão sem perder história."""
import unittest

from strategy.observer import ContinuousObserver


def ts(bets, hero='BB'):
    return dict(positions={'hero': hero, 'a': 'UTG', 'b': 'CO', 'sb': 'SB', 'bb': 'BB'},
                bets=bets, seats={'hero': {'stack_bb': 40.0}})


OPEN = [{'seat': 'a', 'bet_bb': 2.5}, {'seat': 'sb', 'bet_bb': 0.5}, {'seat': 'bb', 'bet_bb': 1.0}]
BLINDS_ONLY = [{'seat': 'sb', 'bet_bb': 0.5}, {'seat': 'bb', 'bet_bb': 1.0}]
THREEBET = [{'seat': 'a', 'bet_bb': 2.5}, {'seat': 'b', 'bet_bb': 8.0},
            {'seat': 'sb', 'bet_bb': 0.5}, {'seat': 'bb', 'bet_bb': 1.0}]


class ObserverTests(unittest.TestCase):
    def test_tracks_current_scenario(self):
        o = ContinuousObserver()
        self.assertEqual(o.observe(('t', 'h1'), ts(OPEN))['scenario'], 'open')

    def test_history_not_discarded_on_lost_read(self):
        # Viu 'open'; no frame seguinte perde a leitura do raise (só blinds). NÃO
        # pode regredir p/ 'unopened' na mesma mão: retém a história.
        o = ContinuousObserver()
        o.observe(('t', 'h1'), ts(OPEN))
        eff = o.observe(('t', 'h1'), ts(BLINDS_ONLY))
        self.assertEqual(eff['scenario'], 'open')
        self.assertTrue(eff.get('retained_history'))

    def test_upgrades_when_aggression_increases(self):
        o = ContinuousObserver()
        o.observe(('t', 'h1'), ts(OPEN))
        eff = o.observe(('t', 'h1'), ts(THREEBET))      # agora há um 3bet a frio
        self.assertEqual(eff['scenario'], 'threebet_cold')

    def test_new_hand_does_not_inherit_history(self):
        o = ContinuousObserver()
        o.observe(('t', 'h1'), ts(OPEN))
        eff = o.observe(('t', 'h2'), ts(BLINDS_ONLY))   # mão nova -> reinicia
        self.assertEqual(eff['scenario'], 'unopened')
        self.assertFalse(eff.get('retained_history'))

    def test_forget(self):
        o = ContinuousObserver()
        o.observe(('t', 'h1'), ts(OPEN))
        o.forget(('t', 'h1'))
        self.assertIsNone(o.scenario(('t', 'h1')))


if __name__ == '__main__':
    unittest.main()
