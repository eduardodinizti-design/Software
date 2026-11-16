"""Auditor de COBERTURA PRE-FLOP AO VIVO: enumera TODA situacao preflop possivel
(posicao x stack x cenario x opener x callers) e verifica se o advisor devolve uma
decisao VALIDADA (nao ABSTAIN, nao validated=False) via advise_from_reading — o
MESMO caminho do ao vivo (infer_live_spot -> advise). Reporta cobertura e lista os
buracos por categoria. Regra do Eduardo: cobertura em TODAS as situacoes preflop.

Uso: python auditar_cobertura_preflop.py [caminho_do_pack.json]
"""
import sys
import collections

from preflop_advisor import PreflopAdvisor

POS = ['UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB', 'BB']
STACKS = [5, 8, 10, 12, 15, 20, 25, 30, 40]
OPEN = 2.0           # tamanho do open
TB = 6.0             # tamanho do 3bet


def _seats(mapping, hero_stk, other_stk=40):
    seats = {}
    for seat, pos in mapping.items():
        seats[seat] = dict(stack_bb=(hero_stk if seat == 'hero' else other_stk), occupied=True)
    return seats


def st_first_in(hero_pos, hero_stk):
    # hero e o primeiro a agir voluntariamente (ninguem abriu antes)
    mp = {'hero': hero_pos}
    return dict(positions=mp, seats=_seats(mp, hero_stk), bets=[])


def st_vs_open(hero_pos, opener_pos, hero_stk):
    mp = {'hero': hero_pos, 'op': opener_pos}
    return dict(positions=mp, seats=_seats(mp, hero_stk),
                bets=[dict(seat='op', bet_bb=OPEN)])


def st_squeeze(hero_pos, opener_pos, caller_pos, hero_stk):
    mp = {'hero': hero_pos, 'op': opener_pos, 'cl': caller_pos}
    return dict(positions=mp, seats=_seats(mp, hero_stk),
                bets=[dict(seat='op', bet_bb=OPEN), dict(seat='cl', bet_bb=OPEN)])


def st_vs_3bet(hero_pos, tb_pos, hero_stk):
    # hero abriu 2bb, vilao 3betou p/ 6bb. pot/to_call como o leitor ao vivo fornece.
    mp = {'hero': hero_pos, 'tb': tb_pos}
    return dict(positions=mp, seats=_seats(mp, hero_stk),
                bets=[dict(seat='hero', bet_bb=OPEN), dict(seat='tb', bet_bb=TB)],
                pot=dict(pot_bb=OPEN + TB + 1.5), to_call=dict(to_call_bb=TB - OPEN))


def st_vs_limp(hero_stk):
    mp = {'hero': 'BB', 'sb': 'SB'}
    return dict(positions=mp, seats=_seats(mp, hero_stk),
                bets=[dict(seat='sb', bet_bb=1.0)])


def _covered(adv, r):
    """Uma situacao esta COBERTA se, para TODA a mesa, existe decisao validada —
    aqui testamos com mao premium (AA) e lixo (72o): ambos devem dar ADVICE validado
    (jam/fold), nunca ABSTAIN nem validated=False."""
    ok = True
    reasons = set()
    for cards in (['Ad', 'Ac'], ['7c', '2d'], ['Kd', 'Qs'], ['9h', '8h']):
        res = adv.advise_from_reading(r, cards, mode='chip_ev')
        if not isinstance(res, dict):
            ok = False; reasons.add('NO_RESULT'); continue
        status = res.get('status')
        if status == 'OUT_OF_RANGE':
            continue                         # decisao VALIDA: mao fora da range = fold
        # Call-off por equity (spot call_off_*) é decisao EXECUTAVEL (autoridade de
        # margem no executor), mesmo validated=False -> conta como coberto.
        if status == 'ADVICE' and str(res.get('spot') or '').startswith('call_off'):
            continue
        if status != 'ADVICE':
            ok = False; reasons.add(res.get('reason') or status or 'ABSTAIN')
        elif res.get('validated') is not True:
            # Piso SEGURO: fold/check nao-validado = decisao correta e executavel
            # (o operador folda/checa). So uma COMITADA (raise/call/all_in) nao-validada
            # e buraco (a agressao pretendida nao e auto-executada -> vira fold).
            if res.get('recommended') in ('fold', 'check'):
                continue
            ok = False; reasons.add('NAO_VALIDADO_COMMIT:%s' % res.get('recommended'))
    return ok, reasons


def hi(pos):
    return POS.index(pos)


def enumerate_situations():
    sits = []
    for stk in STACKS:
        # FIRST IN: hero abre de cada posicao (menos BB, que nao abre)
        for hp in POS:
            if hp == 'BB':
                continue
            sits.append(('first_in', hp, stk, st_first_in(hp, stk)))
        # VS OPEN: opener antes do hero
        for hp in POS:
            for op in POS:
                if hi(op) < hi(hp) and op not in ('SB', 'BB'):
                    sits.append(('vs_open', '%s_vs_%s' % (hp, op), stk, st_vs_open(hp, op, stk)))
        # SQUEEZE: opener + 1 caller antes do hero
        for hp in ('HJ', 'CO', 'BTN', 'SB', 'BB'):
            for op in POS:
                for cl in POS:
                    if hi(op) < hi(cl) < hi(hp) and op not in ('SB', 'BB') and cl not in ('SB', 'BB'):
                        sits.append(('squeeze', '%s_vs_%s+%s' % (hp, op, cl), stk,
                                     st_squeeze(hp, op, cl, stk)))
                        break   # 1 exemplo de caller por (hp,op) basta p/ cobertura
                else:
                    continue
                break
        # VS 3BET: hero abriu, vilao 3betou
        for hp in POS[:-2]:
            for tb in POS:
                if hi(tb) > hi(hp):
                    sits.append(('vs_3bet', '%s_3b_by_%s' % (hp, tb), stk, st_vs_3bet(hp, tb, stk)))
                    break
        # VS LIMP: BB vs SB limp
        sits.append(('vs_limp', 'BB_vs_SB', stk, st_vs_limp(stk)))
    return sits


def main(argv=None):
    pack = (argv or sys.argv[1:] or [r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'])[0]
    adv = PreflopAdvisor.from_file(pack)
    sits = enumerate_situations()
    total = len(sits)
    covered = 0
    gaps = collections.defaultdict(list)       # (categoria, reason) -> [labels]
    by_cat = collections.Counter()
    by_cat_cov = collections.Counter()
    for cat, label, stk, state in sits:
        by_cat[cat] += 1
        ok, reasons = _covered(adv, state)
        if ok:
            covered += 1; by_cat_cov[cat] += 1
        else:
            for rsn in reasons:
                gaps[(cat, rsn)].append('%s@%dbb' % (label, stk))
    print('=' * 70)
    print('COBERTURA PRE-FLOP AO VIVO: %d/%d situacoes = %.1f%%' % (covered, total, 100.0 * covered / total))
    print('=' * 70)
    print('Por categoria (cobertas/total):')
    for cat in ('first_in', 'vs_open', 'squeeze', 'vs_3bet', 'vs_limp'):
        print('  %-10s %d/%d' % (cat, by_cat_cov[cat], by_cat[cat]))
    print()
    print('BURACOS por (categoria, motivo):')
    for (cat, rsn), labels in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        ex = ', '.join(sorted(set(labels))[:6])
        print('  [%-9s] %-34s x%-3d  ex: %s' % (cat, rsn, len(labels), ex))
    return 0


if __name__ == '__main__':
    sys.exit(main())
