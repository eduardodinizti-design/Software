"""Árbitro de clique (lock GLOBAL do cursor p/ multi-plataforma). Testa a injeção do backend e a
propagação de ClickBusy sem depender de win32; smoke do backend real se pywin32 existir."""
import contextlib

import pytest

import click_arbiter as A


def test_impl_injetado_recebe_timeout():
    usado = []

    @contextlib.contextmanager
    def fake(timeout_s):
        usado.append(timeout_s)
        yield

    with A.click_lock(timeout_s=1.5, _impl=fake):
        pass
    assert usado == [1.5]


def test_clickbusy_do_impl_propaga():
    @contextlib.contextmanager
    def busy(timeout_s):
        raise A.ClickBusy('cursor ocupado')
        yield  # noqa: unreachable, só p/ ser generator

    with pytest.raises(A.ClickBusy):
        with A.click_lock(_impl=busy):
            pass


def test_win32_real_adquire_e_libera_reentrante():
    try:
        import win32event  # noqa: F401
    except Exception:
        pytest.skip('sem pywin32')
    # mutex nomeado é reentrante p/ a MESMA thread -> aninhar não trava
    with A.click_lock(timeout_s=2.0):
        with A.click_lock(timeout_s=2.0):
            pass
