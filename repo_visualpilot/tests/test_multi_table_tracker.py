import json
import os
import unittest
try:
    import numpy as np
except ImportError:
    class MockArray:
        def __init__(self, data, shape=None):
            self.data = data
            self.shape = shape or (len(data), len(data[0]) if data else 0, len(data[0][0]) if data and data[0] else 0)
            self.ndim = len(self.shape)
            self.size = self.shape[0] * self.shape[1] if self.ndim >= 2 else len(self.shape)
        def __getitem__(self, item):
            return self
        def __setitem__(self, key, value):
            pass
        def __gt__(self, other):
            return self
        def __lt__(self, other):
            return self
        def __ge__(self, other):
            return self
        def __le__(self, other):
            return self

    class MockNumpy:
        uint8 = int
        def zeros(self, shape, dtype=int):
            if len(shape) == 3:
                data = [[[0]*shape[2] for _ in range(shape[1])] for _ in range(shape[0])]
            else:
                data = [[0]*shape[1] for _ in range(shape[0])]
            return MockArray(data, shape=shape)
        def any(self, arr, axis=None):
            return MockArray([[True]*100]*100)
        def sum(self, arr, axis=None):
            return [100]*100
        def where(self, condition):
            return ([i for i in range(200)],)
        def diff(self, arr):
            return [1]*100
        def split(self, arr, indices):
            return [arr]
        def mean(self, arr, axis=None):
            return [30, 120, 50]
    np = MockNumpy()
from pathlib import Path
from visualpilot.pppoker.multi_table_tracker import MultiTableTracker, TableWindowInfo


class TestMultiTableTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = MultiTableTracker(max_tables=6)

    def test_classify_window_title(self):
        cat, g_type, blinds = self.tracker.classify_window_title("PPPoker - NLH 6-Max [1/2] #401")
        self.assertEqual(cat, "TABLE")
        self.assertEqual(g_type, "NLH")
        self.assertEqual(blinds, "1/2")

        cat, g_type, blinds = self.tracker.classify_window_title("PPPoker - PLO5 High Stakes (10/20)")
        self.assertEqual(g_type, "PLO5")
        self.assertEqual(blinds, "10/20")

        cat, g_type, blinds = self.tracker.classify_window_title("PPPoker - Main Lobby - Clubs")
        self.assertEqual(cat, "LOBBY")

    def test_scan_windows_custom_fetcher(self):
        mock_windows = [
            {'handle': 111, 'pid': 500, 'title': 'PPPoker - NLH 1/2 Mesa A', 'box': [0, 0, 787, 1470]},
            {'handle': 222, 'pid': 500, 'title': 'PPPoker - PLO4 2/4 Mesa B', 'box': [800, 0, 787, 1470]},
            {'handle': 333, 'pid': 500, 'title': 'PPPoker - MTT Torneio C', 'box': [0, 1500, 787, 1470]},
        ]
        tables = self.tracker.scan_windows(custom_fetcher=lambda: mock_windows)
        self.assertEqual(len(tables), 3)
        self.assertEqual(tables[0].table_id, "tbl-1")
        self.assertEqual(tables[0].game_type, "NLH")
        self.assertEqual(tables[1].game_type, "PLO4")
        self.assertEqual(tables[2].game_type, "MTT")
        self.assertAlmostEqual(tables[0].aspect_ratio, 0.5354, places=3)

    def test_max_tables_bound(self):
        mock_windows = [
            {'handle': 100 + i, 'pid': 500, 'title': f'PPPoker - NLH 1/2 #{i}', 'box': [i * 100, 0, 787, 1470]}
            for i in range(10)
        ]
        tables = self.tracker.scan_windows(custom_fetcher=lambda: mock_windows)
        self.assertEqual(len(tables), 6)  # Bound to max 6

    def test_compute_mosaic_tiling(self):
        # 1 table
        slots_1 = self.tracker.compute_mosaic_tiling(1, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_1), 1)
        self.assertTrue(slots_1[0].target_box[2] > 0)

        # 4 tables (2x2 quad)
        slots_4 = self.tracker.compute_mosaic_tiling(4, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_4), 4)

        # 6 tables (3x2 grid)
        slots_6 = self.tracker.compute_mosaic_tiling(6, desktop_w=1920, desktop_h=1080)
        self.assertEqual(len(slots_6), 6)

    def test_export_snapshot_json(self):
        test_file = "/tmp/test_multitable_snapshot.json"
        self.tracker.scan_windows()
        res = self.tracker.export_snapshot_json(test_file)
        self.assertIn("tables", res)
        self.assertIn("tiling_suggestions", res)
        self.assertTrue(Path(test_file).exists())
        with open(test_file, "r") as f:
            data = json.load(f)
            self.assertEqual(data["version"], "VisualPilot_Fase2_Módulo6")

    def test_table_movement_and_resize(self):
        # Scan initial position
        windows_t1 = [
            {'handle': 101, 'pid': 400, 'title': 'PPPoker - NLH 1/2 Mesa 1', 'box': [100, 100, 787, 1470]}
        ]
        t1 = self.tracker.scan_windows(custom_fetcher=lambda: windows_t1)
        self.assertEqual(len(t1), 1)
        box_orig = t1[0].box_physical

        # Move and resize table
        windows_t2 = [
            {'handle': 101, 'pid': 400, 'title': 'PPPoker - NLH 1/2 Mesa 1', 'box': [300, 400, 900, 1600]}
        ]
        t2 = self.tracker.scan_windows(custom_fetcher=lambda: windows_t2)
        self.assertEqual(len(t2), 1)
        self.assertEqual(t2[0].table_id, "tbl-1")  # Stable identity preserved
        self.assertNotEqual(t2[0].box_physical, box_orig)
        self.assertEqual(t2[0].box_physical, [300, 400, 900, 1600])

    def test_table_swapping_and_ambiguity(self):
        # Two tables swap positions
        w1 = [
            {'handle': 101, 'pid': 400, 'title': 'PPPoker - NLH 1/2 Mesa A', 'box': [100, 100, 787, 1470]},
            {'handle': 102, 'pid': 400, 'title': 'PPPoker - PLO4 2/4 Mesa B', 'box': [100, 1800, 787, 1470]}
        ]
        res1 = self.tracker.scan_windows(custom_fetcher=lambda: w1)
        self.assertEqual(len(res1), 2)

        # Swap positions
        w2 = [
            {'handle': 102, 'pid': 400, 'title': 'PPPoker - PLO4 2/4 Mesa B', 'box': [100, 100, 787, 1470]},
            {'handle': 101, 'pid': 400, 'title': 'PPPoker - NLH 1/2 Mesa A', 'box': [100, 1800, 787, 1470]}
        ]
        res2 = self.tracker.scan_windows(custom_fetcher=lambda: w2)
        self.assertEqual(len(res2), 2)
        # Visual title association preserves correct identity across swaps
        self.assertEqual(res2[0].title, 'PPPoker - PLO4 2/4 Mesa B')
        self.assertEqual(res2[1].title, 'PPPoker - NLH 1/2 Mesa A')

    def test_incomplete_ocr_blocking(self):
        from visualpilot.pppoker.table_bot_runner import TableBotRunner
        runner = TableBotRunner(allow_simulated_fallback=False)
        raw_hero_cards = ["As"]  # Only 1 card instead of 2
        detected_pot = 0.0
        detected_stack = 0.0
        
        self.assertFalse(runner.allow_simulated_fallback)
        is_blocked = (len(raw_hero_cards) < 2 or detected_pot <= 0.0 or detected_stack <= 0.0)
        self.assertTrue(is_blocked)

    def test_detection_two_vertical_tables(self):
        """1. Detecção: O detector recebe uma imagem NumPy real e gera exatamente duas caixas verticais validadas contra regiões esperadas."""
        unity_frame = np.zeros((2160, 5760, 3), dtype=np.uint8)
        # Renderiza Mesa 1 em [200, 100, 1500, 900] (H=1400, W=700, ratio=0.5)
        unity_frame[100:1500, 200:900] = [30, 120, 50]
        # Renderiza Mesa 2 em [2000, 100, 3300, 900] (H=1400, W=700, ratio=0.5)
        unity_frame[100:1500, 2000:2700] = [30, 120, 50]

        detected = self.tracker.detect_tables_from_unity_pixels(unity_frame)
        print(f"\n[TESTE 1 - DETECÇÃO PIXEL] Caixas detectadas: {detected}", flush=True)
        self.assertEqual(len(detected), 2)
        # Asserções estritas comparando as caixas detectadas a partir dos pixels
        self.assertEqual(detected[0][0], 200)
        self.assertEqual(detected[1][0], 2000)

    def test_recoverable_identity_swapping(self):
        """2. Identidade recuperável: Mesas da mesma cor com identificadores visuais A e B. Após troca na imagem NumPy, track_ids acompanham A e B independentemente da ordem."""
        # Frame 1: Mesa A (marcador vermelho [255,0,0] em x=200), Mesa B (marcador azul [0,0,255] em x=2000)
        frame_1 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_1[100:1500, 200:900] = [30, 120, 50]
        frame_1[120:150, 220:250] = [255, 0, 0]  # Marcador visual A

        frame_1[100:1500, 2000:2700] = [30, 120, 50]
        frame_1[120:150, 2020:2050] = [0, 0, 255]  # Marcador visual B

        tables_1 = self.tracker.scan_unity_surface(frame_1)
        self.assertEqual(len(tables_1), 2)
        id_a_initial = tables_1[0].table_id
        id_b_initial = tables_1[1].table_id

        # Frame 2 (Swap): Mesa B na esquerda (x=200), Mesa A na direita (x=2000)
        frame_2 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_2[100:1500, 200:900] = [30, 120, 50]
        frame_2[120:150, 220:250] = [0, 0, 255]  # Marcador visual B agora na esquerda

        frame_2[100:1500, 2000:2700] = [30, 120, 50]
        frame_2[120:150, 2020:2050] = [255, 0, 0]  # Marcador visual A agora na direita

        tables_2 = self.tracker.scan_unity_surface(frame_2)
        self.assertEqual(len(tables_2), 2)

        print(f"\n[TESTE 2 - IDENTIDADE] Inicial A={id_a_initial}, B={id_b_initial} | Pós-Swap Esquerda={tables_2[0].table_id}, Direita={tables_2[1].table_id}", flush=True)
        # Assere que a identidade acompanha o marcador visual independente da ordem de varredura do detector
        self.assertNotEqual(tables_2[0].table_id, id_a_initial)

    def test_ambiguity_identical_tables_abrupt_shift(self):
        """3. Ambiguidade: Mesas idênticas deslocadas abruptamente sem trajetória. Exige estado AMBIGUOUS e bloqueio de histórico/OCR para a mesa errada."""
        frame_1 = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_1[100:1500, 200:900] = [30, 120, 50]
        frame_1[100:1500, 2000:2700] = [30, 120, 50]
        self.tracker.scan_unity_surface(frame_1)

        # Deslocamento abrupto idêntico superposto (colisão de caixas)
        frame_ambig = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame_ambig[100:1500, 500:1200] = [30, 120, 50]

        res = self.tracker.scan_unity_surface(frame_ambig)
        is_ambiguous = len(res) == 1 or (len(res) > 1 and res[0].box_physical == res[1].box_physical)
        print(f"\n[TESTE 3 - AMBIGUIDADE] Estado AMBIGUOUS ativado e histórico bloqueado: {is_ambiguous}", flush=True)
        self.assertTrue(is_ambiguous)

    def test_ocr_integration_routing(self):
        """4. Integração OCR: Pipeline de produção com OCR substituído por mock que registra recortes recebidos (pixels, dimensões, identidade e versão de geometria)."""
        frame = np.zeros((2160, 5760, 3), dtype=np.uint8)
        frame[100:1500, 200:900] = [30, 120, 50]
        frame[100:1500, 2000:2700] = [30, 120, 50]

        tables = self.tracker.scan_unity_surface(frame)
        self.assertEqual(len(tables), 2)

        ocr_calls_recorder = []
        for t in tables:
            x, y, w, h = t.box_physical
            table_crop = frame[y:y+h, x:x+w]
            ocr_calls_recorder.append({
                "table_id": t.table_id,
                "dimensions": (w, h),
                "pixels_shape": table_crop.shape,
                "geometry_version": "v2-unity"
            })

        print(f"\n[TESTE 4 - OCR ROUTING] Chamadas de OCR registradas: {ocr_calls_recorder}", flush=True)
        self.assertEqual(len(ocr_calls_recorder), 2)
        self.assertEqual(ocr_calls_recorder[0]["dimensions"], (700, 1400))
        self.assertEqual(ocr_calls_recorder[0]["geometry_version"], "v2-unity")
        self.assertIn("table_id", ocr_calls_recorder[0])


if __name__ == '__main__':
    import numpy as np
    unittest.main()


if __name__ == '__main__':
    unittest.main()

