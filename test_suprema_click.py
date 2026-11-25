"""TRAVA do executor de clique da Suprema (offline): resolve o alvo do plano, respeita o
DRY-RUN (nao clica) e, armado, clica a coord certa — tudo SEM janela real (client_rect_screen
monkeypatchado) e SEM clicar de verdade (mover injetado)."""
import unittest

import suprema_click as C
import suprema_act as A


class ResolveTarget(unittest.TestCase):
    def test_raise_vai_pro_botao_aumentar(self):
        act, frac = C.resolve_target({'action': A.RAISE, 'chips': 1500, 'preset': '3X'})
        self.assertEqual(act, A.RAISE)
        self.assertEqual(frac, C.BUTTON_LAYOUT[A.RAISE])

    def test_fold_check_call(self):
        self.assertEqual(C.resolve_target({'action': A.FOLD})[1], C.BUTTON_LAYOUT[A.FOLD])
        self.assertEqual(C.resolve_target({'action': A.CHECK})[1], C.BUTTON_LAYOUT[A.CHECK])
        self.assertEqual(C.resolve_target({'action': A.CALL})[1], C.BUTTON_LAYOUT[A.CALL])

    def test_wait_e_abstain_sem_alvo(self):
        self.assertEqual(C.resolve_target({'action': A.WAIT}), (A.WAIT, None))
        self.assertEqual(C.resolve_target({'action': A.ABSTAIN}), (A.ABSTAIN, None))


class BuildSequence(unittest.TestCase):
    def test_fold_um_clique(self):
        self.assertEqual(C.build_sequence({'action': A.FOLD}), [C.BUTTON_LAYOUT[A.FOLD]])

    def test_raise_com_preset_3_cliques(self):
        seq = C.build_sequence({'action': A.RAISE, 'preset': '3X'})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['3X'], C.PRESET_LAYOUT['confirm']])

    def test_raise_sem_preset_so_abre_e_confirma(self):
        seq = C.build_sequence({'action': A.RAISE})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['confirm']])

    def test_all_in_abre_allin_confirma(self):
        seq = C.build_sequence({'action': A.ALL_IN})
        self.assertEqual(seq, [C.BUTTON_LAYOUT[A.RAISE], C.PRESET_LAYOUT['all_in'], C.PRESET_LAYOUT['confirm']])

    def test_wait_vazio(self):
        self.assertEqual(C.build_sequence({'action': A.WAIT}), [])


class Execute(unittest.TestCase):
    def setUp(self):
        self._orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (100, 50, 500, 900)   # janela fake

    def tearDown(self):
        C.client_rect_screen = self._orig

    @staticmethod
    def _expected(frac):
        return (int(100 + frac[0] * 500), int(50 + frac[1] * 900))

    def test_dry_run_nao_clica(self):
        out = C.execute({'action': A.FOLD}, hwnd=1, armed=False)
        self.assertFalse(out['clicked'])
        self.assertEqual(out['reason'], 'DRY_RUN')
        self.assertEqual(out['screen'], [self._expected(C.BUTTON_LAYOUT[A.FOLD])])

    def test_armado_raise_sequencia(self):
        cliques = []
        out = C.execute({'action': A.RAISE, 'preset': '2X'}, hwnd=1, armed=True,
                        mover=lambda x, y: cliques.append((x, y)), sleeper=lambda s: None)
        self.assertTrue(out['clicked'])
        self.assertEqual(cliques, [self._expected(C.BUTTON_LAYOUT[A.RAISE]),
                                   self._expected(C.PRESET_LAYOUT['2X']),
                                   self._expected(C.PRESET_LAYOUT['confirm'])])

    def test_sem_alvo_nao_clica(self):
        cliques = []
        out = C.execute({'action': A.WAIT}, hwnd=1, armed=True, mover=lambda x, y: cliques.append((x, y)))
        self.assertFalse(out['clicked'])
        self.assertIn('SEM_ALVO', out['reason'])
        self.assertEqual(cliques, [])


class TileGeometry(unittest.TestCase):
    """Geometria das N mesas tiladas numa única janela (aritmética pura, sem janela real)."""

    def test_uma_mesa_igual_table_rect_screen(self):
        # n_rooms<=1 == modo de 1 mesa (retrato ancorado à direita = table_rect_screen).
        left, top, w, h = 100, 50, 1249, 1110
        tw = min(w, int(round(h * C.TABLE_ASPECT)))
        self.assertEqual(C._tile_rect(left, top, w, h, 0, 1),
                         (left + (w - tw), top, tw, h))
        # client estreito (retrato puro): mesa = client inteiro.
        self.assertEqual(C._tile_rect(100, 50, 500, 900, 0, 1), (100, 50, 500, 900))

    def test_duas_mesas_lado_a_lado_metade_da_largura(self):
        # Client multi-mesa real ~1249x1110: 2 colunas, cada metade ~= retrato 9:16.
        left, top, w, h = 0, 0, 1249, 1110
        r0 = C._tile_rect(left, top, w, h, 0, 2)
        r1 = C._tile_rect(left, top, w, h, 1, 2)
        # cada mesa ~ metade da largura
        self.assertAlmostEqual(r0[2], w / 2, delta=2)
        self.assertAlmostEqual(r1[2], w / 2, delta=2)
        # altura cheia, mesma de ambas
        self.assertEqual(r0[3], h)
        self.assertEqual(r1[3], h)
        # lado a lado: a 2ª começa ~ na metade; sem sobreposição
        self.assertAlmostEqual(r1[0], w / 2, delta=2)
        self.assertLessEqual(r0[0] + r0[2], r1[0] + 2)
        # cada coluna é ~ retrato (largura/altura ~ TABLE_ASPECT)
        self.assertAlmostEqual(r0[2] / r0[3], C.TABLE_ASPECT, delta=0.01)

    def test_fracao_cai_na_mesa_certa(self):
        # fold (fx=0.185) na mesa 0 cai na metade ESQUERDA; na mesa 1, na metade DIREITA.
        C_orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (0, 0, 1249, 1110)
        try:
            x0, _ = C.frac_to_screen_room(1, 0.185, 0.95, 0, 2)
            x1, _ = C.frac_to_screen_room(1, 0.185, 0.95, 1, 2)
            self.assertLess(x0, 1249 / 2)     # mesa 0 -> esquerda
            self.assertGreater(x1, 1249 / 2)  # mesa 1 -> direita
        finally:
            C.client_rect_screen = C_orig

    def test_indice_fora_do_range_clampa(self):
        left, top, w, h = 0, 0, 1200, 1100
        self.assertEqual(C._tile_rect(left, top, w, h, 9, 2),
                         C._tile_rect(left, top, w, h, 1, 2))
        self.assertEqual(C._tile_rect(left, top, w, h, -3, 2),
                         C._tile_rect(left, top, w, h, 0, 2))

    def test_colunas_nao_se_sobrepoem_n3(self):
        left, top, w, h = 0, 0, 1800, 1100
        rects = [C._tile_rect(left, top, w, h, i, 3) for i in range(3)]
        for a, b in zip(rects, rects[1:]):
            self.assertLessEqual(a[0] + a[2], b[0] + 2)   # fim da coluna i <= início da i+1

    def test_execute_roteia_para_a_mesa_certa(self):
        # armado, com room_index, o clique de FOLD sai na coluna certa (mesa 0 esq, mesa 1 dir).
        C_orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (0, 0, 1249, 1110)
        try:
            c0, c1 = [], []
            C.execute({'action': A.FOLD}, hwnd=1, armed=True, room_index=0, n_rooms=2,
                      mover=lambda x, y: c0.append((x, y)))
            C.execute({'action': A.FOLD}, hwnd=1, armed=True, room_index=1, n_rooms=2,
                      mover=lambda x, y: c1.append((x, y)))
            self.assertLess(c0[0][0], 1249 / 2)
            self.assertGreater(c1[0][0], 1249 / 2)
        finally:
            C.client_rect_screen = C_orig

    def test_execute_default_igual_1_mesa(self):
        # sem room params (default 0/1) o dry-run é idêntico ao de 1 mesa.
        C_orig = C.client_rect_screen
        C.client_rect_screen = lambda hwnd: (100, 50, 500, 900)
        try:
            a = C.execute({'action': A.FOLD}, hwnd=1, armed=False)
            b = C.execute({'action': A.FOLD}, hwnd=1, armed=False, room_index=0, n_rooms=1)
            self.assertEqual(a['screen'], b['screen'])
        finally:
            C.client_rect_screen = C_orig


class TileGeometryExhaustive(unittest.TestCase):
    """Varre n=1..4 e TODO room_index em janelas BEM-FORMADAS (w = n * h*aspect): cada mesa cai
    DENTRO da janela, colunas contíguas e sem sobreposição, aspecto retrato, e a fração (0.5,0.5)
    cai no CENTRO da coluna da mesa certa; mesas adjacentes não colidem."""

    HEIGHTS = (900, 1110, 1307, 1509, 2029)

    def _rects(self, w, h, n):
        return [C._tile_rect(0, 0, w, h, i, n) for i in range(n)]

    def test_todas_as_mesas_dentro_contiguas_retrato_centradas(self):
        A = C.TABLE_ASPECT
        for h in self.HEIGHTS:
            for n in (1, 2, 3, 4):
                w = int(round(n * h * A))                  # janela = N retratos lado a lado
                rects = self._rects(w, h, n)
                for i, (x, y, tw, th) in enumerate(rects):
                    # dentro da janela
                    self.assertGreaterEqual(x, 0, (h, n, i))
                    self.assertLessEqual(x + tw, w + 2, (h, n, i))
                    self.assertEqual(y, 0)
                    self.assertEqual(th, h)
                    # aspecto retrato tw ≈ th*aspect
                    self.assertAlmostEqual(tw / th, A, delta=0.02, msg=(h, n, i))
                    # centro da fração (0.5) cai no centro da coluna i
                    cx = x + 0.5 * tw
                    self.assertAlmostEqual(cx, (i + 0.5) * (w / n), delta=3, msg=(h, n, i))
                # colunas contíguas e sem sobreposição (fim da i <= início da i+1)
                for a, b in zip(rects, rects[1:]):
                    self.assertLessEqual(a[0] + a[2], b[0] + 2, (h, n))

    def test_frac_meio_cai_na_coluna_da_mesa_certa(self):
        # Para n=1..4, (0.5,0.5) de cada mesa cai na coluna DELA (e em nenhuma outra).
        A = C.TABLE_ASPECT
        for n in (1, 2, 3, 4):
            h = 1307
            w = int(round(n * h * A))
            C_orig = C.client_rect_screen
            C.client_rect_screen = lambda hwnd, _w=w, _h=h: (0, 0, _w, _h)
            try:
                for i in range(n):
                    x, _ = C.frac_to_screen_room(1, 0.5, 0.5, i, n)
                    col_lo, col_hi = i * (w / n), (i + 1) * (w / n)
                    self.assertGreaterEqual(x, col_lo - 1, (n, i))
                    self.assertLessEqual(x, col_hi + 1, (n, i))
            finally:
                C.client_rect_screen = C_orig

    def test_uma_mesa_identico_table_rect_screen_todos_tamanhos(self):
        # n_rooms<=1 NUNCA pode divergir de table_rect_screen (1 mesa, retrato à direita).
        for h in self.HEIGHTS:
            for w in (int(round(h * C.TABLE_ASPECT)), 1470, 849):
                C_orig = C.client_rect_screen
                C.client_rect_screen = lambda hwnd, _w=w, _h=h: (100, 50, _w, _h)
                try:
                    self.assertEqual(C.table_rect_for_room(1, 0, 1), C.table_rect_screen(1))
                    self.assertEqual(C.table_rect_for_room(1, 0, 0), C.table_rect_screen(1))
                finally:
                    C.client_rect_screen = C_orig

    def test_bg_client_room_dentro_da_coluna(self):
        # caminho de BACKGROUND (coords de CLIENTE) também roteia para a coluna certa.
        w, h, n = 1470, 1307, 2
        orig = C.client_wh
        C.client_wh = lambda hwnd: (w, h)
        try:
            cx0, _ = C.frac_to_client_room(1, 0.5, 0.5, 0, n)
            cx1, _ = C.frac_to_client_room(1, 0.5, 0.5, 1, n)
            self.assertLess(cx0, w / 2)
            self.assertGreater(cx1, w / 2)
        finally:
            C.client_wh = orig


class ColumnsFromSize(unittest.TestCase):
    """columns_from_size/window: dedução da contagem de colunas pela JANELA (verdade-terreno)."""

    def test_tamanhos_conhecidos(self):
        casos = [
            (1470, 1307, 2),   # janela de hoje -> 2 mesas
            (849, 1509, 1),    # retrato puro -> 1 mesa
            (2940, 1307, 4),   # 4 de largura -> 4 mesas
            (1249, 1110, 2),   # client multi-mesa real -> 2
            (2206, 1307, 3),   # 3 colunas
            (735, 1307, 1),    # 1 retrato exato
        ]
        for w, h, exp in casos:
            self.assertEqual(C.columns_from_size(w, h), exp, (w, h))

    def test_janelas_bem_formadas_1_a_4(self):
        for h in (900, 1110, 1307, 1509, 2029):
            for n in (1, 2, 3, 4):
                w = int(round(n * h * C.TABLE_ASPECT))
                self.assertEqual(C.columns_from_size(w, h), n, (w, h, n))

    def test_clamp_minimo_1(self):
        self.assertEqual(C.columns_from_size(10, 2000), 1)     # janela muito estreita
        self.assertEqual(C.columns_from_size(0, 1000), 1)
        self.assertGreaterEqual(C.columns_from_size(300, 1509), 1)

    def test_degenerado_devolve_1(self):
        self.assertEqual(C.columns_from_size(1470, 0), 1)       # h=0
        self.assertEqual(C.columns_from_size(1470, 1307, 0), 1)  # aspect=0
        self.assertEqual(C.columns_from_size(None, None), 1)     # não-numérico

    def test_columns_from_window_le_o_client(self):
        orig = C.client_wh
        C.client_wh = lambda hwnd: (2940, 1307)
        try:
            self.assertEqual(C.columns_from_window(1), 4)
        finally:
            C.client_wh = orig

    def test_columns_from_window_degenerado(self):
        orig = C.client_wh
        C.client_wh = lambda hwnd: (0, 0)
        try:
            self.assertEqual(C.columns_from_window(1), 1)
        finally:
            C.client_wh = orig


if __name__ == '__main__':
    unittest.main()
