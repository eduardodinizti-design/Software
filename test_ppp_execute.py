"""TRAVA do clicker PPPoker: resolve_click (puro) + make_execute single-click (IO injetado).
Offline: sem tela, sem cursor real, sem rede."""
import unittest

import ppp_execute as X


def _row(*actions, status='EXPERIMENTAL_BUTTON_ROW'):
    """button_row no formato do read_action_buttons: cada ação com um box fake distinto."""
    boxes = {'FOLD': [10, 500, 80, 40], 'CHECK': [110, 500, 80, 40],
             'CALL': [110, 500, 80, 40], 'RAISE': [210, 500, 80, 40], 'BET': [210, 500, 80, 40]}
    return {'status': status,
            'buttons': [{'action': a, 'box': boxes[a], 'label': a} for a in actions]}


class ResolveClick(unittest.TestCase):
    def test_fold_de_graca_vira_check_meio(self):
        r = X.resolve_click('fold', _row('FOLD', 'CHECK', 'RAISE'), to_call_bb=0.0)
        self.assertEqual((r['kind'], r['action'], r['slot']), ('single', 'CHECK', 1))
        self.assertEqual(r['box'], [110, 500, 80, 40])   # meio

    def test_fold_vs_aposta_folda_slot0(self):
        r = X.resolve_click('fold', _row('FOLD', 'CALL', 'RAISE'), to_call_bb=2.0)
        self.assertEqual((r['action'], r['slot'], r['box']), ('FOLD', 0, [10, 500, 80, 40]))

    def test_call_meio(self):
        r = X.resolve_click('call', _row('FOLD', 'CALL', 'RAISE'), to_call_bb=2.0)
        self.assertEqual((r['action'], r['slot'], r['box']), ('CALL', 1, [110, 500, 80, 40]))

    def test_check_meio_de_graca(self):
        r = X.resolve_click('check', _row('FOLD', 'CHECK', 'RAISE'), to_call_bb=0.0)
        self.assertEqual((r['action'], r['slot']), ('CHECK', 1))

    def test_raise_multistep(self):
        r = X.resolve_click('raise', _row('FOLD', 'CALL', 'RAISE'), to_call_bb=2.0)
        self.assertEqual(r['kind'], 'multistep')
        self.assertIn('REQUIRES_SIZING_MULTISTEP', r['caveats'])

    def test_all_in_multistep(self):
        self.assertEqual(X.resolve_click('all_in', _row('FOLD', 'CALL', 'RAISE'))['kind'], 'multistep')

    def test_label_free_resolve_por_slot(self):
        # CASO REAL 4K: botões SEM rótulo (OCR falhou -> action=None), mas as CAIXAS existem.
        row = {'status': 'EXPERIMENTAL_BUTTON_ROW', 'buttons': [
            {'action': None, 'box': [10, 500, 80, 40]},
            {'action': None, 'box': [110, 500, 80, 40]},
            {'action': None, 'box': [210, 500, 80, 40]}]}
        r = X.resolve_click('call', row, to_call_bb=3.0)
        self.assertEqual((r['kind'], r['slot'], r['box']), ('single', 1, [110, 500, 80, 40]))

    def test_check_com_aposta_e_inconsistente(self):
        r = X.resolve_click('check', _row('FOLD', 'CALL', 'RAISE'), to_call_bb=5.0)
        self.assertEqual((r['kind'], r['reason']), ('none', 'INCONSISTENTE_CHECK_COM_APOSTA'))

    def test_num_botoes_invalido_abstem(self):
        self.assertEqual(X.resolve_click('call', _row('FOLD'), to_call_bb=2.0)['kind'], 'none')

    def test_sem_button_row(self):
        self.assertEqual(X.resolve_click('fold', {'status': 'NO_BUTTON_ROW'})['kind'], 'none')


class _Adapter:
    def __init__(self):
        self.moves, self.clicks = [], []

    def move_to(self, x, y, bounds=None):
        self.moves.append((x, y))

    def click_once(self, x=None, y=None, bounds=None, hold_s=None):
        self.clicks.append((x, y))


def _to_screen(box, *, window_rect, frame_size):
    """Mapeamento trivial p/ teste: janela == frame (1:1), origem (0,0)."""
    x, y, w, h = box
    return (x, y, w, h)


def _view(origin=(0, 0)):
    """VIEW no formato do ppp_grab.build_view (crop é irrelevante: read_buttons é fake)."""
    return {'crop': object(), 'origin': origin, 'window_rect': (0, 0, 1600, 1000),
            'full_size': (1600, 1000)}


class MakeExecute(unittest.TestCase):
    def _exec(self, *, view=None, on_sizing=None, buttons=('FOLD', 'CALL', 'RAISE')):
        ad = _Adapter()
        ex = X.make_execute(
            hwnd=1, adapter=ad,
            grab_frame=lambda tk, h: (view if view is not None else _view()),
            read_buttons=lambda crop: _row(*buttons),
            to_screen=_to_screen, on_sizing=on_sizing, log=lambda *a, **k: None)
        return ex, ad

    def test_single_click_call_clica_no_centro(self):
        ex, ad = self._exec()
        res = ex({'recommended': 'call'}, 'm', {})
        self.assertEqual((res['state'], res['action']), ('CLICKED', 'CALL'))
        # box CALL = [110,500,80,40], origin (0,0) -> centro (150,520)
        self.assertEqual(ad.clicks, [(150, 520)])
        self.assertEqual(ad.moves, [(150, 520)])

    def test_offset_do_crop_e_somado(self):
        # crop deslocado (200,100) na janela: botão CALL [110,500,..] -> (310,600,80,40) -> centro (350,620)
        ex, ad = self._exec(view=_view(origin=(200, 100)))
        res = ex({'recommended': 'call'}, 'm', {})
        self.assertEqual(ad.clicks, [(350, 620)])

    def test_raise_sem_sizing_nao_clica(self):
        ex, ad = self._exec()
        res = ex({'recommended': 'raise'}, 'm', {})
        self.assertEqual(res['state'], 'SIZING_NAO_PLUGADO')
        self.assertEqual(ad.clicks, [])                 # nunca mis-clica um raise

    def test_raise_com_sizing_delega(self):
        chamado = []
        ex, ad = self._exec(on_sizing=lambda p, tk, e, br, view=None:
                            chamado.append((p['recommended'], view is not None)) or {'state': 'SIZED'})
        res = ex({'recommended': 'raise'}, 'm', {})
        self.assertEqual(res['state'], 'SIZED')
        self.assertEqual(chamado, [('raise', True)])    # recebeu a view (crop) p/ localizar o painel
        self.assertEqual(ad.clicks, [])

    def test_sem_view_nao_clica(self):
        ad = _Adapter()
        ex = X.make_execute(hwnd=1, adapter=ad, grab_frame=lambda tk, h: None,
                            read_buttons=lambda crop: _row('FOLD', 'CALL'),
                            to_screen=_to_screen, log=lambda *a, **k: None)
        self.assertEqual(ex({'recommended': 'call'}, 'm', {})['state'], 'NO_VIEW')
        self.assertEqual(ad.clicks, [])


if __name__ == '__main__':
    unittest.main()
