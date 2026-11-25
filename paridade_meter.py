"""MEDIDOR DE PARIDADE da percepção — quantifica, a partir dos logs do operador
(`--protobuf`), quão bem lemos os cenários de decisão: protobuf × OCR.

O operador emite por decisão uma linha:
  [NNN] PARIDADE: PB[<hero> <pos> <spot>]=<rec> | OCR[<hero> <pos>]=<rec>[   <-- DIVERGE]

Este módulo parseia essas linhas e agrega:
  - protobuf_completo: % de decisões em que o protobuf leu hero+pos (não '??'/ABSTAIN)
  - ocr_completo:      idem p/ o OCR
  - concordam_rec:     % (entre os que ambos leram) em que a RECOMENDAÇÃO bate
  - concordam_hero:    % em que as CARTAS do hero batem (naipes confirmados)
  - protobuf_resgata:  nº de decisões onde o protobuf leu e o OCR NÃO (o ganho real)
  - divergencias:      lista p/ revisão

NÃO é "correção contra verdade absoluta" (não há oráculo); é paridade + completude,
com divergências sinalizadas. Ver [[nvt-upgrade-percepcao-protobuf]].
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_LINE = re.compile(
    r"PARIDADE:\s*PB\[(?P<pbhero>\S+)\s+(?P<pbpos>\S+)\s+(?P<pbspot>\S+)\]=(?P<pbrec>\S+)"
    r"\s*\|\s*OCR\[(?P<ocrhero>\S+)\s+(?P<ocrpos>\S+)\]=(?P<ocrrec>\S+?)"
    r"(?P<diverge>\s*<--\s*DIVERGE)?\s*$"
)


def _ok_hero(h):
    return bool(h) and h != "??"


def _ok_rec(rec):
    return bool(rec) and not rec.startswith("ABSTAIN")


@dataclass
class Paridade:
    total: int = 0
    pb_completo: int = 0
    ocr_completo: int = 0
    ambos: int = 0
    concordam_rec: int = 0
    concordam_hero: int = 0
    pb_resgata: int = 0        # PB leu, OCR não (ganho do protobuf)
    ocr_resgata: int = 0       # OCR leu, PB não
    nenhum: int = 0            # ninguém leu
    divergencias: list = field(default_factory=list)

    def pct(self, n):
        return round(100.0 * n / self.total, 1) if self.total else 0.0

    def resumo(self):
        return {
            "decisoes": self.total,
            "protobuf_completo_%": self.pct(self.pb_completo),
            "ocr_completo_%": self.pct(self.ocr_completo),
            "protobuf_resgata_ocr": self.pb_resgata,
            "ocr_resgata_protobuf": self.ocr_resgata,
            "ninguem_leu": self.nenhum,
            "concordam_rec_%(entre ambos)": round(100.0 * self.concordam_rec / self.ambos, 1) if self.ambos else None,
            "concordam_hero_%(entre ambos)": round(100.0 * self.concordam_hero / self.ambos, 1) if self.ambos else None,
            "divergencias_rec": len([d for d in self.divergencias if d["tipo"] == "rec"]),
        }


def parse_text(text: str) -> Paridade:
    p = Paridade()
    for line in text.splitlines():
        m = _LINE.search(line)
        if not m:
            continue
        g = m.groupdict()
        p.total += 1
        pb_ok = _ok_hero(g["pbhero"]) and _ok_rec(g["pbrec"])
        ocr_ok = _ok_hero(g["ocrhero"]) and _ok_rec(g["ocrrec"])
        if pb_ok:
            p.pb_completo += 1
        if ocr_ok:
            p.ocr_completo += 1
        if pb_ok and ocr_ok:
            p.ambos += 1
            if g["pbrec"] == g["ocrrec"]:
                p.concordam_rec += 1
            else:
                p.divergencias.append(dict(tipo="rec", pb=g["pbrec"], ocr=g["ocrrec"],
                                           hero=g["pbhero"], pos=g["pbpos"], spot=g["pbspot"]))
            if g["pbhero"] == g["ocrhero"]:
                p.concordam_hero += 1
            else:
                p.divergencias.append(dict(tipo="hero", pb=g["pbhero"], ocr=g["ocrhero"],
                                           pos=g["pbpos"], spot=g["pbspot"]))
        elif pb_ok and not ocr_ok:
            p.pb_resgata += 1
        elif ocr_ok and not pb_ok:
            p.ocr_resgata += 1
        else:
            p.nenhum += 1
    return p


def parse_file(path: str) -> Paridade:
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse_text(f.read())


def _main(argv=None):
    import argparse
    import glob
    import json
    p = argparse.ArgumentParser(description="Medidor de paridade da percepção (protobuf x OCR)")
    p.add_argument("logs", nargs="*", help="Arquivos de log do operador (ou glob)")
    p.add_argument("--show-diverge", type=int, default=10, help="Quantas divergências listar")
    args = p.parse_args(argv)
    paths = []
    for a in (args.logs or []):
        paths += glob.glob(a)
    if not paths:
        print("Nenhum log. Passe os caminhos dos logs do operador (--protobuf).")
        return 1
    agg = Paridade()
    for path in paths:
        sub = parse_file(path)
        agg.total += sub.total
        for k in ("pb_completo", "ocr_completo", "ambos", "concordam_rec", "concordam_hero",
                  "pb_resgata", "ocr_resgata", "nenhum"):
            setattr(agg, k, getattr(agg, k) + getattr(sub, k))
        agg.divergencias += sub.divergencias
    print("=== MEDIDOR DE PARIDADE (%d log[s]) ===" % len(paths))
    print(json.dumps(agg.resumo(), ensure_ascii=False, indent=1))
    if agg.divergencias and args.show_diverge:
        print("--- divergências (amostra) ---")
        for d in agg.divergencias[:args.show_diverge]:
            print("  ", d)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main())
