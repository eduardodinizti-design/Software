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


def detect_lobby_viewport(image: np.ndarray) -> tuple[int, int, int, int]:
    """Localiza a área útil rolável da lista de torneios dentro da janela do lobby.
    
    Retorna (vx, vy, vw, vh) em pixels relativos à imagem do lobby.
    """
    require_rgb(image)
    h, w = image.shape[:2]

    # Cartões ocupam tipicamente 90% a 96% da largura útil da lista
    margin_x = int(w * 0.035)
    col_w = w - (2 * margin_x)
    col = image[:, margin_x:margin_x + col_w]

    # Intensidade média horizontal por linha
    row_intensity = col.mean(axis=(1, 2))
    bg_level = float(np.percentile(row_intensity, 15))
    card_threshold = bg_level + 6.0

    # Linhas ativas
    is_card = (row_intensity > card_threshold).astype(np.uint8)
    kernel = np.ones(5, dtype=np.uint8)
    closed = cv2.morphologyEx(is_card, cv2.MORPH_CLOSE, kernel)

    # Encontra o primeiro bloco de cartões (abaixo das abas do topo, tipicamente y > 0.25*h)
    min_start_y = int(h * 0.25)
    starts = np.where((closed[min_start_y:] == 1) & (np.roll(closed[min_start_y:], 1) == 0))[0]

    if starts.size > 0:
        viewport_y = min_start_y + int(starts[0])
    else:
        viewport_y = min_start_y

    viewport_h = h - viewport_y
    return (margin_x, viewport_y, col_w, viewport_h)


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
                # Proporção retrato característica do lobby (0.40 a 0.75)
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

    # 2. Se a imagem fornecida já é a própria janela do lobby
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

    # Busca componente conexo com aspecto de janela de lobby
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
    # Os cartões no PPPoker são centralizados com ~3% a 4% de margem em cada lado
    card_margin_left = int(round(lw * 0.038))
    card_width = int(round(lw * 0.95))
    if card_margin_left + card_width > lw:
        card_width = lw - (2 * card_margin_left)

    col = lobby_image[:, card_margin_left:card_margin_left + card_width]
    row_intensity = col.mean(axis=(1, 2))
    bg_level = float(np.percentile(row_intensity, 15))
    card_threshold = bg_level + 6.0

    # Linhas onde há conteúdo de cartão (mais claro que o vão de fundo)
    is_card = (row_intensity > card_threshold).astype(np.uint8)

    # Fecha pequenos sulcos/linhas internas dentro do cartão (gaps < 5px)
    kernel = np.ones(5, dtype=np.uint8)
    closed = cv2.morphologyEx(is_card, cv2.MORPH_CLOSE, kernel)

    # 2. Agrupa intervalos contínuos de linhas verticais
    raw_segments: list[tuple[int, int, int]] = []
    in_card = False
    start_y = 0

    for y in range(lh):
        if closed[y] and not in_card:
            in_card = True
            start_y = y
        elif not closed[y] and in_card:
            in_card = False
            raw_segments.append((start_y, y - 1, y - start_y))

    if in_card:
        raw_segments.append((start_y, lh - 1, lh - start_y))

    # 3. Filtra apenas os cartões que estão na área rolável de torneios
    # No PPPoker, a lista começa abaixo dos banners e abas (tipicamente y > 0.30 * lh)
    min_list_y = int(lh * 0.30)
    tournament_segments = [s for s in raw_segments if s[1] >= min_list_y and s[2] >= min_card_height]

    if not tournament_segments:
        return []

    # 4. Estima a altura padrão de um cartão completo (mediana dos segmentos significativos)
    significant_heights = [s[2] for s in tournament_segments if s[2] > lh * 0.07]
    median_height = float(np.median(significant_heights)) if significant_heights else 168.0

    cards: list[dict[str, Any]] = []

    for index, (sy, ey, sh) in enumerate(tournament_segments):
        # Validação de integridade do cartão:
        # Altura esperada varia no máximo +-12% da mediana
        height_ratio = sh / median_height
        is_complete = bool(0.88 <= height_ratio <= 1.15)
        
        clip_reason = None
        if not is_complete:
            if sy <= min_list_y + 10:
                clip_reason = "clipped_top"
            elif ey >= lh - 10:
                clip_reason = "clipped_bottom"
            else:
                clip_reason = "irregular_height"

        # Coordenadas locais (dentro da imagem do lobby)
        lx = card_margin_left
        ly = sy
        lw_box = card_width
        lh_box = sh

        # Coordenadas absolutas (no desktop / tela do usuário)
        ax = lx + ox
        ay = ly + oy

        # Ponto central de clique
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
            "index": index,
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

    return cards


def annotate_segmented_lobby(
    lobby_image: np.ndarray,
    cards: list[dict[str, Any]],
    window_box: list[int] | None = None
) -> np.ndarray:
    """Desenha retângulos, mira e identificadores visuais na imagem para auditoria humana."""
    annotated = lobby_image.copy()

    # Se há caixa de janela destacada
    if window_box and len(window_box) == 4:
        wx, wy, ww, wh = window_box
        cv2.rectangle(annotated, (wx, wy), (wx + ww, wy + wh), (255, 200, 0), 2)
        cv2.putText(annotated, "JANELA LOBBY", (wx + 10, wy + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2, cv2.LINE_AA)

    for card in cards:
        lx, ly, lw, lh = card["local_box"]
        cx, cy = int(card["click_point_local"][0]), int(card["click_point_local"][1])
        is_complete = card["complete"]

        # Cor da borda: Verde para completo, Laranja/Vermelho para cortado
        border_color = (0, 220, 100) if is_complete else (0, 140, 255)
        thickness = 2

        # Borda externa do cartão
        cv2.rectangle(annotated, (lx, ly), (lx + lw, ly + lh), border_color, thickness)

        # Mira central no ponto de clique
        cross_size = 8
        cv2.drawMarker(annotated, (cx, cy), border_color, cv2.MARKER_CROSS, cross_size, 2)

        # Etiqueta de identificação
        status_label = f"#{card['index']} COMPLETO" if is_complete else f"#{card['index']} CORTADO ({card['clip_reason']})"
        cv2.putText(annotated, status_label, (lx + 8, ly + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, border_color, 2, cv2.LINE_AA)

        # Se o cartão for completo, desenha as sub-regiões internas em ciano suave
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

    # 1. Salva a imagem anotada com retângulos e miras
    annotated = annotate_segmented_lobby(lobby_image, cards)
    annotated_path = out / "annotated.png"
    cv2.imwrite(str(annotated_path), annotated)

    # 2. Salva o recorte de cada cartão encontrado
    saved_crops = []
    for card in cards:
        lx, ly, lw, lh = card["local_box"]
        crop = lobby_image[ly:ly + lh, lx:lx + lw]
        crop_name = f"card_{card['index']:02d}.png"
        crop_path = out / crop_name
        cv2.imwrite(str(crop_path), crop)
        saved_crops.append(crop_name)
        card["crop_file"] = crop_name

    # 3. Estatísticas resumidas
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

    segments_json_path = out / "segments.json"
    segments_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return report


def process_lobby_image(
    image_path: Path | str,
    output_dir: Path | str,
    origin: tuple[int, int] = (0, 0)
) -> dict[str, Any]:
    """Fluxo principal: lê imagem, segmenta cartões e grava artefatos."""
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Imagem do lobby não encontrada: {path}")

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"Não foi possível abrir o arquivo de imagem: {path}")

    # Localiza janela e segmenta
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
