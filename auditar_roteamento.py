"""AUDITOR DE ROTEAMENTO PRE-FLOP (matriz de reachability). Para cada (spot, bucket)
injeta um no-SONDA validado no contexto e, com o CENARIO ao vivo correto, verifica se
o roteador (advise_from_reading) de fato CHEGA na sonda. Diz, de forma limpa e
independente do dado existente, quais (spot,bucket) o bot REALMENTE usa — logo o que
vale a pena solvar (uma range que o roteador nunca pede seria desperdicio/range morta).

Cenarios por spot: first-in (open_*), vs-open-normal (vs_open), vs-open-ALL-IN
(vs_open_shove), vs-open shove-zone / squeeze (3bet_shove), vs-3bet (vs_3bet).

Uso: python auditar_roteamento.py [pack.json]
Read-only: a sonda e removida apos cada teste; o pack nao e alterado.
"""
import sys

import auditar_cobertura_preflop as aud
from preflop_advisor import PreflopAdvisor

LIVE = [5, 8, 10, 12, 15, 20, 25, 30, 40]
SPEC = [  # (spot, hero, vs, cenario_fn)
    ('open_raise', 'BTN', ()),
    ('open_shove', 'BTN', ()),
    ('vs_open', 'BB', ('BTN',)),
    ('vs_open_shove', 'BB', ('BTN',)),
    ('3bet_shove', 'SB', ('BTN',)),
    ('vs_3bet', 'CO', ('BTN',)),
]


def _probe(mode, fmt, stage, bucket, spot, hero, vs, spread, iaa):
    act = 'all_in' if 'shove' in spot else ('call' if spot in ('vs_open', 'vs_3bet') else 'raise')
    f1 = [1.0 if i == iaa else 0.0 for i in range(169)]
    f0 = [0.0 if i == iaa else 1.0 for i in range(169)]
    return dict(id='PROBE', context=dict(mode=mode, format=fmt, stage=stage, players=9, stack=bucket),
                spot=spot, hero=hero, vs=list(vs), spread=spread, validated=True, evUnit='bb',
                legalActions=[act, 'fold'], actions=[act, 'fold'],
                freq={act: f1, 'fold': f0}, ev={act: [1.0] * 169, 'fold': [0.0] * 169},
                outOfRange=[], source='PROBE')


def _state(spot, hero, vs, bucket, spread):
    opener = vs[0] if vs else 'BTN'
    if spot in ('open_raise', 'open_shove'):
        return aud.st_first_in(hero, bucket, spread or 'iguais')
    if spot == 'vs_3bet':
        tb = vs[0] if vs else 'BTN'                   # o 3bettor TEM que casar com o vs do no
        return aud.st_vs_3bet(hero, tb, bucket, spread or 'iguais')
    if spot == 'vs_open_shove':
        st = aud._table(hero, bucket, spread or 'iguais', [(opener, bucket)])
        st['seats'][opener]['stack_bb'] = 0.3        # abridor ALL-IN (stack atras ~0)
        return st
    if spot == '3bet_shove' and bucket > 15:
        # 20-25bb: 3bet-jam so aparece no SQUEEZE (com caller); monta opener+caller
        return aud.st_squeeze(hero, opener, 'CO', bucket, spread or 'iguais') if opener != 'CO' \
            else aud.st_squeeze(hero, opener, 'HJ', bucket, spread or 'iguais')
    return aud.st_vs_open(hero, opener, bucket, spread or 'iguais')


def reachable(adv, mode, fmt, stage, spread, spot, hero, vs, bucket, iaa):
    key = (mode, fmt, stage, 9, bucket, spot, hero, vs, spread)
    adv._index[key] = _probe(mode, fmt, stage, bucket, spot, hero, vs, spread, iaa)
    try:
        kw = dict(mode=mode, stage=stage)
        if mode in ('pko', 'pko_icm'):
            kw['bounty_bb'] = 10.0
        r = adv.advise_from_reading(_state(spot, hero, vs, bucket, spread), ['Ad', 'Ac'], **kw)
        return isinstance(r, dict) and r.get('node_id') == 'PROBE'
    finally:
        adv._index.pop(key, None)


def matrix(adv, mode='chip_ev', stage='mid', spread=None):
    iaa = adv.hands.index('AA')
    fmt = 'pko' if mode in ('pko', 'pko_icm') else 'regular'
    out = {}
    for spot, hero, vs in SPEC:
        buckets = [b for b in LIVE if (b <= 25 if 'shove' in spot else b >= 10)]
        out[spot] = [b for b in buckets
                     if reachable(adv, mode, fmt, stage, spread, spot, hero, vs, b, iaa)]
    return out


def main(argv=None):
    pack = (argv or sys.argv[1:] or [r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'])[0]
    adv = PreflopAdvisor.from_file(pack)
    print('=' * 70)
    print('MATRIZ DE REACHABILITY DO ROTEADOR (buckets que o bot REALMENTE usa)')
    print('=' * 70)
    for mode, stage, spread in [('chip_ev', 'mid', None), ('pko', 'mid', None),
                                ('icm', 'bubble', 'iguais'), ('pko_icm', 'bubble', 'iguais')]:
        print('\n%s / %s / %s:' % (mode, stage, spread))
        mx = matrix(adv, mode, stage, spread)
        for spot, _h, _v in SPEC:
            print('  %-14s usa buckets=%s' % (spot, mx[spot]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
