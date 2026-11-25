"""Promove nós HRC (estudo, validated=False) -> pack VALIDADO (validated=True),
seguindo a rotina do Eduardo (HRC solver = fonte de verdade; promover é o padrão).

Adiciona SÓ nós cuja CHAVE (_key_of: mode/format/stage/players/stack/spot/hero/vs/
spread) ainda NÃO existe no validado — NUNCA sobrescreve a verdade já validada
(b01/b02: validado sempre vence). Marca validated=True e rotula a proveniência.

Uso: python -I promover_ranges.py <validados.json> <estudo_hrc.json> <saida.json> [mode1,mode2]
Default modes: icm,pko_icm (os esparsos). Passivo: só lê/escreve JSON.
"""
import json
import sys


def _key(node):
    c = node.get('context') or {}
    return (c.get('mode'), c.get('format'), c.get('stage'), c.get('players'),
            c.get('stack'), node.get('spot'), node.get('hero'),
            tuple(node.get('vs') or ()), node.get('spread'))


def promote(validados, estudo, modes):
    existing = {_key(n) for n in validados.get('nodes', [])}
    added = []
    by_mode = {}
    for n in estudo.get('nodes', []):
        c = n.get('context') or {}
        if c.get('mode') not in modes:
            continue
        k = _key(n)
        if k in existing:
            continue                                   # validado já tem -> não mexe
        existing.add(k)
        nn = dict(n)
        nn['validated'] = True
        nn.setdefault('promotion', dict(from_shadow=True, source='hrc_study',
                                        policy='rotina_promocao_automatica'))
        added.append(nn)
        by_mode[c.get('mode')] = by_mode.get(c.get('mode'), 0) + 1
    out = dict(validados)
    out['nodes'] = list(validados.get('nodes', [])) + added
    return out, added, by_mode


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) < 3:
        print(__doc__); return 2
    modes = set((a[3].split(',') if len(a) > 3 else ['icm', 'pko_icm']))
    with open(a[0], encoding='utf-8') as fh:
        val = json.load(fh)
    with open(a[1], encoding='utf-8') as fh:
        est = json.load(fh)
    out, added, by_mode = promote(val, est, modes)
    with open(a[2], 'w', encoding='utf-8') as fh:
        json.dump(out, fh, ensure_ascii=False)
    print('PROMOVIDO -> %s' % a[2])
    print('  nós antes: %d | promovidos: %d | depois: %d'
          % (len(val.get('nodes', [])), len(added), len(out['nodes'])))
    print('  por modo:', by_mode)
    return 0


if __name__ == '__main__':
    sys.exit(main())
