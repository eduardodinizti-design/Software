"""Testes da rotina de ADD-ON (addon_runner) com AMOSTRAS REAIS do torneio BINGO
capturadas ao vivo em 20/11/2026. Lab primeiro (AGENTS.md): trava o detector para
nunca desaprender ([[nvt-metodologia-preventiva]]).
"""
import os

import cv2
import pytest

import addon_runner as ar
from table_reading.pipeline import configure_ocr

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "research", "ppp_il2cpp")
MODAL = os.path.join(FIX, "addon_screen_20261120.png")
APOS = os.path.join(FIX, "addon_apos_20261120.png")


@pytest.fixture(scope="module", autouse=True)
def _ocr():
    configure_ocr()


def _img(path):
    f = cv2.imread(path)
    if f is None:
        pytest.skip("fixture ausente: %s" % path)
    return f


def test_detecta_modal_addon_simples():
    d = ar.detect_addon_popup(_img(MODAL))
    assert d["present"] is True
    assert d["cost_pp"] == 10            # add-on SIMPLES = 10 Fichas PP
    assert d["add_chips"] == 22500       # adiciona 22.500 fichas
    assert d["confirm_rect"] is not None
    x, y, w, h = d["confirm_rect"]
    assert w > 120 and h > 40            # botão plausível
    # Confirmar fica à ESQUERDA do Cancelar (quando ambos lidos)
    if d["cancel_rect"] is not None:
        assert x < d["cancel_rect"][0]


def test_modal_fechado_nao_detecta():
    d = ar.detect_addon_popup(_img(APOS))
    assert d["present"] is False
    assert d["confirm_rect"] is None


def test_confirm_addon_sem_popup_nao_clica():
    """Sem pop-up, confirm_addon NÃO clica (retorna NO_POPUP)."""
    class _Eng:
        def capture_frame(self, hwnd=None):
            return _img(APOS), None
    res = ar.confirm_addon(_Eng(), 0x1, control=None, adapter=None)
    assert res.get("state") == "NO_POPUP"


def test_confirm_addon_barra_custo_acima_do_teto():
    """Guarda: custo em Fichas PP acima de max_cost_pp barra o clique (evita Duplo/Triplo)."""
    class _Eng:
        def capture_frame(self, hwnd=None):
            return _img(MODAL), None
    res = ar.confirm_addon(_Eng(), 0x1, control=None, adapter=None, max_cost_pp=5)
    assert res.get("state") == "COST_EXCEEDS"
    assert res.get("cost_pp") == 10
