"""Binding roomID->coluna por VISÃO (OCR do ID no feltro). Lógica PURA de casamento, com os IDs REAIS
lidos por OCR das capturas de 2 e 4 telas (23/11). Prova que a INVERSÃO que causou 'confusão entre as
mesas' ao vivo fica corrigida."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_tile_binder import _mid_token, _matches, match_rooms_to_columns, TileBinder

# IDs REAIS lidos por OCR do feltro (capturas 23/11):
FELT = {
    0: "112314625_50050813539_172315",   # Freeze Mesa 5  -> tabela 50813539
    1: "112314625_11950813920_40847",    # Bounty Mesa 2  -> tabela 50813920
    2: "112314625_84550812122_309130",   # WarmUp Mesa 7  -> tabela 50812122
    3: "112314625_64350812180_487112",   # Plus Mesa 2    -> tabela 50812180
}
# roomIDs do stream (formato <torneio>_<tabela>_<seat>), como o hook entrega:
R539 = "14625_50813539_5"
R920 = "14625_50813920_2"
R122 = "14625_50812122_7"
R180 = "14625_50812180_2"


def test_mid_token_feltro_e_stream():
    assert _mid_token("112314625_50050813539_172315") == "50050813539"
    assert _mid_token(R539) == "50813539"
    assert _mid_token("") == "" and _mid_token(None) == ""


def test_matches_substring_feltro_vs_stream():
    # o feltro traz '50050813539' e o stream '50813539' — um contém o outro
    assert _matches(FELT[0], R539) is True
    assert _matches(FELT[0], R920) is False


def test_casamento_2_telas():
    col_ids = {0: FELT[0], 1: FELT[1]}
    assert match_rooms_to_columns(col_ids, [R539, R920]) == {R539: 0, R920: 1}


def test_corrige_a_inversao_do_bug_ao_vivo():
    # BUG 23/11: o agente clicou room ...539 em col1(DIR) e room ...920 em col0(ESQ) — INVERTIDO.
    # Na tela, ...539 está na ESQUERDA (col0) e ...920 na DIREITA (col1). O binder tem que dar o
    # mapa CORRETO (não o invertido).
    col_ids = {0: FELT[0], 1: FELT[1]}
    m = match_rooms_to_columns(col_ids, [R539, R920])
    assert m[R539] == 0 and m[R920] == 1           # correto
    assert not (m[R539] == 1 and m[R920] == 0)     # jamais o invertido do bug


def test_casamento_4_telas_todas_corretas():
    m = match_rooms_to_columns(FELT, [R539, R920, R122, R180])
    assert m == {R539: 0, R920: 1, R122: 2, R180: 3}


def test_sala_sem_casar_fica_de_fora_para_fallback():
    # uma sala que não está em nenhuma coluna não é mapeada (o chamador usa fallback só p/ ela)
    desconhecida = "14625_99999999_1"
    m = match_rooms_to_columns({0: FELT[0], 1: FELT[1]}, [R539, desconhecida])
    assert m == {R539: 0} and desconhecida not in m


def test_nunca_duas_salas_na_mesma_coluna():
    m = match_rooms_to_columns(FELT, [R539, R920, R122, R180])
    assert len(set(m.values())) == len(m.values())


def test_ocr_ruidoso_ainda_casa_pelo_token_longo():
    # OCR às vezes gruda ruído nas pontas (blinds/timer); o token longo da mesa ainda casa
    sujo = {0: "0836750 025048 112314625_50050813539_172315 28"}
    assert match_rooms_to_columns(sujo, [R539]) == {R539: 0}


def test_binder_usa_reader_injetado_e_recasa_no_retile():
    # TileBinder com reader e columns injetados (sem Suprema/OCR) — testa o cache + re-ligação.
    reads = [dict(FELT), dict(FELT)]               # 2 leituras iguais
    calls = {"n": 0}

    def fake_reader(hwnd, n):
        calls["n"] += 1
        return reads[min(calls["n"] - 1, len(reads) - 1)]

    b = TileBinder(hwnd=1, reader=fake_reader, columns_fn=lambda: 4)
    b.ensure([R539, R920, R122, R180])
    assert b.column_of(R539) == 0 and b.column_of(R180) == 3 and b.n_cols == 4
    assert calls["n"] == 1
    b.ensure([R539, R920, R122, R180])             # estável -> NÃO re-lê
    assert calls["n"] == 1


def test_mantem_ultimo_bom_quando_ocr_falha_num_ciclo():
    # KEEP-LAST-GOOD: 1ª leitura casa as 4; 2ª (re-bind) vem VAZIA (OCR falhou) -> mantém o mapa bom,
    # NÃO derruba p/ None (que acionaria o fallback de ordem, que pode trocar as mesas).
    reads = [dict(FELT), {}]            # 2ª passada: OCR retornou nada
    calls = {"n": 0}

    def rdr(hwnd, n):
        i = calls["n"]
        calls["n"] += 1
        return reads[min(i, len(reads) - 1)]

    b = TileBinder(hwnd=1, reader=rdr, columns_fn=lambda: 4, max_age=0.0)  # max_age=0 -> sempre re-lê
    b.ensure([R539, R920, R122, R180])
    assert b.column_of(R539) == 0 and b.column_of(R180) == 3
    b.ensure([R539, R920, R122, R180])                 # OCR vazio nesta passada
    assert b.column_of(R539) == 0 and b.column_of(R180) == 3   # manteve o bom, não virou None


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
