"""A4 — testes do contrato discreto do menu de aumento (plan_raise + verify)."""
import unittest

from raise_plan import plan_raise, verify_selected_preset

# presets do skin Karekas (fixture): 2x / 2.5x / 3x / 4x
PRESETS = [dict(box=[0, 0, 10, 10], label='2x', mult=2.0),
           dict(box=[20, 0, 10, 10], label='2.5x', mult=2.5),
           dict(box=[40, 0, 10, 10], label='3x', mult=3.0),
           dict(box=[60, 0, 10, 10], label='4x', mult=4.0)]


class PlanRaiseTests(unittest.TestCase):
    def test_preset_dentro_da_tolerancia(self):
        p = plan_raise(3.0, PRESETS)
        self.assertEqual(p['kind'], 'PRESET')
        self.assertEqual(p['expected_mult'], 3.0)
        self.assertEqual(p['label'], '3x')

    def test_preset_mais_proximo(self):
        p = plan_raise(2.6, PRESETS)            # entre 2.5 e 3 -> 2.5 (|0.1|<|0.4|)
        self.assertEqual(p['kind'], 'PRESET')
        self.assertEqual(p['expected_mult'], 2.5)

    def test_shove_acima_do_maior_preset(self):
        p = plan_raise(25.0, PRESETS,all_in=True)
        self.assertEqual(p['kind'], 'SHOVE')
        self.assertTrue(p['explicit_all_in'])

    def test_shove_sem_slider_vira_abstain(self):
        p = plan_raise(25.0, PRESETS, slider_available=False,all_in=True)
        self.assertEqual(p['kind'], 'ABSTAIN')
        self.assertEqual(p['reason'], 'SHOVE_SEM_SLIDER')

    def test_intermediario_sem_preset_abstem(self):
        # alvo BAIXO, longe de todos os presets (tol=max(0.5,0.2*alvo)=0.5) e NÃO é
        # shove -> abstém, não força o 2x nem shova. (1.2x: |2-1.2|=0.8>0.5)
        p = plan_raise(1.2, PRESETS)
        self.assertEqual(p['kind'], 'ABSTAIN')
        self.assertEqual(p['reason'], 'SEM_PRESET_NA_TOLERANCIA')

    def test_sem_alvo(self):
        p = plan_raise(None, PRESETS)
        self.assertEqual((p['kind'], p['reason']), ('ABSTAIN', 'SEM_ALVO'))

    def test_sem_preset_legivel(self):
        ilegiveis = [dict(box=[0, 0, 1, 1], label='??', mult=None)]
        p = plan_raise(3.0, ilegiveis)
        self.assertEqual((p['kind'], p['reason']), ('ABSTAIN', 'SEM_PRESET_LEGIVEL'))

    def test_lista_vazia(self):
        self.assertEqual(plan_raise(3.0, [])['reason'], 'SEM_PRESET_LEGIVEL')

    def test_normal_six_times_raise_does_not_become_allin(self):
        p=plan_raise(6.0,PRESETS)
        self.assertEqual(p['kind'],'ABSTAIN')
        self.assertEqual(p['reason'],'ALVO_FORA_DO_MENU_NAO_E_ALLIN')

    def test_explicit_shove_never_selects_a_nearby_preset(self):
        p=plan_raise(3.3,PRESETS,all_in=True)
        self.assertEqual(p['kind'],'SHOVE')

    def test_entrada_malformada_nao_quebra(self):
        p = plan_raise(3.0, [None, 'x', dict(mult=3.0, box=[0, 0, 1, 1], label='3x')])
        self.assertEqual(p['kind'], 'PRESET')   # ignora lixo, acha o 3x


class VerifySelectedPresetTests(unittest.TestCase):
    def test_ok_quando_preset_esperado_presente(self):
        ok, reason = verify_selected_preset(dict(presets=PRESETS), 3.0)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_barra_quando_preset_sumiu(self):
        panel = dict(presets=[p for p in PRESETS if p['mult'] != 3.0])  # sem o 3x
        ok, reason = verify_selected_preset(panel, 3.0)
        self.assertFalse(ok)
        self.assertEqual(reason, 'PRESET_ESPERADO_SUMIU')

    def test_barra_quando_painel_sem_preset(self):
        ok, reason = verify_selected_preset(dict(presets=[]), 3.0)
        self.assertFalse(ok)
        self.assertEqual(reason, 'PAINEL_SEM_PRESET')

    def test_barra_quando_painel_none(self):
        ok, reason = verify_selected_preset(None, 3.0)
        self.assertFalse(ok)
        self.assertEqual(reason, 'PAINEL_SEM_PRESET')

    def test_sem_alvo_esperado(self):
        ok, reason = verify_selected_preset(dict(presets=PRESETS), None)
        self.assertFalse(ok)
        self.assertEqual(reason, 'SEM_ALVO_ESPERADO')


if __name__ == '__main__':
    unittest.main()
