"""REGRESSÃO do fix do RAISE (Eduardo 23/11, zig-zag/bust ao vivo): a sequência de clique do raise/
bet (Aumentar -> tamanho -> Confirmar) tem que ESPERAR o painel de size RENDERIZAR entre o 1º clique
('Aumentar') e o clique do preset. Antes saía tudo em step_delay (0.15s) -> o preset caía no vazio =
size errado / all-in acidental. Agora o 1º gap usa panel_delay (>=0.5s); os demais, step_delay.
Fold/call/check = 1 clique, sem espera nenhuma."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import suprema_click as C
import suprema_act as A


def _delays_for(plan, **kw):
    """Roda execute armado com mover/sleeper injetados e devolve a lista de delays entre cliques.
    RESTAURA frac_to_screen_room (senão o patch VAZA e quebra os testes de geometria do suprema_click)."""
    _orig = C.frac_to_screen_room
    C.frac_to_screen_room = lambda h, fx, fy, i, n: (int(fx * 1000), int(fy * 1000))
    ds = []
    try:
        C.execute(plan, 1, armed=True, mover=lambda x, y: None,
                  sleeper=lambda d: ds.append(round(d, 3)), **kw)
    finally:
        C.frac_to_screen_room = _orig
    return ds


def test_raise_espera_o_painel_no_primeiro_gap():
    ds = _delays_for({'action': A.RAISE, 'preset': '2X'}, step_delay=0.15, panel_delay=0.5)
    assert len(ds) == 2 and ds[0] >= 0.5 and ds[1] == 0.15   # Aumentar->(espera painel)->preset->Confirmar


def test_all_in_tambem_espera_o_painel():
    ds = _delays_for({'action': A.ALL_IN}, step_delay=0.15, panel_delay=0.5)
    assert ds and ds[0] >= 0.5                                # Aumentar -> espera painel -> All In -> Confirmar


def test_fold_e_call_sem_espera():
    assert _delays_for({'action': A.FOLD}) == []
    assert _delays_for({'action': A.CHECK}) == []


def test_panel_delay_default_seguro():
    import inspect
    sig = inspect.signature(C.execute)
    assert sig.parameters['panel_delay'].default >= 0.4     # default já protege mesmo sem passar


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
