"""Gera o dataset sintetico (train/val) + data.yaml p/ treinar o detector de cartas YOLOv8.
Usa fundos de mesa REAIS card-free (quebras/mesa vazia) + o gerador synth (cartas rotuladas).
Uso: python -I vision_yolo/make_train_data.py"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

from vision_yolo.synth import generate
from vision_yolo.classes import CLASSES

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.join(HERE, "dataset")
RES = os.path.abspath(os.path.join(HERE, "..", "research", "suprema_cocos"))

# Fundos card-free (quebra "Intervalo" + mesa vazia). Mais fundos = melhor generalizacao.
BG_NAMES = ["raise_c_01.png", "raise_c_02.png", "raise_c_03.png", "suprema_tela.png"]


def main():
    bgs = [os.path.join(RES, n) for n in BG_NAMES if os.path.exists(os.path.join(RES, n))]
    if not bgs:
        print("[erro] sem fundos em", RES); return 1
    print("[data] fundos:", len(bgs))
    import shutil
    for sub in ("images", "labels"):            # limpa dataset antigo (evita stale)
        shutil.rmtree(os.path.join(DS, sub), ignore_errors=True)
    generate(bgs, 800, os.path.join(DS, "images", "train"), os.path.join(DS, "labels", "train"), seed=1)
    generate(bgs, 160, os.path.join(DS, "images", "val"), os.path.join(DS, "labels", "val"), seed=2)
    yaml = os.path.join(DS, "data.yaml")
    with open(yaml, "w", encoding="utf-8") as fh:
        fh.write("path: %s\n" % DS.replace("\\", "/"))
        fh.write("train: images/train\nval: images/val\n")
        fh.write("nc: %d\n" % len(CLASSES))
        fh.write("names:\n")
        for i, c in enumerate(CLASSES):
            fh.write("  %d: %s\n" % (i, c))
    print("[data] train=800 val=160 ->", DS)
    print("[data] data.yaml ->", yaml)
    return 0


if __name__ == "__main__":
    sys.exit(main())
