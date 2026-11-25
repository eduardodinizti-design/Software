"""ANTI-SIT-OUT: detecção por OCR do texto do botão ('Estou de volta' = sit-out; 'Desistir/Pagar' =
sua vez). Validado nos PIXELS REAIS (23/11), INCLUINDO o caso que deu falso-positivo (jogando, com
botões de ação verdes) — a detecção por COR falhava ali; a por TEXTO não. Pula a parte de imagem se
os PNGs/Tesseract não existirem."""
import glob
import os
import shutil
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from PIL import Image
import pytest

import suprema_sitout as SO

_CAPDIR = r"C:\Meus Projetos\Aplicativos\_repo_software\logs\suprema_captures"
_SITOUT = sorted(glob.glob(os.path.join(_CAPDIR, "col*_of2_183814.png")))   # hero SIT-OUT
_PLAY_ACT = sorted(glob.glob(os.path.join(_CAPDIR, "col*_of2_184547.png")))  # JOGANDO c/ botões de ação
_PLAY_BTW = sorted(glob.glob(os.path.join(_CAPDIR, "col*_of2_183319.png")))  # entre mãos (sem botões)
_HAS_TESS = any(os.path.exists(c) for c in (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\tacao\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")) or shutil.which("tesseract")
_img = pytest.mark.skipif(not (_SITOUT and _HAS_TESS), reason="capturas/tesseract ausentes (lab)")


@_img
def test_detecta_sitout_real():
    for fp in _SITOUT:
        assert SO.is_sitout(Image.open(fp)) is True, fp


@_img
def test_NAO_detecta_jogando_com_botoes_de_acao():
    # O caso EXATO do falso-positivo: botões verdes 'Desistir/Pagar/Pagar Qualquer' -> NÃO é sit-out
    for fp in _PLAY_ACT:
        assert SO.is_sitout(Image.open(fp)) is False, fp


@_img
def test_NAO_detecta_entre_maos():
    for fp in _PLAY_BTW:
        assert SO.is_sitout(Image.open(fp)) is False, fp


def test_ocr_vazio_quando_sem_texto_branco():
    import numpy as np
    assert SO._ocr_button_text(np.zeros((100, 80, 3), dtype=np.uint8)) == ""
    assert SO.is_sitout(np.zeros((100, 80, 3), dtype=np.uint8)) is False


# ---- lógica do vigia (sem Suprema/tela/OCR): detect e click injetados ----
class _Ctrl:
    def __init__(self, allowed):
        self._a = allowed

    def execution_allowed(self):
        return self._a


class _Stop:
    def __init__(self, n):
        self._n = n

    def is_set(self):
        self._n -= 1
        return self._n < 0

    def wait(self, _p):
        return False


def _run_watch(allowed, detect_val, monkeypatch):
    import suprema_click as C
    import PIL.ImageGrab as IG
    clicks = []
    monkeypatch.setattr(C, "columns_from_window", lambda h: 1)
    monkeypatch.setattr(C, "table_rect_for_room", lambda h, i, n: (0, 0, 80, 100))
    monkeypatch.setattr(C, "frac_to_screen_room", lambda h, fx, fy, i, n: (100, 200))
    monkeypatch.setattr(IG, "grab", lambda **k: None)
    SO.sitout_watch(hwnd=1, control=_Ctrl(allowed), stop=_Stop(1), period=0, cooldown=0,
                    click=lambda x, y: clicks.append((x, y)), detect=lambda t: detect_val)
    return clicks


def test_vigia_clica_quando_running_e_sitout(monkeypatch):
    assert _run_watch(True, True, monkeypatch) == [(100, 200)]


def test_vigia_nao_clica_se_pausado(monkeypatch):
    assert _run_watch(False, True, monkeypatch) == []


def test_vigia_nao_clica_se_nao_sitout(monkeypatch):
    assert _run_watch(True, False, monkeypatch) == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
