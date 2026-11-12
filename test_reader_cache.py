"""Cache de HUD/bounty: relê só a cada N frames e em mudança de ocupação, com merge
que mantém o valor bom (contra latência e animação). Leitores fake (sem OCR)."""
import unittest

from reader_cache import ReaderCache


class HudCacheTests(unittest.TestCase):
    def test_reads_once_then_caches(self):
        calls = []

        def fn(crop, seats):
            calls.append(list(seats))
            return {s: {'stats': {'vpip': 20}, 'confidence': 'high'} for s in seats}

        c = ReaderCache(hud_every=100, hud_fn=fn)
        occ = ['bot_left', 'left_up']
        for _ in range(5):
            r = c.huds(None, 't', occ)
        self.assertEqual(len(calls), 1)                  # leu 1x, reusou o cache
        self.assertEqual(set(r), set(occ))

    def test_refreshes_every_n(self):
        calls = []

        def fn(crop, seats):
            calls.append(1)
            return {s: {'x': 1} for s in seats}

        c = ReaderCache(hud_every=3, hud_fn=fn)
        for _ in range(7):
            c.huds(None, 't', ['a'])
        self.assertEqual(len(calls), 3)                  # n=0,3,6 -> 3 leituras em 7 frames

    def test_occupancy_change_invalidates_seat(self):
        calls = []

        def fn(crop, seats):
            calls.append(list(seats))
            return {s: {'v': 1} for s in seats}

        c = ReaderCache(hud_every=100, hud_fn=fn)
        c.huds(None, 't', ['a', 'b'])
        c.huds(None, 't', ['a', 'b'])                    # cache
        c.huds(None, 't', ['a', 'c'])                    # b saiu, c entrou -> relê (c faltando)
        self.assertEqual(len(calls), 2)
        c.huds(None, 't', ['a', 'c'])                    # tudo cacheado -> sem releitura
        self.assertEqual(len(calls), 2)

    def test_hero_skipped(self):
        c = ReaderCache(hud_fn=lambda crop, seats: {s: {} for s in seats})
        r = c.huds(None, 't', ['hero', 'a'])
        self.assertNotIn('hero', r)

    def test_failed_refresh_marks_value_stale(self):
        # #A7: leitura boa, depois refresh que FALHA ({}) -> o valor e mantido p/
        # continuidade, mas marcado velho (_age>0) para o exploit NAO trata-lo como fresco.
        seq = [{'a': {'stats': {}, 'confidence': 'high'}}, {}]

        def fn(crop, seats):
            return seq.pop(0) if seq else {}

        c = ReaderCache(hud_every=1, hud_fn=fn)              # tenta reler todo frame
        r1 = c.huds(None, 't', ['a'])
        self.assertEqual(r1['a']['_age'], 0)                 # recem-lido
        r2 = c.huds(None, 't', ['a'])                        # refresh falhou
        self.assertEqual(r2['a']['confidence'], 'high')      # valor preservado
        self.assertGreaterEqual(r2['a']['_age'], 1)          # porem marcado velho

    def test_reuse_between_refreshes_is_not_stale(self):
        # #A7: reuso do cache ENTRE refreshes (cadencia nao disparou) nao envelhece: o
        # valor segue confirmado da ultima leitura boa, so nao foi relido neste frame.
        def fn(crop, seats):
            return {s: {'confidence': 'high'} for s in seats}

        c = ReaderCache(hud_every=100, hud_fn=fn)
        c.huds(None, 't', ['a'])                             # n=0 -> le
        r = c.huds(None, 't', ['a'])                         # n=1 -> reuso confiavel
        self.assertEqual(r['a']['_age'], 0)


class BountyCacheTests(unittest.TestCase):
    def test_failed_refresh_withholds_bounty_then_recovers(self):
        # #A7: bounty muda por KO sem mudar ocupacao. Um refresh que FALHA (None) nao
        # zera o cache (continuidade), mas o valor velho NAO e servido ao overlay de
        # call-off ate reconfirmar. Reconfirmando, volta a ser servido.
        seq = [{'a': 135}, {'a': None}, {'a': 135}]

        def fn(crop, seats):
            return seq.pop(0) if seq else {}

        c = ReaderCache(bounty_every=1, bounty_fn=fn)      # tenta reler todo frame
        self.assertEqual(c.bounties(None, 't', ['a']), {'a': 135})   # lido
        self.assertEqual(c.bounties(None, 't', ['a']), {})           # refresh falhou -> retido
        self.assertEqual(c.bounties(None, 't', ['a']), {'a': 135})   # reconfirmou -> volta

    def test_reuse_between_refreshes_still_served(self):
        # #A7: reuso ENTRE refreshes (cadencia nao disparou) segue servido: o valor foi
        # confirmado na ultima leitura boa, so nao foi relido neste frame.
        seq = [{'a': 135}]

        def fn(crop, seats):
            return seq.pop(0) if seq else {}

        c = ReaderCache(bounty_every=100, bounty_fn=fn)    # le 1x, reusa
        self.assertEqual(c.bounties(None, 't', ['a']), {'a': 135})
        self.assertEqual(c.bounties(None, 't', ['a']), {'a': 135})   # reuso confiavel


if __name__ == '__main__':
    unittest.main()
