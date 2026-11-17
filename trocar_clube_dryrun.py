"""DRY-RUN da troca de clube — a corrente inteira SEM enviar input nenhum.

Captura a janela do PPPoker (ou lê um frame salvo com --image), e:
  1) localiza a GRADE DE CLUBES (find_grid_crop), lista os clubes visíveis e, se
     houver --target, PLANEJA a troca: mostra onde CLICARIA / se ROLARIA p/ procurar
     / se está AMBÍGUO — nada é clicado;
  2) se a tela estiver DENTRO de um clube, lê o clube ATUAL (read_current_club);
  3) roda o coordenador club_switcher.ensure_club(dry_run=True) p/ o plano de alto
     nível (NOOP / PLANO_TROCAR / CLUB_DESCONHECIDO).

É só diagnóstico de percepção+decisão. Os pontos saem em COORDENADA DO FRAME
capturado; o mapeamento final p/ a tela (e o clique de verdade) é o passo de ARME,
ainda a validar ao vivo. Uso:

  python trocar_clube_dryrun.py --hwnd 0xae0902 --target "AK Amakha Club"
  python trocar_clube_dryrun.py --image frame.png --target "Karekas Yellow"
"""
import argparse


def _ocr():
    from table_reading.ocr_runtime import image_to_string
    return lambda g: image_to_string(g, config='--psm 7')


def _read_frame(args):
    if args.image:
        import cv2
        im = cv2.imread(args.image)
        if im is None:
            raise SystemExit('Imagem não lida: %s' % args.image)
        return im, 'image:%s' % args.image
    from window_capture_engine import WindowCaptureEngine
    frame, meta = WindowCaptureEngine().capture_frame(hwnd=args.hwnd)
    if frame is None:
        raise SystemExit('Captura falhou: %s' % meta.get('status'))
    return frame, 'hwnd %#x (%s)' % (args.hwnd, meta.get('status'))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument('--hwnd', type=lambda s: int(s, 0), help='HWND da janela PPPoker')
    src.add_argument('--image', help='Frame/captura salvo (dry-run offline)')
    p.add_argument('--target', default=None, help='Clube-alvo p/ planejar a troca')
    args = p.parse_args(argv)

    from table_reading.pipeline import configure_ocr
    from club_grid import (find_grid_crop, list_visible_from_crop, match_club,
                           read_current_club)
    from lobby_runner import find_lobby_crop
    from club_switcher import ClubSwitcher, describe

    st = configure_ocr()
    frame, srcdesc = _read_frame(args)
    ocr = _ocr()

    print('=' * 70)
    print('TROCA DE CLUBE — DRY-RUN (o bot NÃO clica) | fonte:', srcdesc)
    print('OCR:', st.get('status'), st.get('version') or '', '| alvo:', repr(args.target))
    print('=' * 70)

    # 1) GRADE DE CLUBES visível? find_grid_crop só LOCALIZA a região; a grade é real
    # apenas se houver NOMES de clube legíveis (senão é outra tela com elementos verdes).
    g = find_grid_crop(frame)
    vis = list_visible_from_crop(g['crop'], ocr=ocr, origin=g['origin']) if g['ok'] else []
    named = [v for v in vis if v['name']]
    if named:
        print('GRADE encontrada em origin=%s — %d clube(s) legível(is) de %d tile(s):'
              % (g['origin'], len(named), len(vis)))
        for v in vis:
            print('   - %-22s clique=%s' % (repr(v['name'] or '(ilegível)'), v['click']))
        if args.target:
            m = match_club(args.target, [v['name'] for v in vis])
            if m['ambiguous']:
                print('\n>> ALVO %r: AMBÍGUO (%s) — NÃO clicaria; precisa nome exato/busca.'
                      % (args.target, m['reason']))
            elif m['index'] is not None:
                print('\n>> ALVO %r: CLICARIA em %s  [%s, DRY-RUN — nada enviado]'
                      % (args.target, vis[m['index']]['click'], m['reason']))
            else:
                print('\n>> ALVO %r: não visível nesta tela — ROLARIA p/ procurar [DRY-RUN].'
                      % args.target)
    else:
        why = g['reason'] if not g['ok'] else 'região sem nomes de clube legíveis'
        print('GRADE: não visível (%s). Abra a lista de clubes p/ planejar a troca.' % why)

    # 2) DENTRO de um clube? Só confiamos no "clube atual" quando há uma LISTA DE
    # TORNEIOS de verdade (vários badges de buy-in). Senão é a grade/outra tela e
    # "clube atual" não se aplica — evita ler lixo do cabeçalho e inventar estado.
    crop, _box, nb = find_lobby_crop(frame)
    inside = crop is not None and nb >= 3
    current = read_current_club(crop, ocr=ocr) if inside else None
    print('\nCLUBE ATUAL:', repr(current) if current
          else '(não estamos dentro de um clube nesta tela — badges=%d)' % (nb if crop is not None else 0))

    # 3) Plano de ALTO NÍVEL do coordenador (idempotência/verificação), se houver alvo.
    if args.target:
        sw = ClubSwitcher(read_current_club=lambda: current)   # do_switch=None -> só planeja
        r = sw.ensure_club(args.target, dry_run=True)
        print('COORDENADOR:', describe(r))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
