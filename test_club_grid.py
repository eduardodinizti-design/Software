"""Grade de clubes: limpeza/match de nome (com ruído REAL do OCR) e navegação
rolar-e-buscar (ordem muda, grade rola). Lógica pura; OCR do gabarito é guardado."""
import os
import unittest

from club_grid import clean_club_name, match_club, normalize, ClubGridNavigator


class CleanNameTests(unittest.TestCase):
    def test_ruido_real_do_ocr(self):
        # strings exatamente como o OCR leu o gabarito club-grid-live-1.png
        self.assertEqual(clean_club_name('AK AMAKHA cl...'), ('AK AMAKHA cl', True))
        self.assertEqual(clean_club_name(') Karekas Yellow'), ('Karekas Yellow', False))
        self.assertEqual(clean_club_name('LALINHA�'), ('LALINHA', False))
        self.assertEqual(clean_club_name(') AK Amakha Club'), ('AK Amakha Club', False))

    def test_vazio(self):
        self.assertEqual(clean_club_name(None), ('', False))
        self.assertEqual(clean_club_name('   '), ('', False))


class MatchTests(unittest.TestCase):
    def test_exato_insensivel(self):
        m = match_club('karekas yellow', [') Karekas Yellow', 'LALINHA�'])
        self.assertEqual(m['index'], 0)
        self.assertEqual(m['reason'], 'EXATO')

    def test_prefixo_truncado(self):
        # tile mostra "AK AMAKHA cl..."; alvo é o nome completo
        m = match_club('AK AMAKHA Club 2', ['AK AMAKHA cl...', 'Karekas Yellow'])
        self.assertEqual(m['index'], 0)
        self.assertEqual(m['reason'], 'PREFIXO_TRUNCADO')

    def test_clubes_parecidos_sao_ambiguos(self):
        # dois tiles truncados IDÊNTICOS (ex.: "AK Amakha Club" e "...Club 2", ambos
        # cortados em "AK AMAKHA cl...") -> prefixo casa os dois -> não chuta.
        m = match_club('AK AMAKHA Club', ['AK AMAKHA cl...', 'AK AMAKHA cl...'])
        self.assertTrue(m['ambiguous'])
        self.assertEqual(m['reason'], 'PREFIXO_AMBIGUO')
        self.assertIsNone(m['index'])

    def test_nao_encontrado_e_alvo_vazio(self):
        self.assertEqual(match_club('Veneza', ['Karekas Yellow'])['reason'], 'NAO_ENCONTRADO')
        self.assertEqual(match_club('', ['Karekas Yellow'])['reason'], 'ALVO_VAZIO')


class _FakeGrid:
    """Simula a grade que ROLA e cuja ORDEM MUDA. `pages` = listas de nomes por
    tela; scroll avança a página. Clique registra o ponto."""
    def __init__(self, pages):
        self.pages = pages
        self.i = 0
        self.clicks = []

    def list_visible(self):
        page = self.pages[min(self.i, len(self.pages) - 1)]
        return [{'name': n, 'click': (100, 10 * j)} for j, n in enumerate(page)]

    def scroll(self):
        if self.i >= len(self.pages) - 1:
            return False
        self.i += 1
        return True

    def click(self, point):
        self.clicks.append(point)


class NavigatorTests(unittest.TestCase):
    def test_acha_na_primeira_tela(self):
        g = _FakeGrid([[') Karekas Yellow', 'LALINHA�']])
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll, click=g.click)
        r = nav.find_and_click('Karekas Yellow')
        self.assertTrue(r['ok'])
        self.assertEqual(r['scrolls'], 0)
        self.assertEqual(len(g.clicks), 1)

    def test_acha_apos_rolar(self):
        g = _FakeGrid([['Karekas Yellow', 'LALINHA'], ['AK Amakha Club', 'Veneza']])
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll, click=g.click)
        r = nav.find_and_click('Veneza')
        self.assertTrue(r['ok'])
        self.assertEqual(r['scrolls'], 1)

    def test_ordem_muda_nao_quebra(self):
        # alvo some da 1a tela e aparece reordenado na 2a — busca por nome aguenta
        g = _FakeGrid([['A', 'B'], ['C', 'Veneza', 'A']])
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll, click=g.click)
        self.assertTrue(nav.find_and_click('Veneza')['ok'])

    def test_fim_da_lista_nao_encontrado(self):
        g = _FakeGrid([['A', 'B'], ['C', 'D']])
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll, click=g.click)
        r = nav.find_and_click('Veneza')
        self.assertFalse(r['ok'])
        self.assertEqual(r['reason'], 'FIM_DA_LISTA')
        self.assertEqual(g.clicks, [])

    def test_ambiguo_para_sem_clicar(self):
        g = _FakeGrid([['AK AMAKHA cl...', 'AK AMAKHA cl...']])
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll, click=g.click)
        r = nav.find_and_click('AK AMAKHA Club')
        self.assertFalse(r['ok'])
        self.assertEqual(r['action'], 'AMBIGUO')
        self.assertEqual(g.clicks, [])

    def test_max_scrolls_respeitado(self):
        pages = [['x%d' % i, 'y%d' % i] for i in range(20)]   # sempre tem "próxima"
        g = _FakeGrid(pages)
        nav = ClubGridNavigator(list_visible=g.list_visible, scroll=g.scroll,
                                click=g.click, max_scrolls=3)
        r = nav.find_and_click('Veneza')
        self.assertEqual(r['reason'], 'MAX_SCROLLS')
        self.assertEqual(r['scrolls'], 3)


_FIX = os.path.join('tests', 'fixtures', 'club_grid', 'club-grid-live-1.png')


def _fixture():
    try:
        import cv2
        return cv2.imread(_FIX)
    except Exception:
        return None


def _ocr_ready():
    try:
        from table_reading.pipeline import configure_ocr
        return configure_ocr().get('status') == 'READY'
    except Exception:
        return False


@unittest.skipUnless(_fixture() is not None, 'cv2/gabarito indisponível')
class PillDetectionTests(unittest.TestCase):
    """Detecção da âncora (pílula verde) — só CV, não depende de Tesseract."""
    def test_detecta_seis_pilulas_em_duas_colunas(self):
        from club_grid import detect_club_pills
        pills = detect_club_pills(_fixture())
        self.assertEqual(len(pills), 6)                       # 2 col x 3 linhas visíveis
        cols = {'L' if px < 475 else 'R' for (px, _, _, _) in pills}
        self.assertEqual(cols, {'L', 'R'})                    # duas colunas
        # a barra do topo (larga) NÃO entra
        self.assertTrue(all(pw < 0.12 * _fixture().shape[1] for (_, _, pw, _) in pills))


@unittest.skipUnless(_fixture() is not None and _ocr_ready(),
                     'Tesseract/gabarito indisponível — leitura viva pulada')
class GridReadTests(unittest.TestCase):
    """Leitura completa (detecção + OCR + limpeza) sobre o gabarito real."""
    @staticmethod
    def _ocr():
        from table_reading.ocr_runtime import image_to_string
        return lambda g: image_to_string(g, config='--psm 7')

    def test_le_os_quatro_tiles_reais_com_clique(self):
        from club_grid import read_club_grid
        tiles = read_club_grid(_fixture(), ocr=self._ocr())
        names = [t['name'] for t in tiles]
        self.assertTrue(any(n.casefold().startswith('karekas') for n in names), names)
        self.assertTrue(any(n == 'AK Amakha Club' for n in names), names)
        self.assertTrue(any(t['truncated'] and t['name'].upper().startswith('AK')
                            for t in tiles), names)
        # Karekas está na coluna direita, linha de cima -> clique à direita e no topo
        kar = next(t for t in tiles if t['name'].casefold().startswith('karekas'))
        self.assertGreater(kar['click'][0], 450)
        self.assertLess(kar['click'][1], 650)

    def test_origin_desloca_o_clique(self):
        from club_grid import list_visible_from_crop
        base = list_visible_from_crop(_fixture(), ocr=self._ocr())
        off = list_visible_from_crop(_fixture(), ocr=self._ocr(), origin=(1000, 2000))
        self.assertTrue(base)
        self.assertEqual(off[0]['click'], (base[0]['click'][0] + 1000,
                                           base[0]['click'][1] + 2000))


def _embed_grid(ox, oy, cw=1700, ch=2100):
    """Cola o gabarito da grade (760x1415) num canvas preto maior — simula a janela
    cheia p/ testar o find_grid_crop sem versionar a captura de 5760x2160."""
    import numpy as np
    grid = _fixture()
    h, w = grid.shape[:2]
    canvas = np.zeros((ch, cw, 3), np.uint8)
    canvas[oy:oy + h, ox:ox + w] = grid
    return canvas


@unittest.skipUnless(_fixture() is not None, 'cv2/gabarito indisponível')
class FindGridCropTests(unittest.TestCase):
    """Auto-localização do painel da grade pela âncora das pílulas (só CV)."""
    def test_localiza_a_grade_num_canvas_maior(self):
        from club_grid import find_grid_crop
        ox, oy = 600, 350
        r = find_grid_crop(_embed_grid(ox, oy))
        self.assertTrue(r['ok'], r['reason'])
        self.assertEqual(len(r['pills']), 6)
        self.assertGreaterEqual(r['origin'][0], ox)        # painel à direita do embed
        self.assertLess(r['origin'][1], oy + 300)          # topo perto do embed-top

    def test_frame_preto_devolve_falso(self):
        import numpy as np
        from club_grid import find_grid_crop
        r = find_grid_crop(np.zeros((500, 500, 3), np.uint8))
        self.assertFalse(r['ok'])
        self.assertEqual(r['reason'], 'SEM_PILULAS')


@unittest.skipUnless(_fixture() is not None and _ocr_ready(),
                     'Tesseract/gabarito indisponível — mapeamento vivo pulado')
class FindGridCropOCRTests(unittest.TestCase):
    def test_clique_mapeia_para_coordenada_do_canvas(self):
        from table_reading.ocr_runtime import image_to_string
        from club_grid import find_grid_crop, list_visible_from_crop
        ocr = lambda g: image_to_string(g, config='--psm 7')
        ox, oy = 600, 350
        r = find_grid_crop(_embed_grid(ox, oy))
        self.assertTrue(r['ok'])
        vis = list_visible_from_crop(r['crop'], ocr=ocr, origin=r['origin'])
        kar = next(v for v in vis if v['name'].casefold().startswith('karekas'))
        # no recorte 760x1415 o clique do Karekas é ~(578,568); no canvas soma o offset
        self.assertAlmostEqual(kar['click'][0], ox + 578, delta=25)
        self.assertAlmostEqual(kar['click'][1], oy + 568, delta=25)


_INSIDE = os.path.join('tests', 'fixtures', 'lobby_live', 'karekas-lobby-live-1.png')


def _inside_fixture():
    try:
        import cv2
        return cv2.imread(_INSIDE)
    except Exception:
        return None


@unittest.skipUnless(_inside_fixture() is not None and _ocr_ready(),
                     'Tesseract/gabarito indisponível — verificação viva pulada')
class ReadCurrentClubTests(unittest.TestCase):
    """Verificação: ler o nome COMPLETO do clube no cabeçalho de dentro do clube."""
    def test_le_karekas_yellow_do_cabecalho(self):
        from table_reading.ocr_runtime import image_to_string
        from club_grid import read_current_club
        ocr = lambda g: image_to_string(g, config='--psm 7')
        self.assertEqual(read_current_club(_inside_fixture(), ocr=ocr), 'Karekas Yellow')

    def test_le_em_dois_aspectos_de_painel(self):
        # Regressão do bug 'arekas Yellow' (17/11): o crop do find_lobby_crop ao vivo
        # (839x1266) tem aspecto diferente do gabarito (1005x1787); o ROI deve ler o
        # nome COMPLETO (sem clipar o 'K') nos dois.
        import cv2
        from table_reading.ocr_runtime import image_to_string
        from club_grid import read_current_club
        ocr = lambda g: image_to_string(g, config='--psm 7')
        live = cv2.imread(os.path.join('tests', 'fixtures', 'lobby_live',
                                       'karekas-club-panel-live-3.png'))
        self.assertIsNotNone(live)
        self.assertEqual(read_current_club(live, ocr=ocr), 'Karekas Yellow')


if __name__ == '__main__':
    unittest.main()
