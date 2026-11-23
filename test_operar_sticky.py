"""Cola do StickyBinder no operar_mesa: _sticky_batch acumula por frame, descarrega no vira-ciclo,
e o binder passa a reusar a posição (anti-crossing). Não toca percepção/clique."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import operar_mesa as OM


def test_sticky_batch_aprende_no_vira_ciclo_e_reusa():
    OM._STICKY = OM.table_sticky_bind.StickyBinder(min_score=2)
    OM._STICKY_FRAME.update(cycle=None, binds={}, roomids=set(), n=0)
    estado = {'A': {'players': [{'name': 'joao'}, {'name': 'maria'}]},
              'B': {'players': [{'name': 'lucas'}, {'name': 'ana'}]}}
    cropA = {1: {'raw': 'joao'}, 2: {'raw': 'maria'}}
    cropB = {1: {'raw': 'lucas'}, 2: {'raw': 'ana'}}
    OM._sticky_batch(1, 'posA', cropA, estado, 2)     # ciclo 1
    OM._sticky_batch(1, 'posB', cropB, estado, 2)
    OM._sticky_batch(2, 'posA', {}, estado, 2)         # ciclo 2 -> descarrega o 1 (flush)
    assert OM._STICKY.roomid_for('posA', fresh_roomids=['A', 'B']) == 'A'
    assert OM._STICKY.roomid_for('posB', fresh_roomids=['A', 'B']) == 'B'


def test_hero_turn_roomid_fresco_vs_velho():
    import time
    now = time.time()
    assert OM._hero_turn_roomid({'_hero_turn': {'ref': 'A', 'ts': now}}, now) == 'A'
    assert OM._hero_turn_roomid({'_hero_turn': {'ref': 'A', 'ts': now - 999}}, now) is None
    assert OM._hero_turn_roomid({}, now) is None


def _write_estado(tmp, hero_turn_ref):
    import json, time
    now = time.time()
    data = {
        'A': {'ts': now, 'room': 'T1', 'table': {'sb': 100},
              'players': [{'seat': 1, 'uid': 11, 'name': 'joao'}, {'seat': 2, 'uid': 12, 'name': 'maria'}]},
        'B': {'ts': now, 'room': 'T1', 'table': {'sb': 100},
              'players': [{'seat': 1, 'uid': 21, 'name': 'lucas'}, {'seat': 2, 'uid': 22, 'name': 'rafael'}]},
        '_hero_turn': {'ref': hero_turn_ref, 'ts': now},
    }
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    return tmp


def test_turn_anchor_abstem_se_vez_diferente_do_bind(tmp_path):
    OM.protobuf_state.advise_from_protobuf = lambda sel, *a, **k: {'status': 'ADVICE', 'sentinel': True}
    OM._STICKY = OM.table_sticky_bind.StickyBinder(min_score=2)
    OM._STICKY_FRAME.update(cycle=None, binds={}, roomids=set(), n=0)
    est = _write_estado(str(tmp_path / 'e.json'), hero_turn_ref='A')   # a VEZ é na mesa A
    crop_B = {1: {'raw': 'lucas'}, 2: {'raw': 'rafael'}}               # mas o crop casa com a mesa B
    out = OM._protobuf_advice(None, 'chip_ev', 'mid', estado_path=est, n_crops=2,
                              crop_seats=crop_B, pos='p0', cycle=1, use_sticky=True)
    assert out is None          # vez=A, bind=B -> ABSTÉM (não age na mesa errada)


def test_turn_anchor_age_quando_bind_bate_com_a_vez(tmp_path):
    OM.protobuf_state.advise_from_protobuf = lambda sel, *a, **k: {'status': 'ADVICE', 'sentinel': True}
    OM._STICKY = OM.table_sticky_bind.StickyBinder(min_score=2)
    OM._STICKY_FRAME.update(cycle=None, binds={}, roomids=set(), n=0)
    est = _write_estado(str(tmp_path / 'e.json'), hero_turn_ref='B')   # a VEZ é na mesa B
    crop_B = {1: {'raw': 'lucas'}, 2: {'raw': 'rafael'}}               # e o crop casa com B
    out = OM._protobuf_advice(None, 'chip_ev', 'mid', estado_path=est, n_crops=2,
                              crop_seats=crop_B, pos='p0', cycle=1, use_sticky=True)
    assert out and out.get('sentinel')    # vez=B, bind=B -> AGE


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
