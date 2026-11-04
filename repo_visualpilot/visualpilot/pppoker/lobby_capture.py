"""Phase 1, module 1: one native RGB screenshot, no OCR or desktop input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic
import uuid

import numpy as np
from PIL import Image

from .capture import ScreenCapture, enable_dpi_awareness
from .core import Region, require_rgb


def capture_lobby(output, *, region=None, monitor=None, capture_factory=ScreenCapture):
    """Save PNG plus coordinate metadata, without changing desktop state.

    region is an absolute physical-pixel Region. monitor is a one-based index
    from --list-monitors. The injected factory is only for laboratory testing.
    """
    if (region is None) == (monitor is None):
        raise ValueError('Escolha uma região ou um monitor inteiro.')
    if region is not None and not isinstance(region, Region):
        raise ValueError('Região inválida; use x, y, largura e altura em pixels físicos.')
    if monitor is not None and (type(monitor) is not int or monitor < 1):
        raise ValueError('O índice do monitor começa em 1.')
    output = Path(output)
    if output.exists():
        raise ValueError('A pasta de saída já existe. Escolha outra para preservar a captura anterior.')
    started = monotonic()
    with capture_factory() as capture:
        monitors = capture.monitors()
        if not monitors:
            raise ValueError('Nenhum monitor disponível.')
        if monitor is not None:
            if monitor > len(monitors):
                raise ValueError('Monitor inexistente. Execute --list-monitors novamente.')
            region = monitors[monitor-1]
        containing = [index+1 for index, bounds in enumerate(monitors) if bounds.contains(region)]
        if not containing:
            raise ValueError('A região deve ficar inteiramente dentro de um monitor; não pode atravessar a borda ou uma lacuna.')
        captured_at = datetime.now(timezone.utc).isoformat()
        rgb = capture.grab(region)
        require_rgb(rgb)
        if rgb.shape != (region.height, region.width, 3):
            raise ValueError('Dimensões da captura diferem da região solicitada; verifique escala/DPI.')
        if capture.monitors() != monitors:
            raise ValueError('A configuração dos monitores mudou durante a captura. Capture novamente.')
        source = getattr(capture, 'source', 'desktop_mss')
        # Do not depend on capture buffers after closing the context.
        rgb = np.ascontiguousarray(rgb).copy()
    capture_seconds = monotonic()-started
    uniform = bool(np.all(rgb == rgb[0, 0]))
    report = dict(module='phase1_module1', source=source, platform=sys.platform,
        captured_at_utc=captured_at, capture_seconds=round(capture_seconds, 6),
        region=region.to_dict(), monitors=[r.to_dict() for r in monitors],
        containing_monitors=containing, image_size=[region.width,region.height],
        coordinate_space='absolute_physical_desktop_pixels', pixel_format='RGB',
        resized=False, uniform_image=uniform, validation_state='awaiting_visual_check',
        note=('Imagem uniforme: confira se a tela está bloqueada, vazia ou se a região está correta.'
              if uniform else 'Abra o PNG e confira se a lista visível do lobby foi capturada sem cortes.'),
        image='lobby.png')
    output.mkdir(parents=True, exist_ok=False)
    with (output/'lobby.png').open('xb') as stream:
        Image.fromarray(rgb).save(stream, format='PNG')
    report['png_sha256'] = hashlib.sha256((output/'lobby.png').read_bytes()).hexdigest()
    with (output/'capture.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description='Módulo 1: salvar PNG do lobby sem cliques ou OCR.')
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--list-monitors', action='store_true', help='Listar origem e tamanho dos monitores.')
    choice.add_argument('--monitor', type=int, help='Capturar um monitor inteiro, índice a partir de 1.')
    choice.add_argument('--region', nargs=4, type=int, metavar=('X','Y','LARGURA','ALTURA'),
                        help='Retângulo absoluto em pixels físicos; X/Y podem ser negativos.')
    parser.add_argument('--output', type=Path, help='Pasta nova para PNG e JSON; padrão: capturas/data_id.')
    args = parser.parse_args(argv)
    try:
        enable_dpi_awareness()
        if args.list_monitors:
            with ScreenCapture() as capture:
                values = [dict(index=i+1, **region.to_dict()) for i, region in enumerate(capture.monitors())]
            print(json.dumps(values, ensure_ascii=False, indent=2))
            return 0
        output = args.output or Path('capturas')/(datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
        region = Region(*args.region) if args.region else None
        report = capture_lobby(output, region=region, monitor=args.monitor)
        print('PNG salvo em: '+str((output/'lobby.png').resolve()))
        print('Coordenadas e diagnóstico: '+str((output/'capture.json').resolve()))
        print(report['note'])
        return 0
    except Exception as exc:
        print(f'Captura não concluída: {type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
