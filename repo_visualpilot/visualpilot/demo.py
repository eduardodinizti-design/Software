"""Gera somente imagens sintéticas para demonstrar o fluxo de coleta."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def generate(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    assets = root / 'assets'
    frames = root / 'frames'
    assets.mkdir()
    frames.mkdir()
    rng = np.random.default_rng(92)
    anchor = rng.integers(20, 230, (20, 40), dtype=np.uint8)
    cv2.imwrite(str(assets / 'anchor.png'), anchor)
    templates = {}
    images = {}
    for value in ('As', 'Kh', '2c', '3d', '4s', '5h', '6c'):
        image = np.full((40, 32), 245, dtype=np.uint8)
        cv2.rectangle(image, (0, 0), (31, 39), 45, 1)
        cv2.putText(image, value[0], (3, 19), cv2.FONT_HERSHEY_SIMPLEX, .55, 15, 2)
        cv2.putText(image, value[1], (10, 34), cv2.FONT_HERSHEY_SIMPLEX, .5, 60, 1)
        cv2.imwrite(str(assets / f'{value}.png'), image)
        templates[value] = f'assets/{value}.png'
        images[value] = image
    empty = np.full((40, 32), 70, dtype=np.uint8)
    cv2.rectangle(empty, (1, 1), (30, 38), 120, 2)
    cv2.imwrite(str(assets / 'empty.png'), empty)
    regions = {f'c{i}': [12 + i * 40, 60, 32, 40] for i in range(7)}
    profile = {'version': 1, 'table_size': [310, 140], 'anchor_image': 'assets/anchor.png',
               'anchor_offset': [10, 10], 'regions': regions,
               'hero_cards': ['c0', 'c1'], 'board_cards': [f'c{i}' for i in range(2, 7)],
               'card_templates': templates,
               'empty_slot_templates': {f'c{i}': 'assets/empty.png' for i in range(2, 7)}}
    (root / 'profile.json').write_text(json.dumps(profile, indent=2), encoding='utf-8')
    # 6 mesas, 4 etapas, 2 ciclos por etapa para confirmar estabilidade.
    for cycle in range(8):
        board_count = (0, 3, 4, 5)[cycle // 2]
        screen = np.zeros((450, 950, 3), dtype=np.uint8)
        for index in range(6):
            table = np.full((140, 310, 3), (35, 65, 30), dtype=np.uint8)
            table[10:30, 10:50] = cv2.cvtColor(anchor, cv2.COLOR_GRAY2BGR)
            cv2.putText(table, f'SYNTHETIC {index + 1}', (60, 24), cv2.FONT_HERSHEY_SIMPLEX, .4, (240, 240, 240), 1)
            cards = ['As', 'Kh'] + ['2c', '3d', '4s', '5h', '6c'][:board_count]
            for slot in range(7):
                x, y, w, h = regions[f'c{slot}']
                image = images[cards[slot]] if slot < len(cards) else empty
                table[y:y+h, x:x+w] = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            x, y = 5 + (index % 3) * 315, 5 + (index // 3) * 220
            screen[y:y+140, x:x+310] = table
        cv2.imwrite(str(frames / f'{cycle:03}.png'), screen)
    return root / 'profile.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='Nova pasta; não sobrescreve arquivos existentes')
    args = parser.parse_args()
    print(f'Perfil SINTÉTICO: {generate(args.output)}')


if __name__ == '__main__':
    main()
