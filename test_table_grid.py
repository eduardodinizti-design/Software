"""Regressão da detecção de painéis em multi-table TILADO ([[nvt-multitable-tiled-bug]] #2).

A fixture real `multitable_tiled_20261120.png` tem 3 mesas em colunas iguais; a do MEIO
está coberta por um modal "Dicas… Confirmar" (volta do sit-out) que a escurece abaixo do
limiar de brilho. O detector direto achava só 2/3 → a 3ª mesa ficava sit out. O
`complete_grid` reconstrói a grade de colunas iguais e devolve a 3ª como slot endereçável.
"""
import os

import cv2
import numpy as np
import pytest

from table_grid import detect_table_panels, _complete_equal_grid

FIXTURE = os.path.join(os.path.dirname(__file__), "research", "ppp_il2cpp",
                       "multitable_tiled_20261120.png")


@pytest.fixture(scope="module")
def frame():
    img = cv2.imread(FIXTURE)
    if img is None:
        pytest.skip(f"fixture ausente: {FIXTURE}")
    return img


def test_fixture_tem_3_paineis_iguais(frame):
    """3 painéis, colunas de largura ~igual, ordenados por x e sem sobreposição."""
    panels = detect_table_panels(frame)
    assert len(panels) == 3, panels
    # ordenados e disjuntos
    for a, b in zip(panels, panels[1:]):
        assert a[0] + a[2] <= b[0] + 5, (a, b)
    widths = [p[2] for p in panels]
    wmin, wmax = min(widths), max(widths)
    assert wmax - wmin <= 0.15 * wmax, widths   # larguras ~iguais (tiling igual)


def test_painel_do_meio_cobre_o_modal(frame):
    """O slot sintetizado do meio deve conter a região do modal 'Confirmar'
    (banda dim central ~x 2616..3307 no frame 5760-wide)."""
    panels = detect_table_panels(frame)
    mid = panels[1]
    mx0, mx1 = mid[0], mid[0] + mid[2]
    # o modal estava centrado ~x≈2900 (medido na fixture)
    assert mx0 <= 2900 <= mx1, mid
    # e o meio NÃO é só o vão: tem largura de mesa (herdou h/altura dos brilhantes)
    assert mid[3] >= 0.25 * frame.shape[0], mid


def test_single_table_nao_inventa_paineis():
    """Grade com UM painel brilhante só (single-table): não sintetiza mesas fantasma."""
    # frame preto com uma coluna clara central
    fr = np.zeros((400, 900, 3), np.uint8)
    fr[40:360, 380:520] = (90, 90, 90)
    panels = detect_table_panels(fr)
    assert len(panels) == 1, panels


def test_complete_grid_sem_brilhantes_e_noop():
    """Sem painéis brilhantes de referência, não há como inferir N → devolve como veio."""
    col = np.zeros(1000)
    assert _complete_equal_grid(col, []) == []
