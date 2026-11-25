"""Gera o dataset.yaml do ultralytics a partir de classes.py (FONTE ÚNICA).
Rode sempre que mexer nas classes:  python -I vision_yolo/make_dataset_yaml.py
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from vision_yolo import classes as C   # noqa: E402

YAML = os.path.join(_HERE, "dataset.yaml")


def render() -> str:
    lines = [
        "# GERADO por make_dataset_yaml.py a partir de classes.py — NÃO editar à mão.",
        "# Estrutura esperada (preenchida no F1):",
        "#   vision_yolo/data/images/{train,val}/*.png",
        "#   vision_yolo/data/labels/{train,val}/*.txt  (YOLO: cls cx cy w h normalizados)",
        "path: data",
        "train: images/train",
        "val: images/val",
        "",
        "names:",
    ]
    for i, name in enumerate(C.CLASSES):
        lines.append("  %d: %s" % (i, name))
    lines.append("")
    lines.append("# nc (número de classes) = %d" % C.num_classes())
    return "\n".join(lines) + "\n"


def main():
    txt = render()
    with open(YAML, "w", encoding="utf-8") as f:
        f.write(txt)
    print("escrito: %s  (%d classes)" % (YAML, C.num_classes()))


if __name__ == "__main__":
    main()
