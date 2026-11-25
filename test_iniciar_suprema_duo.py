"""Launcher de 2 contas da Suprema (iniciar_suprema_duo): monta UM agente por instância, cada um com
--pid/--hwnd específicos + base/H2N separados; só o 1º com hotkeys/overlay. Popen mockado."""
import suprema_operar

import iniciar_suprema_duo as D


class _FakeProc:
    def poll(self):
        return 0

    def terminate(self):
        pass


def _run(monkeypatch, insts, argv=None):
    cmds = []
    monkeypatch.setattr(suprema_operar, 'find_suprema_instances', lambda process='SupremaPoker.exe': insts)
    monkeypatch.setattr(D.os, 'makedirs', lambda *a, **k: None)
    monkeypatch.setattr(D.time, 'sleep', lambda s: None)
    monkeypatch.setattr(D.sys, 'frozen', False, raising=False)

    def fake_popen(cmd, **k):
        cmds.append([str(x) for x in cmd])
        return _FakeProc()

    monkeypatch.setattr(D.subprocess, 'Popen', fake_popen)
    import builtins
    ro = builtins.open
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: ro(__file__, 'r', encoding='utf-8'))
    D.main(argv or [])
    return [' '.join(c) for c in cmds]


def test_um_agente_por_conta_com_pid_e_hwnd(monkeypatch):
    cmds = _run(monkeypatch, [(111, 2001), (222, 3002)])
    assert len(cmds) == 2
    assert any('--pid 111' in c and '--hwnd 2001' in c for c in cmds)
    assert any('--pid 222' in c and '--hwnd 3002' in c for c in cmds)
    assert all('--armed' in c and 'suprema_agente' in c for c in cmds)


def test_bases_separados_por_conta(monkeypatch):
    cmds = _run(monkeypatch, [(111, 2001), (222, 3002)])
    assert any('c0' in c for c in cmds) and any('c1' in c for c in cmds)   # base/H2N por conta


def test_extras_sem_hotkeys_nem_overlay(monkeypatch):
    cmds = _run(monkeypatch, [(111, 2001), (222, 3002)])
    c0 = next(c for c in cmds if '--pid 111' in c)
    c1 = next(c for c in cmds if '--pid 222' in c)
    assert '--no-hotkeys' not in c0 and '--no-overlay' not in c0     # conta 0 controla
    assert '--no-hotkeys' in c1 and '--no-overlay' in c1             # extras não duplicam


def test_nenhuma_suprema_nao_sobe(monkeypatch):
    assert _run(monkeypatch, []) == []


def test_mode_stage_repassados(monkeypatch):
    cmds = _run(monkeypatch, [(111, 2001)], argv=['--mode', 'icm', '--stage', 'bubble'])
    assert all('--mode icm' in c and '--stage bubble' in c for c in cmds)
