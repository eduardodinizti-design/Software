"""Testes do LAUNCHER da Suprema (iniciar_suprema) — garante que ele sobe o AGENTE (suprema_agente),
não mais o capturador antigo, e que o ARMAR é controlado pelo flag (DRY por padrão). Sem GUI/Frida."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import iniciar_suprema as L


def _cmd(armed):
    return L._agent_cmd("python.exe", r"C:\base", r"C:\base\_live_suprema",
                        "suprema_2026-11-23", r"C:\base\raw.jsonl", armed)


def test_launcher_sobe_o_agente_nao_o_capturador():
    cmd = _cmd(False)
    assert "suprema_agente.py" in cmd                 # é o AGENTE que decide/clica
    assert "capturar_suprema_net.py" not in cmd       # NÃO o capturador antigo (hook único)


def test_agente_sempre_alimenta_hud_e_h2n():
    # sem --hud-dir a HUD overlay fica sem feed; sem --base não salva H2N -> ambos obrigatórios
    for armed in (False, True):
        cmd = _cmd(armed)
        assert "--hud-dir" in cmd and "--base" in cmd and "--dump-raw" in cmd


def test_dry_por_padrao_nao_arma():
    assert "--armed" not in _cmd(False)               # DRY: não clica


def test_armado_passa_armed():
    assert "--armed" in _cmd(True)                    # flag ligado -> joga sozinho


def test_cleanup_mata_orfaos_do_agente():
    # a limpeza de rotina precisa alcançar órfãos do próprio agente (hook pendurado = sit out)
    import inspect
    src = inspect.getsource(L._cleanup_stale)
    assert "suprema_agente" in src


def test_flag_de_armar_aponta_para_o_arquivo_certo():
    assert L._ARMED_FILE.endswith("suprema_armed.flag")


def test_agente_aceita_os_flags_que_o_launcher_passa():
    # CONTRATO: o suprema_agente precisa aceitar --hud-dir e --dump-raw, senão o comando do launcher
    # quebra na largada. Confere direto no main() do agente (sem janela/Frida).
    import inspect
    import suprema_agente as AG
    src = inspect.getsource(AG.main)
    assert "--hud-dir" in src and "--dump-raw" in src and "--armed" in src


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
