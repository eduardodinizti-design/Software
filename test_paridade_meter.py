"""Testes do medidor de paridade (parser dos logs PARIDADE do operador)."""
import paridade_meter as pm

SAMPLE = """
[010] PARIDADE: PB[AhKh CO open_raise]=raise | OCR[AhKh CO]=raise
[011] PARIDADE: PB[6d3c UTG+1 open_shove]=fold | OCR[?? UTG+1]=ABSTAIN:HERO_CARDS_UNKNOWN   <-- DIVERGE
[012] PARIDADE: PB[4cTd CO call_off_vs_open_shove]=fold | OCR[4sTh CO]=fold
[013] PARIDADE: PB[2h2c BB vs_open]=call | OCR[2h2c BB]=fold   <-- DIVERGE
[014] PARIDADE: PB[?? SB ?]=ABSTAIN:X | OCR[Jd9d SB]=raise   <-- DIVERGE
[015] linha irrelevante qualquer
[016] PARIDADE: PB[?? ? ?]=ABSTAIN:Y | OCR[?? ?]=ABSTAIN:HERO_CARDS_UNKNOWN
"""


def test_parse_contagens():
    p = pm.parse_text(SAMPLE)
    assert p.total == 6
    # linhas: 010 ambos ok; 011 pb resgata; 012 ambos ok; 013 ambos ok; 014 ocr resgata; 016 ninguem
    assert p.pb_completo == 4          # 010,011,012,013 (011 PB=fold é leitura válida)
    assert p.ocr_completo == 4         # 010,012,013,014
    assert p.pb_resgata == 1           # 011
    assert p.ocr_resgata == 1          # 014
    assert p.nenhum == 1               # 016
    assert p.ambos == 3                # 010,012,013


def test_concordancia_rec_e_hero():
    p = pm.parse_text(SAMPLE)
    # rec: 010 raise=raise (ok); 012 fold=fold (ok); 013 call!=fold (diverge) -> 2/3
    assert p.concordam_rec == 2
    # hero: 010 AhKh=AhKh (ok); 012 4cTd!=4sTh (diverge); 013 2h2c=2h2c (ok) -> 2/3
    assert p.concordam_hero == 2
    r = p.resumo()
    assert r["decisoes"] == 6
    assert r["protobuf_resgata_ocr"] == 1


def test_resumo_percentuais():
    p = pm.parse_text(SAMPLE)
    r = p.resumo()
    assert r["protobuf_completo_%"] == round(100 * 4 / 6, 1)   # 4/6 = 66.7
    assert r["ocr_completo_%"] == round(100 * 4 / 6, 1)
