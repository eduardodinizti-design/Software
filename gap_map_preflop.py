"""GAP-MAP pré-flop: para CADA célula que o jogo ao vivo precisa (modo x stage x
spread x spot x bucket x par-de-posição), diz se há nó VALIDADO, e se NÃO, classifica
o buraco: BUCKET_MISMATCH (existe nó validado do MESMO contexto noutro bucket ->
fecha alinhando bucket), SPREAD_MISSING (existe noutro spread -> fecha c/ o spread),
ou SPARSE (não existe em lugar nenhum -> precisa ingerir/gerar range). Read-only.

Uso: python gap_map_preflop.py [pack.json]
"""
import collections
import sys

from preflop_advisor import PreflopAdvisor

LIVE_BUCKETS = [5, 8, 10, 12, 15, 20, 25, 30, 40]
ALIGN_TOL = PreflopAdvisor.ALIGN_TOL   # mesma tolerância de alinhamento do advisor
# chip_ev/pko usam spread=None; icm/pko_icm usam iguais/curtos_ini/curtos_fim.
_STG = ('iguais', 'curtos_ini', 'curtos_fim')
MODES = [('chip_ev', 'mid', (None,)),
         ('icm', 'pre_itm', _STG), ('icm', 'bubble', _STG), ('icm', 'ft', _STG),
         ('pko', 'mid', (None,)),
         ('pko_icm', 'pre_itm', _STG), ('pko_icm', 'bubble', _STG), ('pko_icm', 'ft', _STG)]
# spots executáveis (validar presença de nó): o resto (call-off/piso) é tratado à parte
EXEC_SPOTS = ('open_raise', 'open_shove', 'vs_open', 'vs_open_shove', '3bet_shove', 'vs_3bet')


def main(argv=None):
    pack = (argv or sys.argv[1:] or [r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'])[0]
    adv = PreflopAdvisor.from_file(pack)
    # índice de nós VALIDADOS: (mode,stage,spot,hero,vs,spread) -> set de buckets
    val = collections.defaultdict(set)
    allsp = collections.defaultdict(set)      # (mode,stage,spot,hero,vs) -> set de (spread)
    for key, node in adv._index.items():
        mode, fmt, stage, players, bucket, spot, hero, vs, spread = key
        if not node.get('validated'):
            continue
        val[(mode, stage, spot, hero, vs, spread)].add(bucket)
        allsp[(mode, stage, spot, hero, vs)].add(spread)

    cats = collections.Counter()
    detail = collections.defaultdict(lambda: collections.Counter())
    # varre as células que importam: por (mode,stage,spread) e os spots executáveis,
    # cada (hero,vs) presente em QUALQUER bucket, exigindo os LIVE_BUCKETS plausíveis.
    seen_pairs = collections.defaultdict(set)   # (mode,stage,spot,spread) -> {(hero,vs)}
    for (mode, stage, spot, hero, vs, spread), bks in val.items():
        seen_pairs[(mode, stage, spot, spread)].add((hero, vs))

    for mode, stage, spreads in MODES:
        for spot in EXEC_SPOTS:
            for spread in spreads:
                pairs = seen_pairs.get((mode, stage, spot, spread)) \
                    or {(h, v) for (m, s, sp, h, v) in allsp if (m, s, sp) == (mode, stage, spot)}
                for (hero, vs) in pairs:
                    have = val.get((mode, stage, spot, hero, vs, spread), set())
                    # buckets "necessários" = os LIVE que fazem sentido p/ o spot
                    need = [b for b in LIVE_BUCKETS
                            if (b <= 25 if 'shove' in spot else b >= 10)]
                    for b in need:
                        if b in have:
                            cats['COBERTO']; continue
                        # BUCKET_MISMATCH *honesto*: só conta como "é só alinhar bucket"
                        # se o nó do MESMO contexto está num bucket ADJACENTE na grade
                        # (<= ALIGN_TOL do bucket pedido). Ter um nó de 20/25bb NÃO cobre
                        # um cell de 10bb: range de jam de 20bb != 10bb. Fora da
                        # tolerância é NEEDS_RANGE (dado genuinamente faltando), não
                        # bucketing — o advisor alinha de fato só o que está <= ALIGN_TOL.
                        near = min(have, key=lambda s: abs(s - b)) if have else None
                        alignable = near is not None and abs(near - b) / b <= ALIGN_TOL
                        if alignable:                               # bucket adjacente -> alinha
                            cats['BUCKET_MISMATCH'] += 1
                            detail['BUCKET_MISMATCH'][(mode, spot)] += 1
                        elif have:                                  # só nó distante -> precisa range
                            cats['NEEDS_RANGE'] += 1
                            detail['NEEDS_RANGE'][(mode, spot)] += 1
                        elif spread is not None and any(
                                val.get((mode, stage, spot, hero, vs, s2))
                                for s2 in _STG if s2 != spread):
                            cats['SPREAD_MISSING'] += 1
                            detail['SPREAD_MISSING'][(mode, spot)] += 1
                        else:
                            cats['SPARSE'] += 1
                            detail['SPARSE'][(mode, spot)] += 1

    print('=' * 72)
    print('GAP-MAP PRE-FLOP — classificação dos buracos executáveis')
    print('=' * 72)
    tot = sum(v for k, v in cats.items() if k != 'COBERTO') or 1
    for k in ('BUCKET_MISMATCH', 'SPREAD_MISSING', 'NEEDS_RANGE', 'SPARSE'):
        print('  %-16s %5d células  (%.0f%% dos buracos)' % (k, cats[k], 100.0 * cats[k] / tot))
    print()
    print('COMO FECHA CADA UM:')
    print('  BUCKET_MISMATCH -> alinhar bucketing (nó ADJACENTE <=%.0f%%; JÁ feito no advisor)' % (ALIGN_TOL * 100))
    print('  SPREAD_MISSING  -> ingerir o spread faltante (nó existe noutro spread)')
    print('  NEEDS_RANGE     -> SOLVAR/INGERIR range nova: só há nó distante (ex.: jam 20-25bb')
    print('                     nao cobre 5-15bb; squeeze/PKO deep nao solvados) — NAO fabricar')
    print('  SPARSE          -> gerar/ingerir range nova (não existe em lugar nenhum)')
    print()
    for cat in ('BUCKET_MISMATCH', 'SPREAD_MISSING', 'NEEDS_RANGE', 'SPARSE'):
        print('--- %s por (modo, spot) [top] ---' % cat)
        for (mode, spot), n in detail[cat].most_common(12):
            print('    %-9s %-15s x%d' % (mode, spot, n))
        print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
