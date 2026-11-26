"""TRAVA do grab/crop da mesa PPPoker (item 1): filtra COMPLETE, single->VIEW, multi->abstém.
Offline (capture/detect/discover falsos)."""
import unittest

import numpy as np

import ppp_grab as G
from table_sticky_bind import StickyBinder


class _Crop:
    def __init__(self, box, status='COMPLETE_CANDIDATE'):
        self.box = box
        self.status = status


def _frame(w=3840, h=1440):
    f = np.zeros((h, w, 3), np.uint8)
    f[:] = (28, 60, 150)      # RGB azul = feltro PPPoker (passa no felt_check anti-oclusão)
    return f


def _green_frame(w=3840, h=1440):
    f = np.zeros((h, w, 3), np.uint8)
    f[:] = (30, 150, 60)      # RGB verde = feltro Suprema (oclusão -> felt_check reprova)
    return f


def _grab(crops, *, frame=None, rect=(-1280, 0, 3840, 1440)):
    fr = frame if frame is not None else _frame()
    return G.make_grab(
        hwnd=1,
        capture=lambda r: fr,                       # novo contrato: capture(rect) -> frame
        detect=lambda rgb, max_tables=6: list(crops),
        discover_rect=lambda hwnd: rect,
        log=lambda *a, **k: None)


class Grab(unittest.TestCase):
    def test_single_completa_vira_view(self):
        v = _grab([_Crop((2041, 87, 737, 1298))])('14802382', 1)
        self.assertIsNotNone(v)
        self.assertEqual(v['origin'], (2041, 87))
        self.assertEqual(v['box'], (2041, 87, 737, 1298))
        self.assertEqual(v['window_rect'], (-1280, 0, 3840, 1440))
        self.assertEqual(v['full_size'], (3840, 1440))
        self.assertEqual(v['crop'].shape, (1298, 737, 3))

    def test_completa_entre_ruido_uncertain_pega_a_completa(self):
        # caso REAL do setup do Eduardo: 1 COMPLETE + várias UNCERTAIN (UI parcial) -> usa a COMPLETE
        crops = [_Crop((2041, 87, 737, 1298), 'COMPLETE_CANDIDATE'),
                 _Crop((1333, 186, 644, 997), 'UNCERTAIN'),
                 _Crop((65, 323, 240, 338), 'UNCERTAIN')]
        v = _grab(crops)('x', 1)
        self.assertIsNotNone(v)
        self.assertEqual(v['box'], (2041, 87, 737, 1298))

    def test_multi_sem_resolvedor_abstem(self):
        crops = [_Crop((0, 0, 700, 1200)), _Crop((1000, 0, 700, 1200))]
        self.assertIsNone(_grab(crops)('x', 1))          # sem binding -> abstém (seguro)

    def test_multi_com_binding_pega_o_recorte_certo(self):
        # 2 mesas: pos0 (esq) = roomid 111, pos1 (dir) = roomid 222. Binding resolve pela posição.
        crops = [_Crop((0, 0, 700, 1200)), _Crop((1800, 0, 700, 1200))]
        fresh = ['111', '222']
        binder = StickyBinder(min_score=2)
        binder.observe(n_panels=2, fresh_roomids=fresh,
                       frame_binds={0: ('111', 3), 1: ('222', 3)})
        grab = G.make_grab(hwnd=1, capture=lambda r: _frame(), detect=lambda rgb, max_tables=6: list(crops),
                           discover_rect=lambda h: (-1280, 0, 3840, 1440),
                           resolve_crop_index=G.sticky_crop_resolver(binder, fresh),
                           log=lambda *a, **k: None)
        v222 = grab('222', 1)
        self.assertIsNotNone(v222)
        self.assertEqual(v222['box'], (1800, 0, 700, 1200))   # pegou a mesa da DIREITA (pos1=222)
        v111 = grab('111', 1)
        self.assertEqual(v111['box'], (0, 0, 700, 1200))      # e a da ESQUERDA (pos0=111)

    def test_multi_binding_incerto_abstem(self):
        crops = [_Crop((0, 0, 700, 1200)), _Crop((1800, 0, 700, 1200))]
        binder = StickyBinder(min_score=2)   # nada aprendido -> roomid_for = None p/ toda posição
        grab = G.make_grab(hwnd=1, capture=lambda r: _frame(), detect=lambda rgb, max_tables=6: list(crops),
                           discover_rect=lambda h: (0, 0, 3840, 1440),
                           resolve_crop_index=G.sticky_crop_resolver(binder, ['111', '222']),
                           log=lambda *a, **k: None)
        self.assertIsNone(grab('222', 1))    # binding incerto -> abstém, nunca clica a errada

    def test_so_uncertain_abstem(self):
        self.assertIsNone(_grab([_Crop((0, 0, 700, 1200), 'UNCERTAIN')])('x', 1))

    def test_sem_recorte_abstem(self):
        self.assertIsNone(_grab([])('x', 1))

    def test_sem_frame_abstem(self):
        grab = G.make_grab(hwnd=1, capture=lambda r: None, detect=lambda rgb, max_tables=6: [],
                           discover_rect=lambda h: (0, 0, 1, 1), log=lambda *a, **k: None)
        self.assertIsNone(grab('x', 1))

    def test_sem_rect_abstem(self):
        self.assertIsNone(_grab([_Crop((0, 0, 700, 1200))], rect=None)('x', 1))

    def test_captura_excecao_nao_lanca(self):
        def boom(r):
            raise RuntimeError('grab caiu')
        grab = G.make_grab(hwnd=1, capture=boom, detect=lambda rgb, max_tables=6: [],
                           discover_rect=lambda h: (0, 0, 1, 1), log=lambda *a, **k: None)
        self.assertIsNone(grab('x', 1))


class GrabTiles(unittest.TestCase):
    """grab DATA-driven por tile (roomid -> rect do IL2CPP -> crop). Sem vision, multi robusto."""
    WR = (-1280, 0, 3840, 1440)

    def _grab(self, tiles, *, rect=None):
        return G.make_grab_tiles(
            hwnd=1, tiles_source=lambda: tiles, capture=lambda r: _frame(),
            discover_rect=lambda h: (self.WR if rect is None else rect), log=lambda *a, **k: None)

    def test_roomid_vira_crop_do_tile(self):
        # tile na TELA (1800,0,700,1200); janela em x=-1280 -> no frame fica em x=1800-(-1280)=3080
        v = self._grab({'222': (1800, 0, 700, 1200)})('222', 1)
        self.assertIsNotNone(v)
        self.assertEqual(v['box'], (3080, 0, 700, 1200))
        self.assertEqual(v['crop'].shape, (1200, 700, 3))

    def test_sem_tile_p_roomid_abstem(self):
        self.assertIsNone(self._grab({'111': (0, 0, 700, 1200)})('999', 1))

    def test_tile_fora_do_frame_abstem(self):
        # tile em x de tela 9000 -> fora da janela -> abstém (nunca recorta fora)
        self.assertIsNone(self._grab({'222': (9000, 0, 700, 1200)})('222', 1))

    def test_sem_rect_da_janela_abstem(self):
        grab = G.make_grab_tiles(hwnd=1, tiles_source=lambda: {'222': (1800, 0, 700, 1200)},
                                 capture=lambda r: _frame(), discover_rect=lambda h: None,
                                 log=lambda *a, **k: None)
        self.assertIsNone(grab('222', 1))


class GrabProjection(unittest.TestCase):
    """Grab por PROJEÇÃO (readTilesScreen): roomid -> rect Unity -> frame -> recorte direto."""
    RENDER = [5760.0, 2160.0]
    # rect Unity REAL (WorldToScreenPoint, px físico) das 2 mesas do Eduardo:
    TILES = {'14802382': [2626, 741, 3377, 2077], '14802482': [3388, 747, 4139, 2083]}

    def test_conversao_unity_para_frame(self):
        # 14802382: fx=2626×0.667≈1751, fy=(2160-2077)×0.667≈55, w≈501, h≈891
        fx, fy, w, h = G.unity_rect_to_frame(self.TILES['14802382'], self.RENDER, (3840, 1440))
        self.assertEqual((fx, fy), (1750, 55))
        self.assertTrue(495 <= w <= 505 and 885 <= h <= 895)

    def test_grab_proj_recorta_por_roomid(self):
        grab = G.make_grab_proj(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                capture=lambda r: _frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                log=lambda *a, **k: None)
        v1 = grab('14802382', 1); v2 = grab('14802482', 1)
        self.assertIsNotNone(v1); self.assertIsNotNone(v2)
        self.assertNotEqual(v1['box'], v2['box'])          # mesas distintas (esq != dir)
        self.assertEqual(v1['box'][0], 1750)               # esquerda

    def test_grab_proj_oclusao_verde_abstem(self):
        grab = G.make_grab_proj(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                capture=lambda r: _green_frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                log=lambda *a, **k: None)
        self.assertIsNone(grab('14802382', 1))             # Suprema (verde) por cima -> abstém

    def test_grab_proj_roomid_desconhecido_abstem(self):
        grab = G.make_grab_proj(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                capture=lambda r: _frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                log=lambda *a, **k: None)
        self.assertIsNone(grab('999', 1))

    def test_grab_proj_sem_tiles_abstem(self):
        grab = G.make_grab_proj(hwnd=1, tiles_source=lambda: (None, {}),
                                capture=lambda r: _frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                log=lambda *a, **k: None)
        self.assertIsNone(grab('14802382', 1))


class GrabHybrid(unittest.TestCase):
    """Híbrido: projeção (identidade por roomid) + recorte COMPLETE (mesa inteira, com botões)."""
    RENDER = [5760.0, 2160.0]
    TILES = {'14802382': [2626, 741, 3377, 2077]}   # projeção ~ frame (1750,55,500,891)

    def test_overlap_frac(self):
        self.assertEqual(G._overlap_frac((0, 0, 100, 100), (0, 0, 100, 100)), 1.0)
        self.assertEqual(G._overlap_frac((0, 0, 100, 100), (200, 200, 50, 50)), 0.0)

    def test_best_overlap_escolhe_recorte_que_sobrepoe(self):
        proj = (1750, 55, 500, 891)
        crops = [_Crop((1680, 40, 700, 1170)),            # cobre a projeção (COMPLETE, mesa inteira)
                 _Crop((3000, 40, 700, 1170))]            # outra mesa, longe
        c, f = G.best_overlap_crop(proj, crops)
        self.assertEqual(c.box, (1680, 40, 700, 1170))
        self.assertGreater(f, 0.9)

    def test_hibrido_usa_recorte_completo_pelo_roomid(self):
        # a projeção (menor) casa o recorte COMPLETE (maior, com botões) por sobreposição
        grab = G.make_grab_hybrid(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                  capture=lambda r: _frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                  detect=lambda rgb, max_tables=6: [_Crop((1680, 40, 700, 1170)), _Crop((3000, 40, 700, 1170))],
                                  log=lambda *a, **k: None)
        v = grab('14802382', 1)
        self.assertIsNotNone(v)
        self.assertEqual(v['box'], (1680, 40, 700, 1170))   # recorte COMPLETO (não a projeção crua)

    def test_expand_box_cresce_pra_baixo(self):
        x, y, w, h = G.expand_box((1750, 55, 500, 891), (3840, 1440))
        self.assertLess(x, 1750)                 # alargou p/ esquerda
        self.assertGreater(x + w, 1750 + 500)    # e p/ direita
        self.assertGreater(y + h, 55 + 891 + 200)  # esticou bastante p/ BAIXO (botões)

    def test_hibrido_detect_falho_usa_projecao_expandida(self):
        # detect longe/0 -> sem sobreposição -> usa a projeção EXPANDIDA (ancorada no roomid)
        grab = G.make_grab_hybrid(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                  capture=lambda r: _frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                  detect=lambda rgb, max_tables=6: [],   # detect falhou
                                  log=lambda *a, **k: None)
        v = grab('14802382', 1)
        self.assertIsNotNone(v)
        self.assertLess(v['box'][0], 1750)       # é a projeção expandida (não a crua)

    def test_hibrido_oclusao_verde_abstem(self):
        grab = G.make_grab_hybrid(hwnd=1, tiles_source=lambda: (self.RENDER, self.TILES),
                                  capture=lambda r: _green_frame(), discover_rect=lambda h: (0, 0, 3840, 1440),
                                  detect=lambda rgb, max_tables=6: [_Crop((1680, 40, 700, 1170))],
                                  log=lambda *a, **k: None)
        self.assertIsNone(grab('14802382', 1))


class TilesOrderResolver(unittest.TestCase):
    """Binding data-driven por ORDEM world-x (readTiles2 v228): roomid -> rank -> recorte."""
    TILES = {'14802382': [-1.14, -1.52, 2.34, 4.66],    # esquerda
             '14802482': [2.35, -1.54, 5.83, 4.64]}      # direita

    def test_casa_roomid_ao_recorte_por_ordem(self):
        resolve = G.tiles_order_resolver(self.TILES)
        crops = [_Crop((100, 0, 700, 1200)), _Crop((1800, 0, 700, 1200))]   # esq, dir (por x)
        self.assertEqual(resolve('14802382', crops), 0)   # roomid da esquerda -> recorte 0
        self.assertEqual(resolve('14802482', crops), 1)   # roomid da direita  -> recorte 1

    def test_contagem_diverge_abstem(self):
        resolve = G.tiles_order_resolver(self.TILES)
        self.assertIsNone(resolve('14802382', [_Crop((0, 0, 700, 1200))]))  # 1 recorte, 2 mesas

    def test_roomid_desconhecido_abstem(self):
        resolve = G.tiles_order_resolver(self.TILES)
        crops = [_Crop((100, 0, 700, 1200)), _Crop((1800, 0, 700, 1200))]
        self.assertIsNone(resolve('999', crops))

    def test_sem_tiles_abstem(self):
        self.assertIsNone(G.tiles_order_resolver({})('x', [_Crop((0, 0, 1, 1))]))


class FeltOcclusion(unittest.TestCase):
    """Rede anti-oclusão: só feltro AZUL do PPPoker passa; verde (Suprema)/não-feltro abstém."""
    def test_azul_pppoker_passa(self):
        self.assertTrue(G.is_pppoker_felt(_frame(200, 200)))

    def test_verde_suprema_reprova(self):
        self.assertFalse(G.is_pppoker_felt(_green_frame(200, 200)))

    def test_crop_minusculo_falha_aberto(self):
        self.assertTrue(G.is_pppoker_felt(_frame(5, 5)))   # não avalia -> True (rede extra)

    def test_grab_abstem_se_recorte_ocluido_verde(self):
        # 1 mesa COMPLETE, mas o frame está VERDE (Suprema por cima) -> felt_check reprova -> abstém
        grab = G.make_grab(hwnd=1, capture=lambda r: _green_frame(), detect=lambda rgb, max_tables=6: [_Crop((100, 200, 400, 300))],
                           discover_rect=lambda h: (0, 0, 3840, 1440), log=lambda *a, **k: None)
        self.assertIsNone(grab('x', 1))

    def test_grab_passa_se_azul(self):
        grab = G.make_grab(hwnd=1, capture=lambda r: _frame(), detect=lambda rgb, max_tables=6: [_Crop((100, 200, 400, 300))],
                           discover_rect=lambda h: (0, 0, 3840, 1440), log=lambda *a, **k: None)
        self.assertIsNotNone(grab('x', 1))


class LoadTiles(unittest.TestCase):
    def test_formato_xywh(self):
        import json, os, tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.json')
            json.dump({'222': [1800, 0, 700, 1200]}, open(p, 'w'))
            self.assertEqual(G.load_tiles(p), {'222': (1800, 0, 700, 1200)})

    def test_formato_cantos_e_lista(self):
        import json, os, tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 't.json')
            # lista [{roomid, rect:[x0,y0,x1,y1]}] (cantos) -> converte p/ (x,y,w,h)
            json.dump([{'roomid': 222, 'rect': [1800, 0, 2500, 1200]}], open(p, 'w'))
            self.assertEqual(G.load_tiles(p), {'222': (1800, 0, 700, 1200)})

    def test_ausente_vazio(self):
        self.assertEqual(G.load_tiles('nao/existe.json'), {})


def _screen_frame(w=2560, h=1440, *, felt=(200, 240, 1000, 760)):
    """Frame do MONITOR PRINCIPAL: fundo escuro + um retângulo de FELTRO AZUL (a mesa). felt=(x,y,w,h)."""
    f = np.zeros((h, w, 3), np.uint8)
    f[:] = (10, 20, 15)                      # fundo escuro (wallpaper)
    x, y, fw, fh = felt
    f[y:y + fh, x:x + fw] = (28, 60, 150)    # RGB azul = feltro
    return f


class LocateTableByFelt(unittest.TestCase):
    def test_acha_o_blob_de_feltro_e_estende_pra_baixo(self):
        fr = _screen_frame(felt=(300, 200, 900, 800))     # feltro em (300,200) 900x800
        box = G.locate_table_by_felt(fr)
        self.assertIsNotNone(box)
        x, y, w, h = box
        self.assertLessEqual(abs(x - 300), 40)            # pegou o x do feltro (com respiro lateral)
        self.assertLessEqual(abs(y - 200), 20)            # topo do feltro
        self.assertGreater(y + h, 200 + 800)              # ESTENDEU pra baixo (barra de botões)
        self.assertLess(y + h, 1440 + 1)                  # clampado ao frame

    def test_sem_azul_devolve_none(self):
        fr = np.zeros((1440, 2560, 3), np.uint8)          # tela preta, sem feltro
        self.assertIsNone(G.locate_table_by_felt(fr))

    def test_blob_pequeno_demais_none(self):
        fr = _screen_frame(felt=(0, 0, 80, 80))           # mancha minúscula < min_area_frac
        self.assertIsNone(G.locate_table_by_felt(fr))


def _screen_frame_2(w=2560, h=1440):
    """Monitor principal com DUAS mesas (feltro): esquerda em x~200, direita em x~1400."""
    f = np.zeros((h, w, 3), np.uint8)
    f[:] = (10, 20, 15)
    f[200:1000, 200:1000] = (28, 60, 150)      # mesa ESQUERDA
    f[200:1000, 1400:2200] = (28, 60, 150)     # mesa DIREITA
    return f


class LocateTablesByFelt(unittest.TestCase):
    def test_acha_duas_mesas_ordenadas_por_x(self):
        boxes = G.locate_tables_by_felt(_screen_frame_2())
        self.assertEqual(len(boxes), 2)
        self.assertLess(boxes[0][0], boxes[1][0])        # ordenadas esquerda->direita
        self.assertLessEqual(abs(boxes[0][0] - 200), 40)
        self.assertLessEqual(abs(boxes[1][0] - 1400), 40)

    def test_uma_mesa_lista_unitaria(self):
        boxes = G.locate_tables_by_felt(_screen_frame(felt=(300, 200, 900, 800)))
        self.assertEqual(len(boxes), 1)


class GrabPrimaryMulti(unittest.TestCase):
    RENDER = [5760, 2160]
    # roomid A projeta à ESQUERDA (x menor), B à DIREITA -> ordem [A, B] casa [mesa esq, mesa dir]
    TILES = {'A': [1000, 200, 2000, 1800], 'B': [3200, 200, 4200, 1800]}

    def _grab(self, frame=None, tiles=None):
        fr = frame if frame is not None else _screen_frame_2()
        tl = tiles if tiles is not None else self.TILES
        return G.make_grab_primary_multi(
            tiles_source=lambda: (self.RENDER, tl), capture=lambda r: fr,
            rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)

    def test_binda_por_ordem_e_devolve_a_mesa_certa(self):
        grab = self._grab()
        va = grab('A'); vb = grab('B')
        self.assertIsNotNone(va); self.assertIsNotNone(vb)
        self.assertLess(va['origin'][0], vb['origin'][0])   # A=esquerda, B=direita
        self.assertEqual(va['window_rect'], (0, 0, 2560, 1440))   # identidade

    def test_abstem_se_contagem_nao_bate(self):
        # 2 mesas na tela, mas 3 roomids no tiles -> binding incerto -> None
        tiles3 = dict(self.TILES, C=[5000, 200, 5600, 1800])
        self.assertIsNone(self._grab(tiles=tiles3)('A'))

    def test_abstem_sem_tiles(self):
        self.assertIsNone(self._grab(tiles={})('A'))

    def test_roomid_desconhecido_abstem(self):
        self.assertIsNone(self._grab()('Z'))


class GrabPrimaryAuto(unittest.TestCase):
    def test_uma_mesa_usa_single(self):
        grab = G.make_grab_primary_auto(
            tiles_source=lambda: ([5760, 2160], {'A': [1000, 200, 2000, 1800]}),   # 1 roomid
            capture=lambda r: _screen_frame(felt=(300, 200, 900, 800)),
            rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        v = grab('A')
        self.assertIsNotNone(v)                        # single achou a maior mesa

    def test_duas_mesas_usa_multi_binding(self):
        grab = G.make_grab_primary_auto(
            tiles_source=lambda: ([5760, 2160], {'A': [1000, 200, 2000, 1800], 'B': [3200, 200, 4200, 1800]}),
            capture=lambda r: _screen_frame_2(), rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        va, vb = grab('A'), grab('B')
        self.assertIsNotNone(va); self.assertIsNotNone(vb)
        self.assertLess(va['origin'][0], vb['origin'][0])   # bindou por ordem (A esq, B dir)

    def test_sem_tiles_source_sempre_single(self):
        grab = G.make_grab_primary_auto(
            tiles_source=None, capture=lambda r: _screen_frame(felt=(300, 200, 900, 800)),
            rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        self.assertIsNotNone(grab('qualquer'))


class GrabPrimary(unittest.TestCase):
    def test_view_tem_mapeamento_IDENTIDADE(self):
        # o VIEW sai com window_rect=(0,0,w,h) e full_size=(w,h) -> rect_frame_to_screen é IDENTIDADE
        # (clique == coord do botão no frame). Esta é a TRAVA do fix de coordenada off-screen (25/11).
        from screen_coords import rect_frame_to_screen
        fr = _screen_frame(felt=(300, 200, 900, 800))
        grab = G.make_grab_primary(capture=lambda r: fr, detect=lambda rgb, max_tables=6: [],
                                   rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        v = grab()
        self.assertIsNotNone(v)
        self.assertEqual(v['window_rect'], (0, 0, 2560, 1440))
        self.assertEqual(v['full_size'], (2560, 1440))
        box = (v['origin'][0] + 50, v['origin'][1] + 10, 120, 60)   # um "botão" qualquer no frame
        sx, sy, sw, sh = rect_frame_to_screen(box, window_rect=v['window_rect'], frame_size=v['full_size'])
        self.assertEqual((int(sx), int(sy)), (box[0], box[1]))      # IDENTIDADE: tela == frame

    def test_usa_felt_locator_quando_detect_vazio(self):
        fr = _screen_frame(felt=(300, 200, 900, 800))
        grab = G.make_grab_primary(capture=lambda r: fr, detect=lambda rgb, max_tables=6: [],
                                   rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        v = grab()
        self.assertIsNotNone(v)                      # achou pela via do feltro, sem detect
        self.assertLessEqual(abs(v['origin'][0] - 300), 40)

    def test_abstem_sem_mesa(self):
        preta = np.zeros((1440, 2560, 3), np.uint8)
        grab = G.make_grab_primary(capture=lambda r: preta, detect=lambda rgb, max_tables=6: [],
                                   rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        self.assertIsNone(grab())

    def test_sem_frame_abstem(self):
        grab = G.make_grab_primary(capture=lambda r: None, detect=lambda rgb, max_tables=6: [],
                                   rect=(0, 0, 2560, 1440), log=lambda *a, **k: None)
        self.assertIsNone(grab())


if __name__ == '__main__':
    unittest.main()
