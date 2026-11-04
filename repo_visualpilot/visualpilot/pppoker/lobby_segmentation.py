"""VisualPilot - Fase 1 / Módulo 2: Segmentação de Cartões e Janela do Lobby PPPoker.

Identifica a janela do lobby do PPPoker (mesmo em resolução/posição arbitrária),
segmenta automaticamente os cartões de torneio da lista, classifica a integridade
(completo vs. cortado pelo scroll/viewport) e mapeia as sub-regiões e pontos de clique.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import cv2
import numpy as np

from .core import Region, require_rgb


# Proporções relativas das sub-regiões internas de um cartão do lobby PPPoker:
# [rel_x, rel_y, rel_w, rel_h] normalizados (0.0 a 1.0)
SUB_REGIONS_TEMPLATE = {
    "name": (0.16, 0.22, 0.22, 0.50),        # Nome do torneio / logo
    "buyin_prize": (0.39, 0.16, 0.40, 0.26),  # Buy-in / Premiação
    "start_time": (0.39, 0.62, 0.42, 0.24),   # Horário de início
    "status": (0.80, 0.20, 0.18, 0.60),       # Status / Botão (ex: Aberto / Encerrado)
}


def locate_lobby_window(
    desktop_image: np.ndarray,
    windows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Identifica a janela do lobby do PPPoker na captura do desktop.
    
    Aceita lista de janelas do Win32 (via window_geometry) ou busca visualmente.
    """
    require_rgb(desktop_image)
    dh, dw = desktop_image.shape[:2]

    # 1. Se recebemos as janelas nativas do sistema, busca a janela de título PPPoker
    if windows:
        for win in windows:
            title = win.get("title", "").lower()
            x, y, w, h = win.get("box", [0, 0, 0, 0])
            if "pppoker" in title and w > 200 and h > 300:
                ratio = w / float(max(1, h))
                if 0.40 <= ratio <= 0.75:
                    x1 = max(0, min(dw - 1, x))
                    y1 = max(0, min(dh - 1, y))
                    x2 = max(x1 + 1, min(dw, x + w))
                    y2 = max(y1 + 1, min(dh, y + h))
                    crop = desktop_image[y1:y2, x1:x2].copy()
                    return {
                        "status": "found",
                        "method": "native_window_title",
                        "box": [x, y, w, h],
                        "crop_box": [x1, y1, x2 - x1, y2 - y1],
                        "image": crop,
                        "origin": [x1, y1]
                    }

    # 2. Se a imagem fornecida já é a própria janela do lobby (proporção retrato)
    ratio = dw / float(max(1, dh))
    if 0.40 <= ratio <= 0.75 and dw >= 250 and dh >= 400:
        return {
            "status": "found",
            "method": "direct_window_image",
            "box": [0, 0, dw, dh],
            "crop_box": [0, 0, dw, dh],
            "image": desktop_image.copy(),
            "origin": [0, 0]
        }

    # 3. Varredura visual no desktop por área com padrão de cartões empilhados
    gray = cv2.cvtColor(desktop_image, cv2.COLOR_RGB2GRAY)
    sobel = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    edge_map = (np.abs(sobel) > 40).astype(np.uint8)

    contours, _ = cv2.findContours(edge_map, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        r = w / float(max(1, h))
        if 0.42 <= r <= 0.70 and w >= 280 and h >= 500:
            candidates.append((w * h, [x, y, w, h]))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        x, y, w, h = candidates[0][1]
        crop = desktop_image[y:y + h, x:x + w].copy()
        return {
            "status": "found",
            "method": "visual_contour_search",
            "box": [x, y, w, h],
            "crop_box": [x, y, w, h],
            "image": crop,
            "origin": [x, y]
        }

    return {
        "status": "not_found",
        "method": "none",
        "box": [0, 0, dw, dh],
        "crop_box": [0, 0, dw, dh],
        "image": desktop_image.copy(),
        "origin": [0, 0]
    }


def segment_tournament_cards(
    lobby_image: np.ndarray,
    origin: tuple[int, int] = (0, 0),
    min_card_width: int = 240,
    min_card_height: int = 40
) -> list[dict[str, Any]]:
    """Segmenta automaticamente todos os cartões de torneio visíveis no lobby.
    
    Identifica cartões completos e cartões cortados nas bordas do scroll.
    Calcula as sub-regiões relativas e o ponto de clique de cada cartão.
    """
    require_rgb(lobby_image)
    lh, lw = lobby_image.shape[:2]
    ox, oy = origin

    # 1. Determina as margens horizontais e a coluna dos cartões
    card_margin_left = int(round(lw * 0.038))
    card_width = int(round(lw * 0.95))
    if card_margin_left + card_width > lw:
        card_width = lw - (2 * card_margin_left)

    col = lobby_image[:, card_margin_left:card_margin_left + card_width]
    row_mean = col.mean(axis=(1, 2))

    # O fundo escuro entre cartões no PPPoker tem intensidade baixa (< 32)
    # Detecta blocos contínuos de linhas escuras de fundo (separadores entre cartões)
    bg_threshold = min(34.0, max(24.0, float(np.percentile(row_mean, 15)) + 4.0))
    is_dark = (row_mean <= bg_threshold).astype(np.uint8)

    gaps = np.where(is_dark == 1)[0]
    if len(gaps) < 2:
        return []

    diff = np.diff(gaps)
    split_indices = np.where(diff > 1)[0]
    blocks = np.split(gaps, split_indices + 1)
    
    # Blocos escuros com altura suficiente para serem separadores reais (>= 6 px)
    dark_blocks = [(b[0], b[-1], len(b)) for b in blocks if len(b) >= 6]
    if len(dark_blocks) < 2:
        return []

    # 2. Identifica os candidatos a cartões entre blocos escuros
    candidate_spans: list[tuple[int, int, int]] = []
    
    # Caso especial: cartão cortado no topo da imagem antes do primeiro bloco escuro
    if dark_blocks[0][0] > min_card_height:
        first_top = 0
        first_bottom = dark_blocks[0][0] - 1
        candidate_spans.append((first_top, first_bottom, first_bottom - first_top + 1))

    # Cartões entre blocos escuros consecutivos
    for i in range(len(dark_blocks) - 1):
        sy = dark_blocks[i][1] + 1
        ey = dark_blocks[i + 1][0] - 1
        h = ey - sy + 1
        if h >= min_card_height:
            candidate_spans.append((sy, ey, h))

    # Caso especial: cartão cortado no rodapé após o último bloco escuro
    if lh - 1 - dark_blocks[-1][1] >= min_card_height:
        last_top = dark_blocks[-1][1] + 1
        last_bottom = lh - 1
        candidate_spans.append((last_top, last_bottom, last_bottom - last_top + 1))

    if not candidate_spans:
        return []

    # 3. Detecta a altura padrão dos cartões (mediana dos segmentos significativos)
    # Um cartão de torneio típico no PPPoker tem altura entre 140 e 200 px (em escala 787p)
    # Proporção típica largura/altura é entre 3.8 e 5.0
    valid_card_heights = [
        s[2] for s in candidate_spans 
        if 3.2 <= (card_width / float(max(1, s[2]))) <= 5.5 and s[0] > lh * 0.20
    ]
    
    median_height = float(np.median(valid_card_heights)) if valid_card_heights else 168.0

    # Detecta o início da área rolável de torneios:
    # No PPPoker com cabeçalho/abas, há um vão escuro largo (>= 20px) separando as abas da lista.
    # Se a imagem já for apenas a lista rolada/recortada, a lista começa no primeiro cartão (y=0).
    header_gaps = [b for b in dark_blocks if b[2] >= 20 and b[0] < lh * 0.50]
    if header_gaps:
        min_list_y = header_gaps[-1][1] + 1
    else:
        min_list_y = 0

    # 4. Filtra e classifica os cartões de torneio
    cards: list[dict[str, Any]] = []
    card_index = 0

    for sy, ey, sh in candidate_spans:
        # Descarta elementos acima do início da lista de torneios
        if ey < min_list_y:
            continue

        ratio = card_width / float(max(1, sh))
        height_ratio = sh / median_height

        # Se for muito fino (< 35% da altura padrão), não é cartão de torneio
        if sh < median_height * 0.35:
            continue

        is_complete = bool(0.85 <= height_ratio <= 1.15)
        clip_reason = None
        if not is_complete:
            if sy <= 10 or (sy < lh * 0.40 and sh < median_height):
                clip_reason = "clipped_top"
            elif ey >= lh - 10:
                clip_reason = "clipped_bottom"
            else:
                clip_reason = "irregular_height"

        lx = card_margin_left
        ly = sy
        lw_box = card_width
        lh_box = sh

        ax = lx + ox
        ay = ly + oy

        center_x = lx + (lw_box / 2.0)
        center_y = ly + (lh_box / 2.0)

        # Mapeia as 4 sub-regiões internas proporcionais
        sub_regions = {}
        for region_name, (rx, ry, rw, rh) in SUB_REGIONS_TEMPLATE.items():
            sub_regions[region_name] = {
                "local_box": [
                    int(round(lx + (rx * lw_box))),
                    int(round(ly + (ry * lh_box))),
                    int(round(rw * lw_box)),
                    int(round(rh * lh_box))
                ],
                "absolute_box": [
                    int(round(ax + (rx * lw_box))),
                    int(round(ay + (ry * lh_box))),
                    int(round(rw * lw_box)),
                    int(round(rh * lh_box))
                ]
            }

        card_entry = {
            "index": card_index,
            "complete": is_complete,
            "clip_reason": clip_reason,
            "visibility_ratio": round(min(1.0, height_ratio), 3),
            "local_box": [lx, ly, lw_box, lh_box],
            "absolute_box": [ax, ay, lw_box, lh_box],
            "click_point_local": [round(center_x, 1), round(center_y, 1)],
            "click_point_absolute": [round(center_x + ox, 1), round(center_y + oy, 1)],
            "sub_regions": sub_regions
        }
        cards.append(card_entry)
        card_index += 1

    return cards


def annotate_segmented_lobby(
    lobby_image: np.ndarray,
    cards: list[dict[str, Any]],
    window_box: list[int] | None = None
) -> np.ndarray:
    """Desenha retângulos, mira e identificadores visuais na imagem para auditoria humana."""
    annotated = lobby_image.copy()

    if window_box and len(window_box) == 4:
        wx, wy, ww, wh = window_box
        cv2.rectangle(annotated, (wx, wy), (wx + ww, wy + wh), (255, 200, 0), 2)
        cv2.putText(annotated, "JANELA LOBBY", (wx + 10, wy + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2, cv2.LINE_AA)

    for card in cards:
        lx, ly, lw, lh = card["local_box"]
        cx, cy = int(card["click_point_local"][0]), int(card["click_point_local"][1])
        is_complete = card["complete"]

        border_color = (0, 220, 100) if is_complete else (0, 140, 255)
        thickness = 2

        cv2.rectangle(annotated, (lx, ly), (lx + lw, ly + lh), border_color, thickness)
        cv2.drawMarker(annotated, (cx, cy), border_color, cv2.MARKER_CROSS, 8, 2)

        status_label = f"#{card['index']} COMPLETO" if is_complete else f"#{card['index']} CORTADO ({card['clip_reason']})"
        cv2.putText(annotated, status_label, (lx + 8, ly + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, border_color, 2, cv2.LINE_AA)

        if is_complete:
            for rname, rdata in card["sub_regions"].items():
                rx, ry, rw, rh = rdata["local_box"]
                cv2.rectangle(annotated, (rx, ry), (rx + rw, ry + rh), (200, 200, 50), 1)

    return annotated


def save_segmentation_artifacts(
    output_dir: Path | str,
    lobby_image: np.ndarray,
    cards: list[dict[str, Any]],
    metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Salva segments.json, annotated.png e os recortes individuais para validação."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    annotated = annotate_segmented_lobby(lobby_image, cards)
    annotated_path = out / "annotated.png"
    cv2.imwrite(str(annotated_path), annotated)

    saved_crops = []
    for card in cards:
        lx, ly, lw, lh = card["local_box"]
        crop = lobby_image[ly:ly + lh, lx:lx + lw]
        crop_name = f"card_{card['index']:02d}.png"
        crop_path = out / crop_name
        cv2.imwrite(str(crop_path), crop)
        saved_crops.append(crop_name)
        card["crop_file"] = crop_name

    complete_count = sum(1 for c in cards if c["complete"])
    clipped_count = len(cards) - complete_count

    report = {
        "module": "phase1_module2",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "total_cards_found": len(cards),
        "complete_cards": complete_count,
        "clipped_cards": clipped_count,
        "cards": cards,
        "artifacts": {
            "annotated_image": annotated_path.name,
            "crops": saved_crops
        }
    }
    if metadata:
        report["metadata"] = metadata

    def _json_default(obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    segments_json_path = out / "segments.json"
    segments_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

    return report


def process_lobby_image(
    image_path: Path | str,
    output_dir: Path | str,
    origin: tuple[int, int] = (0, 0)
) -> dict[str, Any]:
    """Fluxo principal: lê imagem, localiza janela, segmenta cartões e grava artefatos."""
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Imagem do lobby não encontrada: {path}")

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Não foi possível abrir o arquivo de imagem: {path}")

    window_info = locate_lobby_window(image)
    cards = segment_tournament_cards(window_info["image"], origin=tuple(window_info["origin"]))

    metadata = {
        "source_image": path.name,
        "image_size": [image.shape[1], image.shape[0]],
        "window_detection": {
            "status": window_info["status"],
            "method": window_info["method"],
            "box": window_info["box"]
        }
    }

    return save_segmentation_artifacts(output_dir, window_info["image"], cards, metadata=metadata)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Módulo 2: Segmentação de cartões no lobby do PPPoker.")
    parser.add_argument("--image", type=Path, required=True, help="Caminho do PNG capturado do lobby.")
    parser.add_argument("--output", type=Path, required=True, help="Pasta de saída para os artefatos.")
    parser.add_argument("--origin", nargs=2, type=int, default=[0, 0], metavar=("X", "Y"),
                        help="Origem absoluta do recorte no desktop.")
    args = parser.parse_args(argv)

    try:
        report = process_lobby_image(args.image, args.output, origin=tuple(args.origin))
        print(f"Segmentação concluída:")
        print(f"  Cartões detectados: {report['total_cards_found']}")
        print(f"  Cartões completos: {report['complete_cards']}")
        print(f"  Cartões cortados: {report['clipped_cards']}")
        print(f"  Imagem anotada salva em: {args.output / 'annotated.png'}")
        print(f"  Dados salvos em: {args.output / 'segments.json'}")
        return 0
    except Exception as exc:
        print(f"Erro na segmentação: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
