"""Launcher ÚNICO multi-plataforma (iniciar_multi): detecção + montagem dos comandos de spawn, sem
subir processo de verdade (Popen mockado). Trava: sobe os DOIS quando ambos abertos, só o aberto senão,
nada quando nenhum, e usa SUBCOMANDO quando frozen (.exe)."""
import iniciar_multi as M


class _FakeProc:
    pid = 123

    def poll(self):
        return 0            # já terminou -> o loop de monitoramento sai na hora

    def terminate(self):
        pass


def _run(monkeypatch, sup, ppp, frozen=False, argv=None):
    cmds = []
    monkeypatch.setattr(M, '_suprema_open', lambda: sup)
    monkeypatch.setattr(M, '_pppoker_open', lambda: ppp)
    monkeypatch.setattr(M.os, 'makedirs', lambda *a, **k: None)
    monkeypatch.setattr(M.time, 'sleep', lambda s: None)
    monkeypatch.setattr(M.sys, 'frozen', frozen, raising=False)

    def fake_popen(cmd, **k):
        cmds.append([str(x) for x in cmd])
        return _FakeProc()

    monkeypatch.setattr(M.subprocess, 'Popen', fake_popen)
    # não criar arquivos de log de verdade
    import builtins
    real_open = builtins.open
    monkeypatch.setattr(builtins, 'open', lambda *a, **k: real_open(__file__, 'r', encoding='utf-8'))
    M.main(argv or [])
    return [' '.join(c) for c in cmds]


def test_sobe_os_dois_quando_ambos_abertos(monkeypatch):
    cmds = _run(monkeypatch, True, True)
    assert len(cmds) == 2
    assert any('suprema_agente.py' in c and '--armed' in c for c in cmds)
    assert any('iniciar_bot.py' in c for c in cmds)


def test_so_pppoker(monkeypatch):
    cmds = _run(monkeypatch, False, True)
    assert len(cmds) == 1 and 'iniciar_bot.py' in cmds[0]


def test_so_suprema(monkeypatch):
    cmds = _run(monkeypatch, True, False)
    assert len(cmds) == 1 and 'suprema_agente.py' in cmds[0]


def test_nenhuma_nao_sobe_nada(monkeypatch):
    assert _run(monkeypatch, False, False) == []


def test_frozen_usa_subcomando_nao_py(monkeypatch):
    cmds = _run(monkeypatch, True, True, frozen=True)
    # frozen -> re-invoca o .exe por subcomando (sem 'script.py')
    assert any('suprema-agente' in c and '.py' not in c for c in cmds)
    assert any(' iniciar ' in (' ' + c + ' ') and 'iniciar_bot.py' not in c for c in cmds)


def test_only_sobe_apenas_uma(monkeypatch):
    cmds = _run(monkeypatch, True, True, argv=['--only', 'pppoker'])
    assert len(cmds) == 1 and 'iniciar_bot.py' in cmds[0]


def test_mode_stage_repassados(monkeypatch):
    cmds = _run(monkeypatch, True, True, argv=['--mode', 'icm', '--stage', 'bubble'])
    assert all('--mode icm' in c and '--stage bubble' in c for c in cmds)
