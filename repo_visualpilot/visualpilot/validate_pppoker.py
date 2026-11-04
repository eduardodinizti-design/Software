"""Reavalia recortes reais rotulados; não mede captura ou seis mesas no Windows."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from .pppoker.observer.perception import CachedReader, read_table
from .pppoker.replay.reader import ReplayReader


def validate(folder):
    folder = Path(folder)
    labels = json.loads((folder / 'labels.json').read_text(encoding='utf-8'))
    reader = CachedReader(ReplayReader())
    results, missing = [], []
    for name, expected in labels['cases'].items():
        path = folder / (name + '.png')
        if not path.is_file():
            missing.append(path.name)
            continue
        image = np.array(Image.open(path).convert('RGB'))
        began = perf_counter()
        reading = read_table(reader, image)
        results.append({'sample': name, 'expected': expected, 'reading': reading,
                        'reader_seconds': round(perf_counter() - began, 4)})
    summary = {'executed': len(results), 'missing': missing,
               'hero_correct': sum(r['reading'].get('hero', []) == r['expected']['hero'] for r in results),
               'hero_pending': sum(not r['reading'].get('hero') for r in results),
               'hero_incorrect': sum(bool(r['reading'].get('hero')) and r['reading']['hero'] != r['expected']['hero'] for r in results),
               'visible_boards': sum(bool(r['expected']['board']) for r in results),
               'board_correct': sum(bool(r['expected']['board']) and r['reading'].get('board') == r['expected']['board'] for r in results),
               'board_incorrect': sum(bool(r['reading'].get('board')) and r['reading']['board'] != r['expected']['board'] for r in results),
               'false_preflop': sum(not r['expected']['board'] and r['reading'].get('street') == 'preflop' for r in results),
               'windows_verified': False, 'six_table_throughput_verified': False}
    return {'scope': 'Recortes existentes no arquivo recebido, do mesmo vídeo; rótulos herdados e pixels revisáveis. Não é validação independente no Windows.',
            'summary': summary, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', default='tests/fixtures/heldout_cards')
    parser.add_argument('--output', default='sessions/validation/pppoker-images.json')
    args = parser.parse_args()
    result = validate(args.fixtures)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['summary'], ensure_ascii=False, indent=2))
    if not result['summary']['executed'] or any(result['summary'][k] for k in ('hero_incorrect', 'board_incorrect', 'false_preflop')):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
