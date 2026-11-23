"""Testes do CLIQUE EM BACKGROUND da Suprema (offline, sem janela real).

Trava: (1) empacotamento de lParam e frac->cliente (puros); (2) o execute() em modo background
emite coords de CLIENTE e nao mexe no cursor; (3) o caminho DEFAULT (SendInput) continua
IDENTICO (mesmo dict, coords de tela). Nao clica em nada — injeta um `mover` fake e faz
monkeypatch da geometria (sem hwnd real). Ver nvt-suprema-nao-matar-multitable.
"""
import suprema_act as A
import suprema_click as C


# ---- puros -------------------------------------------------------------
def test_make_lparam_empacota_xy():
    assert C._make_lparam(0, 0) == 0
    assert C._make_lparam(5, 0) == 5
    assert C._make_lparam(0, 3) == (3 << 16)
    assert C._make_lparam(0x1234, 0x5678) == ((0x5678 << 16) | 0x1234)


def test_make_lparam_mascara_low_word():
    # so os 16 bits baixos do X entram no low word (nao vaza pro high)
    assert C._make_lparam(0x1FFFF, 0) == 0xFFFF


def test_frac_to_client_wh():
    assert C._frac_to_client_wh(0.5, 0.95, 1000, 2000) == (500, 1900)
    assert C._frac_to_client_wh(0.0, 0.0, 1141, 2029) == (0, 0)


# ---- execute() em modo BACKGROUND -------------------------------------
def test_execute_bg_emite_client_e_nao_mexe_cursor(monkeypatch):
    monkeypatch.setattr(C, "client_wh", lambda hwnd: (1000, 2000))
    calls = []
    res = C.execute({"action": A.FOLD}, hwnd=1234, armed=True, background=True,
                    mover=lambda x, y: calls.append((x, y)))
    assert res["mode"] == "bg" and res["clicked"] is True
    assert res["client"] == [(185, 1900)]          # 0.185*1000, 0.950*2000
    assert calls == [(185, 1900)]                  # clicou em coords de CLIENTE
    assert "screen" not in res                     # bg nao usa coords de tela


def test_execute_bg_raise_sequencia_client(monkeypatch):
    monkeypatch.setattr(C, "client_wh", lambda hwnd: (1000, 2000))
    res = C.execute({"action": A.RAISE, "preset": "2X"}, hwnd=1, armed=True, background=True,
                    mover=lambda x, y: None, sleeper=lambda s: None)
    # Aumentar(0.815,0.950) -> 2X(0.101,0.949) -> Confirmar(0.816,0.949)
    assert res["client"] == [(815, 1900), (101, 1898), (816, 1898)]
    assert res["mode"] == "bg" and res["clicked"]


def test_execute_bg_dry_run(monkeypatch):
    monkeypatch.setattr(C, "client_wh", lambda hwnd: (1000, 2000))
    res = C.execute({"action": A.CALL}, hwnd=1, armed=False, background=True)
    assert res["reason"] == "DRY_RUN" and res["mode"] == "bg"
    assert res["client"] == [(500, 1900)] and res["clicked"] is False


def test_flag_de_modulo_ativa_bg_quando_background_none(monkeypatch):
    monkeypatch.setattr(C, "client_wh", lambda hwnd: (1000, 2000))
    monkeypatch.setattr(C, "SUPREMA_CLICK_BG", True)
    calls = []
    res = C.execute({"action": A.FOLD}, hwnd=1, armed=True,     # background=None -> usa o flag
                    mover=lambda x, y: calls.append((x, y)))
    assert res["mode"] == "bg" and res["client"] == [(185, 1900)]
    assert calls == [(185, 1900)]


# ---- DEFAULT (SendInput) nao pode ter mudado --------------------------
def test_execute_default_dict_identico(monkeypatch):
    monkeypatch.setattr(C, "frac_to_screen", lambda hwnd, fx, fy: (int(fx * 1000) + 7, int(fy * 2000) + 9))
    res = C.execute({"action": A.FOLD}, hwnd=1, armed=False)       # background None, flag False
    assert set(res.keys()) == {"action", "screen", "clicked", "reason"}   # SEM mode/client
    assert res["reason"] == "DRY_RUN" and res["screen"] == [(192, 1909)]


def test_execute_default_clica_coords_de_tela(monkeypatch):
    monkeypatch.setattr(C, "frac_to_screen", lambda hwnd, fx, fy: (int(fx * 1000), int(fy * 2000)))
    calls = []
    res = C.execute({"action": A.CALL}, hwnd=1, armed=True,
                    mover=lambda x, y: calls.append((x, y)))
    assert calls == [(500, 1900)] and res["screen"] == [(500, 1900)]
    assert "client" not in res


def test_restore_cursor_usa_sendinput_por_padrao(monkeypatch):
    # com mover injetado, restore_cursor nao muda o alvo (so trocaria o clicker real); garante
    # que a opcao existe e nao quebra o caminho default.
    monkeypatch.setattr(C, "frac_to_screen", lambda hwnd, fx, fy: (int(fx * 1000), int(fy * 2000)))
    calls = []
    res = C.execute({"action": A.FOLD}, hwnd=1, armed=True, restore_cursor=True,
                    mover=lambda x, y: calls.append((x, y)))
    assert calls == [(185, 1900)] and res["clicked"]


def test_sem_alvo_inalterado():
    res = C.execute({"action": A.WAIT}, hwnd=1, armed=True)
    assert res["clicked"] is False and res["reason"].startswith("SEM_ALVO")
