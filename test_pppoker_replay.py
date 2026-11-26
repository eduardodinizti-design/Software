"""TRAVA do replay offline da percepção protobuf do PPPoker: capturas reais -> cérebro -> decisão.

Determinístico (AA abre) + tolerância + smoke na captura real do repo. Puro/offline: sem cliente,
sem clique, sem rede."""
import os
import unittest

import pppoker_replay as R
from ppp_cards import decode_cards

PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
CAPTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'research', 'ppp_il2cpp', 'estado_mesa_multitable_20261120.json')


def _card(rank, suit):           # encoding PPPoker: suit*256 + rank (ver ppp_cards)
    return suit * 256 + rank


def _entry_btn_aa():
    """3-handed, hero no BTN com AA, folded-to-hero (first in preflop). SB=seat0, BB=seat1,
    BTN/hero=seat2. sb=50 -> bb=100; stacks 100bb (deep). Hero = único com 2 cartas face-up."""
    As, Ah = _card(14, 4), _card(14, 3)      # A♠, A♥
    return {
        'ts': 0, 'room': 'TESTE',
        'table': {'dealer': 2, 'sbseat': 0, 'bbseat': 1, 'sb': 50, 'minraise': 100,
                  'maxraise': 10000, 'board': [], 'stage': 0, 'tocall': 100, 'pot': 150},
        'players': [
            {'seat': 0, 'uid': 1, 'name': 'sb', 'stack': 10000, 'sit': 0, 'bet': 50, 'act': 0, 'hascard': 1, 'cards': []},
            {'seat': 1, 'uid': 2, 'name': 'bb', 'stack': 10000, 'sit': 0, 'bet': 100, 'act': 0, 'hascard': 1, 'cards': []},
            {'seat': 2, 'uid': 3, 'name': 'hero', 'stack': 10000, 'sit': 0, 'bet': 0, 'act': 0, 'hascard': 1, 'cards': [As, Ah]},
        ],
    }


class LoadCapture(unittest.TestCase):
    def test_captura_real_vira_lista_de_mesas(self):
        if not os.path.exists(CAPTURE):
            self.skipTest('captura ausente')
        entries = R.load_capture(CAPTURE)
        self.assertEqual(len(entries), 2)                      # multitable: 2 mesas
        for _k, ent in entries:
            self.assertIn('players', ent)


class DecideReal(unittest.TestCase):
    def _advisor(self):
        if not os.path.exists(PACK):
            self.skipTest('pack de ranges ausente')
        return R._load_advisor()

    def test_smoke_captura_real_decide_sem_crash(self):
        if not os.path.exists(CAPTURE):
            self.skipTest('captura ausente')
        adv = self._advisor()
        out = R.replay(R.load_capture(CAPTURE), adv)
        self.assertEqual(len(out), 2)
        for d in out:
            # todo registro tem os campos de exibição e um status (ADVICE ou ABSTAIN), nunca crash
            for key in ('table', 'hero', 'pos', 'board', 'status'):
                self.assertIn(key, d)
            self.assertIsInstance(R.format_line(d), str)

    def test_hero_decodificado_na_captura_real(self):
        if not os.path.exists(CAPTURE):
            self.skipTest('captura ausente')
        adv = self._advisor()
        out = {d['table']: d for d in R.replay(R.load_capture(CAPTURE), adv)}
        # mesa 14603957: hero seat 6 = 5c 8d (ver ppp_cards); confirma leitura EXATA (não OCR)
        self.assertEqual(out['14603957']['hero'], ['5c', '8d'])
        self.assertEqual(out['14603993']['hero'], ['9s', '7d'])


class DecideSintetico(unittest.TestCase):
    def test_aa_btn_abre_nunca_folda(self):
        if not os.path.exists(PACK):
            self.skipTest('pack de ranges ausente')
        adv = R._load_advisor()
        d = R.decide_entry('AA', _entry_btn_aa(), adv)
        self.assertEqual(d['hero'], ['As', 'Ah'])
        self.assertEqual(d['pos'], 'BTN')
        self.assertEqual(d['status'], 'ADVICE')
        # AA deep no BTN first-in: AGRIDE (raise/open/all_in), JAMAIS fold/check
        self.assertIn(d['recommended'], ('raise', 'open', 'open_raise', 'all_in', 'three_bet'))


if __name__ == '__main__':
    unittest.main()
