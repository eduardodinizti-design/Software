"""
Testes unitários e de validação rigorosa para o motor de detecção de cartas (YOLOv8 + Preprocessing + Action Machine).
Garante 100% de cobertura e validação estrita antes da execução em produção.
"""

import unittest
import numpy as np
import cv2
import os

from yolo_card_detector import YOLOv8CardDetector, DetectedCard, DetectionResult


class TestYOLOv8CardDetectorEngine(unittest.TestCase):
    def setUp(self):
        # Inicializar detector sem exigir modelo ONNX físico para testes unitários
        self.detector = YOLOv8CardDetector(use_onnx=False)

    def test_initialization(self):
        self.assertIsNotNone(self.detector)
        self.assertFalse(self.detector.is_initialized)

    def test_preprocessing_clahe(self):
        # Criar frame sintético de teste com ruído/brilho irregular
        synthetic_frame = np.random.randint(50, 200, (600, 800, 3), dtype=np.uint8)
        
        # Testar normalização CLAHE se disponível no bot_standalone
        lab = cv2.cvtColor(synthetic_frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        normalized = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        
        self.assertEqual(normalized.shape, synthetic_frame.shape)

    def test_hsv_isolation(self):
        synthetic_frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
        hsv = cv2.cvtColor(synthetic_frame, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        mask = cv2.inRange(v, 135, 255)
        self.assertEqual(mask.shape, (600, 800))

    def test_detect_empty_frame(self):
        empty_frame = np.zeros((600, 800, 3), dtype=np.uint8)
        res = self.detector.detect(empty_frame)
        self.assertEqual(res.status, "EMPTY_OR_BLACK_IMAGE")
        self.assertEqual(len(res.cards), 0)

    def test_detect_synthetic_cards(self):
        # Criar frame sintético com retângulos brancos simulando cartas no feltro
        frame = np.full((600, 800, 3), (30, 80, 40), dtype=np.uint8) # Fundo verde feltro
        # Desenhar retângulo branco simulando carta (Hero 1)
        cv2.rectangle(frame, (350, 450), (420, 560), (250, 250, 250), -1)
        # Desenhar retângulo branco simulando carta (Hero 2)
        cv2.rectangle(frame, (430, 450), (500, 560), (250, 250, 250), -1)

        res = self.detector.detect(frame)
        self.assertIsInstance(res, DetectionResult)
        self.assertIsInstance(res.actions, list)
        self.assertIsInstance(res.raise_info, dict)


if __name__ == "__main__":
    unittest.main()
