"""B03 — consulta pré-flop EXPLICÁVEL (diagnóstico offline). Nunca captura/clica.

Mostra, para um contexto + mão, o nó de FONTE usado, o hash do(s) pack(s), o
contexto do nó, as DIFERENÇAS exatas (bucket de stack, stack emprestado, mesa
9-max de referência, profundidade acima do solve), o mix/EV e o motivo da
resposta. Liga toda recomendação à sua fonte.

Exemplos:
  python explicar_preflop.py --ranges nvt-ranges-validados.json \
      --cartas Ah Kd --pos BTN --stack 25
  python explicar_preflop.py --ranges nvt-ranges-validados.json --deep nvt-ranges-deep.json \
      --cartas 7h 2d --pos BB --stack 30 --spot vs_open --vs BTN
"""
import argparse
import json

from preflop_advisor import PreflopAdvisor


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--ranges', required=True)
    p.add_argument('--deep', default=None, help='Pack de referência deep (merge auditado)')
    p.add_argument('--cartas', nargs=2, required=True, metavar=('C1', 'C2'),
                   help='Cartas do hero, ex.: Ah Kd')
    p.add_argument('--pos', required=True, help='Posição do hero (UTG, CO, BTN, SB, BB, ...)')
    p.add_argument('--stack', type=float, required=True, help='Stack efetivo em BB')
    p.add_argument('--spot', default='open_raise',
                   help='open_raise | vs_open | vs_3bet | 3bet_shove | vs_open_shove | open_shove ...')
    p.add_argument('--vs', nargs='*', default=[], help='Posição(ões) do(s) vilão(ões), ex.: BTN')
    p.add_argument('--players', type=int, default=9)
    p.add_argument('--mode', default='chip_ev', choices=('chip_ev', 'icm', 'pko', 'pko_icm'))
    p.add_argument('--stage', default='mid')
    p.add_argument('--manifest', action='store_true', help='Imprime também o manifesto de fontes (B01)')
    args = p.parse_args(argv)

    advisor = (PreflopAdvisor.from_files(args.ranges, args.deep) if args.deep
               else PreflopAdvisor.from_file(args.ranges))
    out = advisor.explain(hero_cards=list(args.cartas), hero_position=args.pos,
                          stack_bb=args.stack, mode=args.mode, stage=args.stage,
                          players=args.players, spot=args.spot, vs=tuple(args.vs))
    if args.manifest:
        out = dict(out, manifest=advisor.manifest())
    print(json.dumps(dict(scope='OFFLINE_EXPLAIN', **out), ensure_ascii=False, indent=2))
    return 0 if out['answer'].get('status') == 'ADVICE' else 2


if __name__ == '__main__':
    raise SystemExit(main())
