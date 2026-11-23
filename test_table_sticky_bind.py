"""Invariantes do binding grudento posição->roomid (anti-crossing do multi-mesa tilado PPPoker)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from table_sticky_bind import StickyBinder


def test_aprende_bind_confiante():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('B', 2)}, now=100)
    assert b.roomid_for(0, fresh_roomids=['A', 'B'], now=101) == 'A'
    assert b.roomid_for(1, fresh_roomids=['A', 'B'], now=101) == 'B'


def test_reusa_quando_ocr_falha():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('B', 2)}, now=100)
    # frame seguinte SEM binds (nome ilegível) -> ainda devolve o grudado
    live = b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={}, now=105)
    assert live == {0: 'A', 1: 'B'}


def test_retile_por_numero_de_paineis_zera():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('B', 3)}, now=100)
    # abriu/fechou mesa: agora 3 painéis -> mapa zera (não reusa posição antiga -> não cruza)
    live = b.observe(n_panels=3, fresh_roomids=['A', 'B', 'C'], frame_binds={}, now=101)
    assert live == {} and b.roomid_for(0, fresh_roomids=['A', 'B', 'C'], now=101) is None


def test_retile_por_conjunto_de_roomids_zera():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('B', 3)}, now=100)
    # mesmo nº de painéis, mas trocou um torneio (B->C) -> re-tile -> zera
    live = b.observe(n_panels=2, fresh_roomids=['A', 'C'], frame_binds={}, now=101)
    assert live == {}


def test_unicidade_move_roomid_de_posicao():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3)}, now=100)
    # depois A aparece com confiança na posição 1 -> sai da 0, fica só na 1 (nunca 2 pos no mesmo roomid)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={1: ('A', 3)}, now=101)
    assert b.roomid_for(1, fresh_roomids=['A', 'B'], now=101) == 'A'
    assert b.roomid_for(0, fresh_roomids=['A', 'B'], now=101) is None


def test_frame_ambiguo_nao_ensina():
    b = StickyBinder(min_score=2)
    # mesmo roomid 'A' casando em 2 posições no mesmo frame = ambíguo -> ignora ambos
    live = b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('A', 3)}, now=100)
    assert live == {}


def test_score_baixo_nao_aprende():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 1)}, now=100)   # score<min
    assert b.roomid_for(0, fresh_roomids=['A', 'B'], now=100) is None


def test_roomid_que_saiu_dos_frescos_vira_none():
    b = StickyBinder(min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3), 1: ('B', 3)}, now=100)
    # A parou de emitir (stale no protobuf) -> não está mais fresco -> abstém naquela posição
    assert b.roomid_for(0, fresh_roomids=['B'], now=100) is None


def test_ttl_expira():
    b = StickyBinder(confirm_ttl=10.0, min_score=2)
    b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: ('A', 3)}, now=100)
    assert b.roomid_for(0, fresh_roomids=['A', 'B'], now=109) == 'A'       # dentro do TTL
    assert b.roomid_for(0, fresh_roomids=['A', 'B'], now=111) is None      # velho -> abstém


def test_best_crop_ref_alimenta_o_binder():
    import table_binding as TB
    estado = {
        'A': {'players': [{'name': 'joaozinho'}, {'name': 'maria'}, {'name': 'pedro'}]},
        'B': {'players': [{'name': 'lucas'}, {'name': 'ana'}, {'name': 'rafael'}]},
    }
    # crop com nameplates OCR do torneio A (2 casam) -> (A, 2)
    crop_A = {1: {'raw': 'joaozinho'}, 2: {'raw': 'maria'}, 3: {'raw': 'xyz'}}
    ref, score = TB.best_crop_ref(crop_A, estado)
    assert ref == 'A' and score == 2
    # empate (1 de cada) -> ambíguo -> (None, 0), não ensina o binder
    crop_amb = {1: {'raw': 'maria'}, 2: {'raw': 'ana'}}
    assert TB.best_crop_ref(crop_amb, estado) == (None, 0)
    # integra no binder
    b = StickyBinder(min_score=2)
    live = b.observe(n_panels=2, fresh_roomids=['A', 'B'], frame_binds={0: (ref, score)}, now=1)
    assert live == {0: 'A'}


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
