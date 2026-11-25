"""Vigia de BUST da Suprema: acha o botão SAIR do pop-up de CLASSIFICAÇÃO (caiu do torneio) por
título (OCR) + cor dos botões (Sair vermelho esq / Observar laranja dir). Calibrado no print real 23/11.
find_sair validado nos pixels reais; aqui trava a lógica de cor/geometria e o gating do loop."""
import numpy as np

import suprema_bust as B


def _tile(left_g=93, right_g=147, two=True, H=400, W=300):
    """Tile sintético: faixa inferior com botão VERMELHO à esquerda (Sair, G baixo) e LARANJA à
    direita (Observar, G alto). _is_classificacao é monkeypatchado nos testes (OCR à parte)."""
    im = np.zeros((H, W, 3), dtype=np.uint8)
    y0, y1 = int(0.70 * H), int(0.78 * H)
    im[y0:y1, 30:120] = [207, left_g, 81]            # Sair (vermelho) ESQUERDA
    if two:
        im[y0:y1, 170:260] = [216, right_g, 64]      # Observar (laranja) DIREITA
    return im


def test_find_sair_acha_o_vermelho_esquerdo(monkeypatch):
    monkeypatch.setattr(B, "_is_classificacao", lambda im: True)
    pos = B.find_sair(_tile())
    assert pos is not None
    cx, cy = pos
    assert 30 <= cx <= 120                            # botão ESQUERDO (Sair), não o Observar
    assert int(0.68 * 400) <= cy <= int(0.82 * 400)


def test_find_sair_none_sem_confirmacao_do_popup(monkeypatch):
    monkeypatch.setattr(B, "_is_classificacao", lambda im: False)
    assert B.find_sair(_tile()) is None              # sem o título -> NÃO clica (anti-clique-errado)


def test_find_sair_none_sem_o_par(monkeypatch):
    monkeypatch.setattr(B, "_is_classificacao", lambda im: True)
    assert B.find_sair(_tile(two=False)) is None     # só 1 botão -> não é Sair/Observar


def test_find_sair_none_se_esquerdo_nao_e_o_mais_vermelho(monkeypatch):
    monkeypatch.setattr(B, "_is_classificacao", lambda im: True)
    assert B.find_sair(_tile(left_g=160, right_g=90)) is None   # layout invertido -> aborta seguro


class _Ctrl:
    def __init__(self, a):
        self._a = a

    def execution_allowed(self):
        return self._a


class _Stop:
    def __init__(self, n):
        self.n = n

    def is_set(self):
        self.n -= 1
        return self.n < 0

    def wait(self, t):
        pass


def _run_bust(allowed, detect_val, monkeypatch):
    import suprema_click as C
    import PIL.ImageGrab as IG
    clicks = []
    monkeypatch.setattr(C, "columns_from_window", lambda h: 1)
    monkeypatch.setattr(C, "table_rect_for_room", lambda h, i, n: (0, 0, 80, 100))
    monkeypatch.setattr(IG, "grab", lambda **k: None)
    B.bust_watch(hwnd=1, control=_Ctrl(allowed), stop=_Stop(1), period=0, cooldown=0,
                 click=lambda x, y: clicks.append((x, y)), detect=lambda t: detect_val)
    return clicks


def test_vigia_clica_sair_quando_running_e_bust(monkeypatch):
    assert _run_bust(True, (10, 20), monkeypatch) == [(10, 20)]


def test_vigia_nao_clica_se_pausado(monkeypatch):
    assert _run_bust(False, (10, 20), monkeypatch) == []   # Eduardo assumiu -> não força


def test_vigia_nao_clica_sem_bust(monkeypatch):
    assert _run_bust(True, None, monkeypatch) == []


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
