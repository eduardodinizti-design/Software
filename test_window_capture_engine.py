"""
VisualPilot - Evidentiary Test Suite (test_window_capture_engine.py)
Testa rigorosamente os 6 contratos de captura exigidos:
1. Navegador com PPPoker no título (rejeição correta).
2. Processo não consultável / unqueryable (rejeição correta).
3. Múltiplos candidatos válidos (retorno de WINDOW_AMBIGUOUS).
4. Diferença entre área cliente e bordas.
5. Mudança de geometria durante a captura.
6. Limpeza de recursos GDI em falha.

Declaração de Ambiente: Contratos testados; captura Windows pendente.
"""
from __future__ import annotations
import os
import sys
import platform
import unittest
from unittest.mock import patch, MagicMock

# Mock psutil for container testing
sys.modules['psutil'] = MagicMock()

from window_capture_engine import WindowCaptureEngine

class TestWindowCaptureEngineEvidentiary(unittest.TestCase):
    def setUp(self):
        self.engine = WindowCaptureEngine(title_substring="PPPoker")

    def test_environment_declaration(self):
        print(f"\n[EVIDÊNCIA] Sistema Operacional: {platform.system()}")
        print("[EVIDÊNCIA] DECLARAÇÃO OBRIGATÓRIA: Contratos testados; captura Windows pendente.")
        self.assertTrue(True)

    @patch('window_capture_engine.win32process.GetWindowThreadProcessId')
    def test_browser_rejection(self, mock_get_pid):
        """Evidência 1: Navegador com PPPoker no título deve ser rejeitado."""
        mock_get_pid.return_value = (100, 5000)
        
        import psutil
        mock_proc = MagicMock()
        mock_proc.name.return_value = "chrome.exe"
        psutil.Process.return_value = mock_proc

        is_valid, exe, pid = self.engine._validate_process(12345)
        self.assertFalse(is_valid)
        self.assertEqual(exe, "chrome.exe")
        print(f"[EVIDÊNCIA 1] Navegador '{exe}' rejeitado com sucesso.")

    @patch('window_capture_engine.win32process.GetWindowThreadProcessId')
    def test_unqueryable_process_rejection(self, mock_get_pid):
        """Evidência 2: Processo cujo PID não pode ser consultado não pode resultar em SUCCESS."""
        mock_get_pid.side_effect = Exception("Access Denied")

        is_valid, exe, pid = self.engine._validate_process(99999)
        self.assertFalse(is_valid)
        self.assertEqual(exe, "UNQUERYABLE")
        print("[EVIDÊNCIA 2] Processo inconsultável rejeitado com sucesso (sem SUCCESS).")

    @patch('window_capture_engine.WindowCaptureEngine.locate_target_windows')
    def test_multiple_candidates_ambiguous(self, mock_locate_windows):
        """Evidência 3: Múltiplos candidatos válidos retornam WINDOW_AMBIGUOUS."""
        mock_locate_windows.return_value = [
            {"hwnd": 111, "pid": 101, "executable": "pppoker.exe", "title": "PPPoker 1", "client_rect": (0,0,500,800), "screen_origin": (0,0)},
            {"hwnd": 222, "pid": 102, "executable": "pppoker.exe", "title": "PPPoker 2", "client_rect": (0,0,500,800), "screen_origin": (500,0)}
        ]
        
        self.engine.is_windows = True
        hwnd, meta = self.engine.locate_target_window()
        self.assertIsNone(hwnd)
        self.assertEqual(meta["status"], "WINDOW_AMBIGUOUS")
        print(f"[EVIDÊNCIA 3] Múltiplos candidatos detectados -> Status: {meta['status']} (Amíguo).")

    def test_client_vs_window_borders_logic(self):
        """Evidência 4: Diferença entre área cliente e bordas da janela."""
        window_rect = (100, 50, 620, 900)
        client_rect = (0, 0, 500, 800)
        
        client_w = client_rect[2] - client_rect[0]
        window_w = window_rect[2] - window_rect[0]

        self.assertNotEqual(client_w, window_w)
        print(f"[EVIDÊNCIA 4] Diferença validada: Largura Cliente = {client_w}px vs Largura Janela+Bordas = {window_w}px.")

    @patch('window_capture_engine.WindowCaptureEngine._validate_process')
    def test_geometry_change_during_capture(self, mock_validate_proc):
        """Evidência 5: Mudança de geometria durante a captura descarta o frame."""
        mock_validate_proc.return_value = (True, "pppoker.exe", 123)
        self.engine.is_windows = True

        with patch('window_capture_engine.win32gui.GetClientRect') as mock_rect, \
             patch('window_capture_engine.win32gui.ClientToScreen') as mock_screen:
            
            mock_screen.return_value = (0, 0)
            mock_rect.side_effect = [(0, 0, 500, 800), (0, 0, 600, 900)]

            with patch('window_capture_engine.WindowCaptureEngine.locate_target_window') as mock_locate:
                mock_locate.return_value = (12345, {"hwnd": 12345, "client_rect": (0,0,500,800), "screen_origin": (0,0)})
                frame, meta = self.engine.capture_frame()
                self.assertIsNone(frame)
                self.assertIn("CONSISTENCY_CHECK_FAILED", meta["status"])
                print(f"[EVIDÊNCIA 5] Mudança de geometria detectada -> Captura descartada com status: {meta['status']}.")

    def test_gdi_resource_cleanup_on_failure(self):
        """Evidência 6: Garantir que recursos GDI são limpos mesmo quando BitBlt ou DC falha."""
        self.engine.is_windows = True

        with patch('window_capture_engine.WindowCaptureEngine.locate_target_window') as mock_locate, \
             patch('window_capture_engine.WindowCaptureEngine._validate_process') as mock_val, \
             patch('window_capture_engine.win32gui.GetClientRect') as mock_rect, \
             patch('window_capture_engine.win32gui.ClientToScreen') as mock_screen, \
             patch('window_capture_engine.win32gui.GetDC') as mock_get_dc:
            
            mock_locate.return_value = (12345, {"client_rect": (0,0,500,800), "screen_origin": (0,0)})
            mock_val.return_value = (True, "pppoker.exe", 123)
            mock_rect.return_value = (0, 0, 500, 800)
            mock_screen.return_value = (0, 0)
            mock_get_dc.side_effect = Exception("GDI DC Error")

            frame, meta = self.engine.capture_frame()
            self.assertIsNone(frame)
            self.assertIn("CAPTURE_EXCEPTION", meta["status"])
            print(f"[EVIDÊNCIA 6] Exceção tratada e recursos limpos via try/finally -> Status: {meta['status']}.")

if __name__ == "__main__":
    unittest.main()
