"""Testes do agente de produção da Suprema (suprema_agente) SEM Suprema viva: valida a lógica do
emit (DRY não clica / armado clica / anti-thrash por mão-rua / abstém), com C.execute mockado."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import suprema_agente as AG
import suprema_act as A
import pytest


@pytest.fixture(autouse=True)
def _restore_click_globals():
    """_mock_exec() troca suprema_click.execute e time.sleep; sem restaurar, o mock VAZA p/ outros
    arquivos (ex.: test_suprema_click_bg) e quebra o default SendInput. Restaura após cada teste."""
    _orig_exec, _orig_sleep = AG.C.execute, AG.time.sleep
    yield
    AG.C.execute, AG.time.sleep = _orig_exec, _orig_sleep


def _state(hand_id, street, board):
    return dict(hand_id=hand_id, street=street, board=board, positions={'hero': 'BTN'},
                to_call={'to_call_bb': 2.0}, pot={'pot_bb': 5.0})


def _mock_exec():
    calls = []
    AG.C.execute = lambda *a, **k: (calls.append((a, k)) or {'clicked': True, 'reason': 'MOCK'})
    AG.time.sleep = lambda *a, **k: None    # sem think-time real nos testes
    return calls


def test_import_modulo_ok():
    assert hasattr(AG, 'make_auto_emit') and hasattr(AG, 'main') and hasattr(AG, 'SaveStats')


def test_dry_nao_clica():
    calls = _mock_exec()
    stats = {'acoes': 0}
    emit = AG.make_auto_emit(hwnd=1, armed=False, delay=0.0, stats=stats)
    emit(_state(1, 'FLOP', ['8d', '3d', '9c']), {'recommended': 'raise'},
         {'action': A.RAISE, 'chips': 100}, ['As', 'Ks'])
    assert calls == [] and stats['acoes'] == 0       # DRY: salva/loga, mas NÃO clica


def test_armed_clica_uma_vez():
    calls = _mock_exec()
    stats = {'acoes': 0}
    emit = AG.make_auto_emit(hwnd=1, armed=True, delay=0.0, stats=stats)
    emit(_state(7, 'PREFLOP', []), {'recommended': 'all_in'}, {'action': A.ALL_IN}, ['As', '5h'])
    assert stats['acoes'] == 1 and len(calls) == 1


def test_antithrash_posflop_uma_acao_por_rua():
    calls = _mock_exec()
    stats = {'acoes': 0}
    emit = AG.make_auto_emit(hwnd=1, armed=True, delay=0.0, stats=stats)
    st = _state(42, 'FLOP', ['8d', '8h', 'Kc'])
    emit(st, {'recommended': 'raise'}, {'action': A.RAISE, 'chips': 100}, ['Kd', 'Td'])   # age
    emit(st, {'recommended': 'check'}, {'action': A.CHECK}, ['Kd', 'Td'])                 # flicker -> ignora
    emit(st, {'recommended': 'fold'}, {'action': A.FOLD}, ['Kd', 'Td'])                   # flicker -> ignora
    assert stats['acoes'] == 1, stats                 # só a 1ª ação do flop vale


def test_abstain_e_wait_nao_agem():
    calls = _mock_exec()
    stats = {'acoes': 0}
    emit = AG.make_auto_emit(hwnd=1, armed=True, delay=0.0, stats=stats)
    emit(_state(1, 'PREFLOP', []), {'recommended': 'abstain'}, {'action': A.ABSTAIN}, ['As', 'Kd'])
    emit(_state(2, 'PREFLOP', []), {'recommended': 'wait'}, {'action': A.WAIT}, ['As', 'Kd'])
    assert calls == [] and stats['acoes'] == 0


# -- _order / roteamento de COLUNA por mesa (mapeamento roomID->room_index, n_rooms vivos) --------
from suprema_multi import RoomOrder


def _emit_para_sala(order, room, stats):
    """Replica a fiação do main(): emit de uma mesa consulta room_index/n_rooms do RoomOrder."""
    return AG.make_auto_emit(hwnd=1, armed=True, delay=0.0, stats=stats, room=room,
                             room_index_fn=(lambda r=room: order.index(r)),
                             n_rooms_fn=order.n_rooms)


def test_order_clica_na_coluna_da_mesa():
    calls = _mock_exec()
    stats = {'acoes': 0}
    order = RoomOrder()
    order.touch("B", 1.0)                 # B aparece 1º -> coluna 0
    order.touch("A", 1.0)                 # A depois -> coluna 1 (append-only, NÃO sorted)
    emit_b = _emit_para_sala(order, "B", stats)
    emit_a = _emit_para_sala(order, "A", stats)
    emit_b(_state(1, 'PREFLOP', []), {'recommended': 'all_in'}, {'action': A.ALL_IN}, ['As', 'Ks'])
    emit_a(_state(2, 'PREFLOP', []), {'recommended': 'all_in'}, {'action': A.ALL_IN}, ['Ad', 'Kd'])
    # execute(plan, hwnd, armed=, step_delay=, room_index=, n_rooms=)
    assert calls[0][1]['room_index'] == 0 and calls[0][1]['n_rooms'] == 2   # mesa B -> coluna 0
    assert calls[1][1]['room_index'] == 1 and calls[1][1]['n_rooms'] == 2   # mesa A -> coluna 1


def test_order_bustada_recompacta_coluna_e_n_rooms():
    calls = _mock_exec()
    stats = {'acoes': 0}
    order = RoomOrder(ttl=90.0)
    order.touch("A", 100.0)
    order.touch("B", 100.0)
    order.touch("C", 100.0)
    order.touch("B", 300.0)               # A bustou (fica >ttl atrás); B e C seguem
    order.touch("C", 300.0)
    emit_c = _emit_para_sala(order, "C", stats)
    emit_c(_state(9, 'PREFLOP', []), {'recommended': 'all_in'}, {'action': A.ALL_IN}, ['As', 'Ks'])
    assert calls[-1][1]['n_rooms'] == 2            # só as 2 vivas contam
    assert calls[-1][1]['room_index'] == 1         # C desliza p/ coluna 1 (A saiu, B=0, C=1)


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
