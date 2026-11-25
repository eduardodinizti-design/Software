"""Testes OFFLINE do núcleo do guardião (ClientMonitor + parse WER + classify).

Tudo puro: nenhum processo real, nenhum som, nenhum Windows exigido.
"""
import guardiao as g


def _collect(mon, sequence):
    """Aplica uma sequência de mapas 'present' e devolve a lista de (tick, cliente)."""
    out = []
    for i, pm in enumerate(sequence):
        for ev in mon.update(pm, now=float(i)):
            out.append((i, ev.client))
    return out


def test_nao_dispara_para_cliente_que_nunca_apareceu():
    mon = g.ClientMonitor(confirm_ticks=2)
    ev = _collect(mon, [{"PPPoker": False}] * 5)
    assert ev == []


def test_queda_simples_confirma_apos_debounce():
    mon = g.ClientMonitor(confirm_ticks=2)
    # vivo, vivo, some, some(confirma)
    ev = _collect(mon, [{"PPPoker": True}, {"PPPoker": True},
                        {"PPPoker": False}, {"PPPoker": False}])
    assert ev == [(3, "PPPoker")]


def test_ausencia_momentanea_nao_dispara():
    mon = g.ClientMonitor(confirm_ticks=2)
    # some por 1 tick só e volta -> não é queda
    ev = _collect(mon, [{"PPPoker": True}, {"PPPoker": False},
                        {"PPPoker": True}, {"PPPoker": True}])
    assert ev == []


def test_dispara_uma_unica_vez_por_queda():
    mon = g.ClientMonitor(confirm_ticks=2)
    ev = _collect(mon, [{"PPPoker": True}, {"PPPoker": False},
                        {"PPPoker": False}, {"PPPoker": False}, {"PPPoker": False}])
    assert ev == [(2, "PPPoker")]  # só no tick que confirma, não repete


def test_queda_e_religa_depois_pode_cair_de_novo():
    mon = g.ClientMonitor(confirm_ticks=2)
    seq = [
        {"PPPoker": True}, {"PPPoker": False}, {"PPPoker": False},  # queda 1 (tick 2)
        {"PPPoker": True}, {"PPPoker": True},                        # religou
        {"PPPoker": False}, {"PPPoker": False},                      # queda 2 (tick 6)
    ]
    ev = _collect(mon, seq)
    assert ev == [(2, "PPPoker"), (6, "PPPoker")]


def test_dois_clientes_independentes():
    mon = g.ClientMonitor(confirm_ticks=2)
    seq = [
        {"PPPoker": True, "Suprema": True},
        {"PPPoker": True, "Suprema": False},
        {"PPPoker": False, "Suprema": False},   # Suprema confirma (tick2), PPPoker 1ª ausência
        {"PPPoker": False, "Suprema": True},    # PPPoker confirma (tick3), Suprema volta
    ]
    ev = _collect(mon, seq)
    assert (2, "Suprema") in ev
    assert (3, "PPPoker") in ev
    assert len(ev) == 2


def test_parse_wer_pt():
    msg = (
        "Nome do aplicativo com falha: PPPoker.exe, versão: 2022.3.62.30479\n"
        "Nome do módulo com falha: unknown, versão: 0.0.0.0\n"
        "Código de exceção: 0xc0000409\n"
        "Deslocamento de falha: 0x000001752324d5e1\n"
    )
    w = g._parse_wer(msg)
    assert w["app"] == "PPPoker.exe"
    assert w["modulo"] == "unknown"
    assert w["excecao"] == "0xc0000409"
    assert w["offset"].endswith("d5e1")


def test_classify_suspeita_injecao():
    w = {"modulo": "unknown", "excecao": "0xc0000409", "offset": "x", "app": "PPPoker.exe"}
    assert "SUSPEITA_INJECAO" in g.classify(w)


def test_classify_heap_ntdll():
    w = {"modulo": "ntdll.dll", "excecao": "0xc0000005", "offset": "x", "app": "PPPoker.exe"}
    assert "heap" in g.classify(w).lower()


def test_classify_sem_wer():
    # caso Suprema: travou/fechado, sem evento de falha
    assert "sem_registro_wer" in g.classify(None)


def test_classify_falha_no_cliente():
    w = {"modulo": "PPPoker.exe", "excecao": "0xc0000005", "offset": "x", "app": "PPPoker.exe"}
    assert "falha_no_cliente" in g.classify(w)
