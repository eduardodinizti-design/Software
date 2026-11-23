"""Testa multiway_bb_defense.py contra as fixtures da aula + as regras macro.

Regras verificadas (todas vindas da aula 'Defesa multiway do BB'):
  - fold SOBE com n de jogadores, com profundidade e com a forca (tightness)
    do range dos viloes; IP sobre o SB defende ~como HU (nao folda a mais);
  - squeeze e LINEAR em deep e POLARIZADO+JAM no curto; freq maior vs capado,
    menor vs tight; size maior em deep.
"""
import json
import os
import unittest

import multiway_bb_defense as m

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "fixtures", "multiway_bb_fixtures.json")


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(FIX, encoding="utf-8") as fh:
            cls.rows = json.load(fh)

    def test_quantidade_e_schema(self):
        self.assertEqual(len(self.rows), 58)
        req = {"hero_pos", "raiser_pos", "callers", "n_players", "stack_bb",
               "hero_rel_position", "opp_strength", "hand", "action", "fonte"}
        for r in self.rows:
            self.assertTrue(req <= set(r), "faltam chaves em %r" % r)
            self.assertEqual(r["hero_pos"], "BB")
            self.assertIn(r["action"], ("fold", "call", "squeeze", "jam"))
            self.assertIn(r["hero_rel_position"], ("IP", "OOP"))
            self.assertIn(r["opp_strength"], ("wide", "tight", "capped"))
            self.assertEqual(r["n_players"], 2 + len(r["callers"]))

    def test_classificador_bate_com_fixtures(self):
        for r in self.rows:
            line, _ = m.classify_line(r["hand"], r["stack_bb"],
                                      r["opp_strength"], r["hero_rel_position"],
                                      r["n_players"])
            if r.get("mixed"):
                # marginais: a aula hesita -> modulo pode abster; so nao pode crashar
                self.assertIn(line, ("fold", "call", "aggressive", "study"))
                continue
            self.assertEqual(line, m.action_to_line(r["action"]),
                             "mao %s (%s, %dbb, %s): esperado %s, veio %s" %
                             (r["hand"], r["opp_strength"], r["stack_bb"],
                              r["hero_rel_position"], r["action"], line))

    def test_estilo_linear_deep_jam_short(self):
        # quando o classificador recomenda agressao, o estilo respeita o regime
        for r in self.rows:
            if m.action_to_line(r["action"]) != "aggressive" or r.get("mixed"):
                continue
            line, style = m.classify_line(r["hand"], r["stack_bb"],
                                          r["opp_strength"],
                                          r["hero_rel_position"], r["n_players"])
            if line != "aggressive":
                continue
            if m.is_short(r["stack_bb"]):
                self.assertIn(style, ("jam", "squeeze_polar"))
            else:
                self.assertEqual(style, "squeeze_linear")


class FoldScalingTests(unittest.TestCase):
    def test_hu_ancora(self):
        self.assertAlmostEqual(m.estimated_fold_freq(2, 25, "wide", "OOP"), 0.21, places=2)
        self.assertAlmostEqual(m.estimated_fold_freq(2, 100, "wide", "OOP"), 0.30, places=2)

    def test_folda_mais_com_mais_jogadores(self):
        hu = m.estimated_fold_freq(2, 100, "wide", "OOP")
        tri = m.estimated_fold_freq(3, 100, "wide", "OOP")
        quad = m.estimated_fold_freq(4, 100, "tight", "OOP")
        self.assertGreater(tri, hu)
        self.assertGreater(quad, m.estimated_fold_freq(3, 100, "tight", "OOP"))

    def test_folda_mais_com_profundidade(self):
        curto = m.estimated_fold_freq(3, 25, "wide", "OOP")
        fundo = m.estimated_fold_freq(3, 100, "wide", "OOP")
        self.assertGreater(fundo, curto)

    def test_folda_mais_vs_range_forte(self):
        wide = m.estimated_fold_freq(3, 100, "wide", "OOP")
        tight = m.estimated_fold_freq(3, 100, "tight", "OOP")
        self.assertGreater(tight, wide)

    def test_ip_sobre_sb_defende_como_hu(self):
        # caller = SB, BB IP: folda ~como HU (nao sofre a penalidade multiway)
        ip = m.estimated_fold_freq(3, 100, "capped", "IP")
        oop = m.estimated_fold_freq(3, 100, "wide", "OOP")
        hu = m.estimated_fold_freq(2, 100, "wide", "OOP")
        self.assertAlmostEqual(ip, hu, places=2)
        self.assertLess(ip, oop)

    def test_ancoras_aula(self):
        # 3way CO+BTN ~36%@25bb e ~40%@100bb; 3way UTG+LJ ~60%@100; 4way ~76%
        self.assertAlmostEqual(m.estimated_fold_freq(3, 25, "wide", "OOP"), 0.33, delta=0.05)
        self.assertAlmostEqual(m.estimated_fold_freq(3, 100, "wide", "OOP"), 0.40, delta=0.05)
        self.assertAlmostEqual(m.estimated_fold_freq(3, 100, "tight", "OOP"), 0.60, delta=0.05)
        self.assertAlmostEqual(m.estimated_fold_freq(4, 100, "tight", "OOP"), 0.76, delta=0.06)


class SqueezeTests(unittest.TestCase):
    def test_perfil_linear_deep_polar_short(self):
        self.assertEqual(m.squeeze_profile(100), "linear")
        self.assertEqual(m.squeeze_profile(25), "polarized_jam")

    def test_freq_capado_maior_tight_menor(self):
        wide = m.squeeze_freq_est(100, "wide", "OOP")
        capped = m.squeeze_freq_est(100, "capped", "IP")
        tight = m.squeeze_freq_est(100, "tight", "OOP")
        self.assertGreater(capped, wide)
        self.assertGreater(wide, tight)
        self.assertAlmostEqual(wide, 0.12, delta=0.02)
        self.assertAlmostEqual(capped, 0.17, delta=0.02)
        self.assertAlmostEqual(tight, 0.07, delta=0.02)

    def test_size_maior_deep(self):
        self.assertGreater(m.squeeze_size_bb(100), m.squeeze_size_bb(25))
        self.assertAlmostEqual(m.squeeze_size_bb(25), 6.6, delta=0.3)
        self.assertAlmostEqual(m.squeeze_size_bb(100), 12.0, delta=0.3)


class GatingTests(unittest.TestCase):
    def test_nunca_validado(self):
        self.assertFalse(m.VALIDATED)
        r = m.recommend(25, "capped", "IP", 3, hand="A8o")
        self.assertFalse(r["validated"])
        self.assertEqual(r["direction"], "tighter_multiway")
        self.assertIn("profile", r["squeeze"])


if __name__ == "__main__":
    unittest.main()
