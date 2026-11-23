"""Trava a camada heurística de DEFESA CONTRA 3-BET (vs3bet_defense): roda todas as
fixtures extraídas da aula + as TRÊS REGRAS DE OURO (size, linear/polar, posição).

É camada de ESTUDO: o módulo NUNCA arma (validated=False). O teste garante fidelidade
à aula, não homologação para operar ao vivo."""
import json
import os
import unittest

import vs3bet_defense as vd

_FIX = os.path.join(os.path.dirname(__file__), 'fixtures', 'vs3bet_defense_fixtures.json')


def _load():
    with open(_FIX, encoding='utf-8') as fh:
        return json.load(fh)['spots']


class Fixtures(unittest.TestCase):
    def test_todas_as_fixtures_batem(self):
        falhas = []
        for sp in _load():
            res = vd.advise_spot(sp)
            if res.get('recommended') != sp['action']:
                falhas.append('%s %s vs %s %dbb %.1fx %s: esperado=%s obtido=%s (%s)' % (
                    sp['hand'], sp['hero_pos'], sp['villain_pos'], sp['stack_bb'],
                    sp['villain_3bet_size_x'], sp['villain_range_type'], sp['action'],
                    res.get('recommended'), res.get('reason')))
        self.assertEqual([], falhas, '\n'.join(falhas))

    def test_cobertura_minima(self):
        spots = _load()
        self.assertGreaterEqual(len(spots), 30)
        # as quatro ações aparecem no corpus
        acoes = {s['action'] for s in spots}
        self.assertEqual({'fold', 'call', '4bet', 'jam'}, acoes)


class NuncaArma(unittest.TestCase):
    def test_validated_false(self):
        self.assertFalse(vd.VALIDATED)

    def test_toda_advice_marcada_como_estudo(self):
        for sp in _load():
            res = vd.advise_spot(sp)
            self.assertFalse(res.get('validated'))
            self.assertTrue(res.get('advisory_only'))


class RegraOuroSize(unittest.TestCase):
    """Regra 1: maior size => mais fold (a borda cai primeiro)."""

    def test_k9s_defende_normal_folda_grande(self):
        base = dict(hero_pos='HJ', villain_pos='BTN', stack_bb=60,
                    villain_range_type='polar', hand='K9s')
        self.assertEqual('call', vd.advise(villain_3bet_size_x=3.5, **base)['recommended'])
        self.assertEqual('fold', vd.advise(villain_3bet_size_x=4.0, **base)['recommended'])

    def test_borda_suited_cai_quando_size_sobe(self):
        # ATs defende vs 3x e folda vs size grande (linhas 209-216 do txt).
        base = dict(hero_pos='UTG', villain_pos='UTG', stack_bb=70,
                    villain_range_type='linear', hand='ATs')
        self.assertEqual('call', vd.advise(villain_3bet_size_x=3.0, **base)['recommended'])
        self.assertEqual('fold', vd.advise(villain_3bet_size_x=4.5, **base)['recommended'])


class RegraOuroLinearPolar(unittest.TestCase):
    """Regra 2: a MESMA mão folda vs linear e defende vs polar."""

    def test_qjo_fold_vs_linear_call_vs_polar_ip(self):
        self.assertEqual('fold', vd.advise('UTG', 'HJ', 50, 3.0, 'linear', 'QJo')['recommended'])
        self.assertEqual('call', vd.advise('BTN', 'BB', 50, 3.0, 'polar', 'QJo')['recommended'])

    def test_suited_fraca_dominada_so_folda_vs_linear(self):
        # K9s em size normal: fold vs linear (dominada), call vs polar.
        self.assertEqual('fold', vd.advise('UTG', 'HJ', 60, 3.0, 'linear', 'K9s')['recommended'])
        self.assertEqual('call', vd.advise('HJ', 'BTN', 60, 3.0, 'polar', 'K9s')['recommended'])


class RegraOuroPosicao(unittest.TestCase):
    """Regra 3: IP defende mais largo que OOP (mesma mão/range)."""

    def test_offsuit_broadway_ip_call_oop_fold_vs_polar(self):
        # QTo vs polar: call IP, fold OOP.
        ip = vd.advise('BTN', 'BB', 50, 3.0, 'polar', 'QTo')     # BTN > BB -> IP
        oop = vd.advise('CO', 'BTN', 50, 3.0, 'polar', 'QTo')    # CO < BTN -> OOP
        self.assertEqual('call', ip['recommended'])
        self.assertEqual('fold', oop['recommended'])

    def test_is_ip_deriva_da_ordem(self):
        self.assertTrue(vd.is_ip('BTN', 'BB'))
        self.assertFalse(vd.is_ip('CO', 'BTN'))
        self.assertFalse(vd.is_ip('UTG', 'UTG'))   # empate -> OOP (conservador)


class JamPairDinamica(unittest.TestCase):
    """Pares: jam vs polar curto (fold equity); flat/não-jam vs TG-vs-TG (vilão paga curto)."""

    def test_par_jam_vs_polar_curto_mas_flat_tg_vs_tg(self):
        self.assertEqual('jam', vd.advise('BTN', 'BB', 40, 3.0, 'polar', '22')['recommended'])
        self.assertEqual('call', vd.advise('UTG', 'UTG', 45, 3.0, 'linear', '77')['recommended'])

    def test_par_deep_nunca_folda(self):
        self.assertEqual('call', vd.advise('UTG', 'HJ', 70, 3.0, 'linear', '55')['recommended'])


if __name__ == '__main__':
    unittest.main()
