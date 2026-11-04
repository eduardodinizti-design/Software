"""Gera fixtures sintéticas auditáveis; não substitui validação com cartas reais."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


RANKS = "23456789TJQKA"
SUITS = "shdc"
REAL_OBSERVED = {
    "2s", "3s", "4d", "5c", "5d", "7d", "7h", "8h",
    "As", "Jd", "Js", "Kc", "Kd", "Qh", "Th", "Ts",
}
MISSING_CARDS = tuple(rank + suit for rank in RANKS for suit in SUITS
                      if rank + suit not in REAL_OBSERVED)


def _load_rank_templates(project_root: Path) -> dict[str, np.ndarray]:
    """Extrai os glifos aceitos das evidências reais já auditadas."""
    report = json.loads((project_root / "docs/pppoker-image-validation.json").read_text("utf-8"))
    fixture_root = project_root / "tests/fixtures/heldout_cards"
    templates = {}
    for result in report["results"]:
        source = fixture_root / f"{result['sample']}.png"
        if not source.is_file():
            continue
        image = cv2.cvtColor(cv2.imread(str(source)), cv2.COLOR_BGR2RGB)
        reading = result["reading"]
        width, height = reading["diagnostics"]["image_size"]
        normalized = cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)
        for card in reading["diagnostics"]["hero"].get("cards", []):
            if not card.get("accepted"):
                continue
            x, y, w, h = card["rank_box"]
            templates.setdefault(card["card"][0], normalized[y:y+h, x:x+w].copy())
        for card in reading["diagnostics"].get("board", []):
            if not card.get("card"):
                continue
            x, y, w, h = card["box"]
            templates.setdefault(card["card"][0],
                                 normalized[y:y+round(h*.43), x:x+round(w*.55)].copy())
    return templates


def _rounded_card(canvas, x, y, width, height):
    mask = np.zeros(canvas.shape[:2], dtype=np.uint8)
    cv2.rectangle(mask, (x, y), (x + width, y + height), 255, -1)
    shadow = cv2.GaussianBlur(mask, (0, 0), 3.0)
    alpha = (shadow.astype(np.float32) / 255 * .30)[..., None]
    canvas[:] = np.clip(canvas * (1-alpha), 0, 255).astype(np.uint8)
    cv2.rectangle(canvas, (x, y), (x + width, y + height), (238, 238, 238), -1)


def _place_rank(canvas, rank, x, y, template):
    area = canvas[y:y+43, x:x+42]
    if template is None:
        cv2.putText(canvas, rank, (x+2, y+34), cv2.FONT_HERSHEY_DUPLEX,
                    1.0, (35, 35, 35), 2, cv2.LINE_AA)
        return "synthetic_font"
    tile = cv2.resize(template, (34, 42), interpolation=cv2.INTER_CUBIC)
    # Preserve the real glyph while matching the synthetic card brightness.
    gray = cv2.cvtColor(tile, cv2.COLOR_RGB2GRAY)
    ink = cv2.GaussianBlur((255-gray).astype(np.float32), (3, 3), .45) / 255
    for channel in range(3):
        area[:42, :34, channel] = np.clip(238*(1-ink)+28*ink, 0, 255)
    return "real_extracted"


def _place_suit(canvas, suit, x, y, project_root):
    mask = cv2.imread(str(project_root / f"visualpilot/pppoker/assets/suit_{suit}.png"), 0)
    if mask is None:
        raise FileNotFoundError(f"Molde de naipe ausente: {suit}")
    mask = cv2.resize(mask, (27, 31), interpolation=cv2.INTER_AREA)
    mask = cv2.GaussianBlur(mask, (3, 3), .35).astype(np.float32) / 255
    colour = {"h": (220, 25, 25), "d": (20, 80, 220),
              "c": (20, 150, 45), "s": (25, 25, 25)}[suit]
    target = canvas[y:y+31, x:x+27]
    for channel in range(3):
        target[..., channel] = np.clip(target[..., channel]*(1-mask)+colour[channel]*mask,0,255)


def render_card(base_rgb, card, project_root, rank_templates):
    if card[0] not in RANKS or card[1] not in SUITS or len(card) != 2:
        raise ValueError(f"Carta inválida: {card}")
    image = base_rgb.copy()
    # Carta única dentro do ROI board_turn calibrado em 835 x 1485.
    x, y, width, height = 477, 587, 84, 124
    _rounded_card(image, x, y, width, height)
    origin = _place_rank(image, card[0], x+5, y+2, rank_templates.get(card[0]))
    _place_suit(image, card[1], x+28, y+66, project_root)
    return image, origin


def generate(output, project_root=None):
    project_root = Path(project_root or Path(__file__).resolve().parents[2])
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    base_path = project_root / "tests/fixtures/actions/right_99.png"
    base_bgr = cv2.imread(str(base_path))
    if base_bgr is None:
        raise FileNotFoundError(base_path)
    base = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2RGB)
    if base.shape[:2] != (1485, 835):
        raise ValueError("A base deve medir exatamente 835 x 1485.")
    templates = _load_rank_templates(project_root)
    manifest = {"schema_version": 1, "scope": "synthetic_regression_only",
                "base": str(base_path.relative_to(project_root)),
                "real_observed": sorted(REAL_OBSERVED), "generated": {}}
    for card in MISSING_CARDS:
        image, origin = render_card(base, card, project_root, templates)
        target = output / f"{card}.png"
        ok = cv2.imwrite(str(target), cv2.cvtColor(image, cv2.COLOR_RGB2BGR),
                         [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise OSError(f"Não foi possível salvar {target}")
        manifest["generated"][card] = {
            "file": target.name, "rank_origin": origin,
            "suit_origin": "pppoker_asset", "synthetic": True,
        }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="tests/fixtures/synthetic_deck")
    args = parser.parse_args()
    manifest = generate(args.output)
    print(json.dumps({"generated": len(manifest["generated"]),
                      "synthetic_font_ranks": sorted({card[0] for card,data in manifest["generated"].items()
                                                      if data["rank_origin"]=="synthetic_font"})},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
