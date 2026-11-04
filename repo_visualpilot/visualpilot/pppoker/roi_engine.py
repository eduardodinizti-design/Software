"""Regiões calibradas para detectar mudanças relevantes sem inventar estado."""
from __future__ import annotations

from collections import OrderedDict
import hashlib

import numpy as np


REFERENCE_WIDTH = 835
REFERENCE_HEIGHT = 1485

# Coordenadas na captura original 835 x 1485, em (ymin, xmin, ymax, xmax).
# As margens incluem as caixas de evidência observadas nos dois frames reais.
REGIONS = OrderedDict([
    ("hand_id", ((970, 235, 1105, 615),)),
    ("total_pot", ((525, 345, 585, 500),)),
    ("board_flop", ((565, 170, 735, 475),)),
    ("board_turn", ((565, 465, 735, 575),)),
    ("board_river", ((565, 565, 735, 680),)),
    ("hero_cards", ((1160, 450, 1330, 630),)),
    ("hero_stack", ((1310, 350, 1385, 505),)),
    ("action_buttons", ((1370, 0, 1485, 835),)),
    ("observed_actions", (
        (125, 250, 315, 590),
        (345, 0, 1000, 220),
        (345, 590, 1150, 835),
        (1035, 250, 1320, 500),
    )),
])


def _validate_rgb(image: np.ndarray) -> None:
    if not isinstance(image, np.ndarray) or image.size == 0:
        raise ValueError("Imagem da mesa nula ou vazia.")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("A imagem da mesa deve usar RGB com três canais.")
    if image.shape[0] < 100 or image.shape[1] < 100:
        raise ValueError("Imagem da mesa pequena demais para calibrar as regiões.")


def scaled_box(box, width: int, height: int):
    """Converte uma âncora 835 x 1485 para a geometria recebida."""
    ymin, xmin, ymax, xmax = box
    return (
        max(0, min(height, round(ymin * height / REFERENCE_HEIGHT))),
        max(0, min(width, round(xmin * width / REFERENCE_WIDTH))),
        max(0, min(height, round(ymax * height / REFERENCE_HEIGHT))),
        max(0, min(width, round(xmax * width / REFERENCE_WIDTH))),
    )


def region_hashes(image: np.ndarray) -> dict[str, str]:
    """Hash exato por região; uma mudança de um byte nunca vira cache hit."""
    _validate_rgb(image)
    height, width = image.shape[:2]
    result = {}
    for name, boxes in REGIONS.items():
        digest = hashlib.blake2b(digest_size=16)
        for box in boxes:
            ymin, xmin, ymax, xmax = scaled_box(box, width, height)
            crop = np.ascontiguousarray(image[ymin:ymax, xmin:xmax])
            if crop.size == 0:
                raise ValueError(f"Região vazia após redimensionamento: {name}")
            digest.update(str(crop.shape).encode("ascii"))
            digest.update(crop.tobytes())
        result[name] = digest.hexdigest()
    return result


def frame_signature(image: np.ndarray) -> str:
    """Assinatura somente dos pixels que podem alterar a leitura publicada."""
    hashes = region_hashes(image)
    digest = hashlib.blake2b(digest_size=16)
    for name, value in hashes.items():
        digest.update(name.encode("ascii"))
        digest.update(value.encode("ascii"))
    return digest.hexdigest()


class TableROIEngine:
    """Mantém hashes por mesa e informa quais campos precisam ser revistos."""
    def __init__(self):
        self.previous: dict[str, str] | None = None
        self.metrics = {"frames": 0, "cache_hits": 0, "region_changes": 0,
                        "changes": {name: 0 for name in REGIONS}}

    def inspect(self, image: np.ndarray) -> dict:
        current = region_hashes(image)
        self.metrics["frames"] += 1
        if self.previous is None:
            changed = list(REGIONS)
            hand_changed = True
        else:
            changed = [name for name in REGIONS if current[name] != self.previous[name]]
            hand_changed = "hand_id" in changed
            if hand_changed:
                # Uma mão nova invalida todos os valores, mesmo que alguns pixels coincidam.
                changed = list(REGIONS)
        if not changed:
            self.metrics["cache_hits"] += 1
        else:
            self.metrics["region_changes"] += len(changed)
            for name in changed:
                self.metrics["changes"][name] += 1
        self.previous = current
        return {"changed": changed, "hand_changed": hand_changed,
                "cache_hit": not changed, "hashes": current}
