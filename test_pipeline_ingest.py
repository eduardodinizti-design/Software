"""Testes do pipeline_ingest: a camada de VALIDACAO tem que REJEITAR o no que
quebrou o cerebro antes (freq que nao soma 1 por classe; AA que nao jamma num spot
de shove), e ACEITAR o no limpo."""
import unittest

import hrc_ingest
import pipeline_ingest as pi


def _node(spot, freq, stack=12, hero='BTN', vs=('CO',)):
    return dict(id='t', context=dict(mode='icm', format='regular', stage='bubble',
                                      players=9, stack=stack),
                spot=spot, hero=hero, vs=list(vs), spread='iguais',
                validated=False, evUnit='bb', actions=list(freq), freq=freq)


def _col(val):
    return [val] * 169


class ValidateNode(unittest.TestCase):
    def test_accepts_clean_binary_jam(self):
        iaa = hrc_ingest.HANDS.index('AA')
        allin = _col(0.0); fold = _col(1.0)
        allin[iaa] = 1.0; fold[iaa] = 0.0            # AA jamma, resto folda (soma 1)
        ok, why = pi.validate_node(_node('open_shove', {'all_in': allin, 'fold': fold}))
        self.assertTrue(ok, why)

    def test_rejects_sum_not_one(self):
        # all_in=0.43, fold=0.0 -> soma 0.43 (massa de call descartada = o BUG real)
        ok, why = pi.validate_node(_node('vs_open_shove',
                                         {'all_in': _col(0.43), 'fold': _col(0.0)}))
        self.assertFalse(ok)
        self.assertIn('SOMA_CLASSE', why)

    def test_rejects_aa_not_jamming_in_shove(self):
        iaa = hrc_ingest.HANDS.index('AA')
        allin = _col(1.0); fold = _col(0.0)
        allin[iaa] = 0.0; fold[iaa] = 1.0            # AA NAO jamma (soma 1, mas absurdo)
        ok, why = pi.validate_node(_node('3bet_shove', {'all_in': allin, 'fold': fold}))
        self.assertFalse(ok)
        self.assertIn('AA_NAO_JAMMA', why)

    def test_rejects_bad_bucket_and_hero(self):
        ok, _ = pi.validate_node(_node('open_shove', {'all_in': _col(1.0), 'fold': _col(0.0)}, stack=37))
        self.assertFalse(ok)
        ok, _ = pi.validate_node(_node('open_shove', {'all_in': _col(1.0), 'fold': _col(0.0)}, hero='XX'))
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
