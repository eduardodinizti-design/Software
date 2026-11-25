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


# Perfis de spread (do engine, = preflop_advisor._SPREADS): distribuição de stacks
# na mesa. ICM/PKO têm ranges POR spread; p/ infer_spread classificar é preciso >=5
# assentos com stack seguindo o perfil.
SPREADS = {'iguais': (25,) * 9,
           'curtos_fim': (35, 35, 30, 30, 25, 20, 15, 15, 20),
           'curtos_ini': (15, 15, 20, 20, 25, 30, 35, 35, 30)}


def _table(hero_pos, hero_stk, spread, bets_by_pos):
    """Mesa de 9 assentos: hero no bucket de teste, os outros seguindo o PERFIL do
    spread (escalado p/ a posição do hero bater hero_stk), p/ infer_spread acertar.
    Assentos keyados por POSIÇÃO (o hero por 'hero'). bets_by_pos: [(pos, bb), ...]."""
    prof = SPREADS.get(spread) or SPREADS['iguais']
    hidx = POS.index(hero_pos)
    scale = hero_stk / prof[hidx] if prof[hidx] else 1.0
    positions = {'hero': hero_pos}
    seats = {'hero': dict(stack_bb=hero_stk, occupied=True)}
    for i, pos in enumerate(POS):
        if pos == hero_pos:
            continue
        positions[pos] = pos
        seats[pos] = dict(stack_bb=round(prof[i] * scale, 1), occupied=True)
    bets = [dict(seat=('hero' if p == hero_pos else p), bet_bb=bb) for p, bb in bets_by_pos]
    return dict(positions=positions, seats=seats, bets=bets)


def st_first_in(hero_pos, hero_stk, spread='iguais'):
    return _table(hero_pos, hero_stk, spread, [])


def st_vs_open(hero_pos, opener_pos, hero_stk, spread='iguais'):
    return _table(hero_pos, hero_stk, spread, [(opener_pos, OPEN)])


def st_squeeze(hero_pos, opener_pos, caller_pos, hero_stk, spread='iguais'):
    return _table(hero_pos, hero_stk, spread, [(opener_pos, OPEN), (caller_pos, OPEN)])


def st_squeeze2(hero_pos, opener_pos, c1, c2, hero_stk, spread='iguais'):
    return _table(hero_pos, hero_stk, spread,
                  [(opener_pos, OPEN), (c1, OPEN), (c2, OPEN)])


def st_vs_3bet(hero_pos, tb_pos, hero_stk, spread='iguais'):
    t = _table(hero_pos, hero_stk, spread, [(hero_pos, OPEN), (tb_pos, TB)])
    t['pot'] = dict(pot_bb=OPEN + TB + 1.5)
    t['to_call'] = dict(to_call_bb=TB - OPEN)
    return t


def st_vs_limp(hero_stk, spread='iguais'):
    return _table('BB', hero_stk, spread, [('SB', 1.0)])


def _covered(adv, r, mode='chip_ev', stage='mid', bounty=None):
    """Uma situacao esta COBERTA se, para TODA a mesa, ha decisao EXECUTAVEL: ADVICE
    validado, OU OUT_OF_RANGE (fold), OU call_off_* (margem), OU piso fold/check
    nao-validado. So uma COMITADA (raise/call/all_in) nao-validada e buraco."""
    ok = True
    reasons = set()
    kw = dict(mode=mode, stage=stage)
    if bounty is not None:
        kw['bounty_bb'] = bounty
    for cards in (['Ad', 'Ac'], ['7c', '2d'], ['Kd', 'Qs'], ['9h', '8h']):
        res = adv.advise_from_reading(r, cards, **kw)
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
            # (o operador folda/checa).
            if res.get('recommended') in ('fold', 'check'):
                continue
            # HOMOLOGADO (Eduardo 20/11, Nash push/fold): uma COMITADA nao-validada COM NO
            # (node_id -> autoridade REFERENCE no contrato) e EXECUTAVEL. O operador NAO tem
            # trava val-based no caminho de raise/shove ("referencia manda") e o shove usa
            # _SHOVE_TARGET_MULT (nunca None) -> arma. Nash shadow (node_id setado) entra aqui.
            # So uma comitada SEM no (gap-aproximacao sem node_id -> raise sem sizing -> abstem)
            # continua sendo buraco real.
            if res.get('node_id'):
                continue
            ok = False; reasons.add('NAO_VALIDADO_COMMIT:%s' % res.get('recommended'))
    return ok, reasons


def hi(pos):
    return POS.index(pos)


def enumerate_situations(spread='iguais'):
    sits = []
    for stk in STACKS:
        # FIRST IN: hero abre de cada posicao (menos BB, que nao abre)
        for hp in POS:
            if hp == 'BB':
                continue
            sits.append(('first_in', hp, stk, st_first_in(hp, stk, spread)))
        # VS OPEN: opener antes do hero
        for hp in POS:
            for op in POS:
                if hi(op) < hi(hp) and op not in ('SB', 'BB'):
                    sits.append(('vs_open', '%s_vs_%s' % (hp, op), stk, st_vs_open(hp, op, stk, spread)))
        # SQUEEZE: opener + 1 caller antes do hero
        for hp in ('HJ', 'CO', 'BTN', 'SB', 'BB'):
            for op in POS:
                for cl in POS:
                    if hi(op) < hi(cl) < hi(hp) and op not in ('SB', 'BB') and cl not in ('SB', 'BB'):
                        sits.append(('squeeze', '%s_vs_%s+%s' % (hp, op, cl), stk,
                                     st_squeeze(hp, op, cl, stk, spread)))
                        break   # 1 exemplo de caller por (hp,op) basta p/ cobertura
                else:
                    continue
                break
        # SQUEEZE MULTIWAY (opener + 2 callers): só p/ posições tardias.
        for hp in ('BTN', 'SB', 'BB'):
            if hi('UTG') < hi('UTG+1') < hi('UTG+2') < hi(hp):
                sits.append(('squeeze_mw', '%s_vs_UTG+2c' % hp, stk,
                             st_squeeze2(hp, 'UTG', 'UTG+1', 'UTG+2', stk, spread)))
        # VS 3BET: hero abriu, vilao 3betou
        for hp in POS[:-2]:
            for tb in POS:
                if hi(tb) > hi(hp):
                    sits.append(('vs_3bet', '%s_3b_by_%s' % (hp, tb), stk, st_vs_3bet(hp, tb, stk, spread)))
                    break
        # VS LIMP: BB vs SB limp
        sits.append(('vs_limp', 'BB_vs_SB', stk, st_vs_limp(stk, spread)))
    return sits


# Todos os (modo, stage, bounty) que o cérebro serve. ICM/PKO usam stages; PKO tem bounty.
MODES = [('chip_ev', 'mid', None),
         ('icm', 'pre_itm', None), ('icm', 'bubble', None), ('icm', 'ft', None),
         ('pko', 'mid', 10.0),
         ('pko_icm', 'pre_itm', 10.0), ('pko_icm', 'bubble', 10.0), ('pko_icm', 'ft', 10.0)]
CATS = ('first_in', 'vs_open', 'squeeze', 'squeeze_mw', 'vs_3bet', 'vs_limp')


# Spreads a testar por modo: chip_ev/pko ignoram spread (iguais); ICM/PKO-ICM têm
# ranges POR spread -> testa os três.
def _spreads_for(mode):
    return ('iguais', 'curtos_ini', 'curtos_fim') if mode in ('icm', 'pko_icm') else ('iguais',)


def audit(adv, modes=MODES):
    """(covered, total, by_cat_cov, by_cat, gaps) sobre TODOS os modos E spreads."""
    covered = 0
    total = 0
    gaps = collections.defaultdict(list)
    by_cat = collections.Counter()
    by_cat_cov = collections.Counter()
    bymode = collections.Counter()
    bymode_cov = collections.Counter()
    for mode, stage, bounty in modes:
        for spread in _spreads_for(mode):
            for cat, label, stk, state in enumerate_situations(spread):
                total += 1
                by_cat[cat] += 1
                bymode[(mode, stage)] += 1
                ok, reasons = _covered(adv, state, mode=mode, stage=stage, bounty=bounty)
                if ok:
                    covered += 1; by_cat_cov[cat] += 1; bymode_cov[(mode, stage)] += 1
                else:
                    for rsn in reasons:
                        gaps[(cat, rsn)].append('%s/%s/%s %s@%dbb' % (mode, stage, spread, label, stk))
    audit.bymode = bymode
    audit.bymode_cov = bymode_cov
    return covered, total, by_cat_cov, by_cat, gaps


# ===========================================================================
# AUDITORIA DE DEFAULT PASSIVO vs LIMPERS (item #2, Eduardo 24/11).
# A audit() de COBERTURA acima trata um 'call'/'limp' VALIDADO como coberto — por
# isso era CEGA ao leak do Padrão de Jogo (mão iso-worthy LIMPANDO vs limper, o bug
# que derrubou o AQo ao vivo e que medimos em 358 casos). Esta auditoria é a lupa
# que faltava: enumera mãos ISO-WORTHY × posição (NÃO-BB) × stack × modo enfrentando
# limpers e FLAGA qualquer recomendação PASSIVA (limp/call/check). Exclui o BB
# (guerra de blinds = decisão da range vs_limp, autoridade — ver nvt-padrao-de-jogo).
PASSIVO = ('limp', 'call', 'check')
ISO_WORTHY_HANDS = {'AQo': ['Ad', 'Qc'], 'AJs': ['As', 'Js'], 'KQs': ['Ks', 'Qs'],
                    'AQs': ['As', 'Qs'], 'AKo': ['Ad', 'Kc'], 'TT': ['Td', 'Tc'],
                    '99': ['9d', '9c'], 'AJo': ['Ad', 'Jc'], 'KQo': ['Kd', 'Qc'],
                    'A5s': ['Ad', '5d'], '77': ['7d', '7c']}
# hero NÃO-BB isolando sobre limper(es) de posição anterior.
LIMPER_SCENARIOS = [
    ('SB_vs_CO', 'SB', ['CO']),
    ('SB_vs_LJ+CO', 'SB', ['LJ', 'CO']),
    ('CO_vs_LJ', 'CO', ['LJ']),
    ('BTN_vs_CO', 'BTN', ['CO']),
    ('HJ_vs_UTG', 'HJ', ['UTG']),
]


def _table_vs_limpers(hero_pos, hero_stk, limpers, spread='iguais'):
    """Mesa com o hero em `hero_pos` e limpers (bet 1.0) em `limpers`, blinds postados."""
    bets = [(p, 1.0) for p in limpers]
    if hero_pos != 'SB':
        bets.append(('SB', 0.5))
    if hero_pos != 'BB':
        bets.append(('BB', 1.0))
    return _table(hero_pos, hero_stk, spread, bets)


def audit_passive_leaks(adv, modes=MODES):
    """(leaks, total) — leaks = lista de str de cada mão iso-worthy que jogou PASSIVO
    vs limpers (viola o Padrão). total = situações checadas."""
    leaks = []
    total = 0
    for mode, stage, bounty in modes:
        for spread in _spreads_for(mode):
            for name, hpos, limpers in LIMPER_SCENARIOS:
                st = _table_vs_limpers(hpos, 0, limpers, spread)  # stk preenchido abaixo
                for stk in STACKS:
                    st = _table_vs_limpers(hpos, stk, limpers, spread)
                    for hlabel, cards in ISO_WORTHY_HANDS.items():
                        total += 1
                        kw = dict(mode=mode, stage=stage)
                        if bounty is not None:
                            kw['bounty_bb'] = bounty
                        r = adv.advise_from_reading(st, cards, **kw)
                        rec = r.get('recommended') if isinstance(r, dict) else None
                        if rec in PASSIVO:
                            leaks.append('%s/%s/%s %s %s@%dbb -> %s'
                                         % (mode, stage, spread, name, hlabel, stk, rec))
    return leaks, total


def main(argv=None):
    import os
    args = list(argv or sys.argv[1:])
    pack = args[0] if args else r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
    deep = args[1] if len(args) > 1 else r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
    # Audita o que o Henrique AO VIVO serve: operar_mesa usa from_files(validados, deep). Medir só
    # o pack validado SUB-REPORTA (ex.: refs de spread/nós que moram no deep) — foi o que fazia
    # os 63 'gaps' vs_3bet pko_icm/curtos_fim aparecerem sendo que o Henrique os cobre pelo deep.
    adv = (PreflopAdvisor.from_files(pack, deep) if os.path.exists(deep)
           else PreflopAdvisor.from_file(pack))
    covered, total, by_cat_cov, by_cat, gaps = audit(adv)
    print('=' * 72)
    print('COBERTURA PRE-FLOP AO VIVO (TODOS OS MODOS: chip_ev/icm/pko/pko_icm):')
    print('  %d/%d situacoes = %.1f%%' % (covered, total, 100.0 * covered / total))
    print('=' * 72)
    print('Por categoria (cobertas/total):')
    for cat in CATS:
        if by_cat[cat]:
            print('  %-11s %d/%d' % (cat, by_cat_cov[cat], by_cat[cat]))
    print()
    print('BURACOS por (categoria, motivo):')
    for (cat, rsn), labels in sorted(gaps.items(), key=lambda kv: -len(kv[1])):
        ex = ', '.join(sorted(set(labels))[:5])
        print('  [%-10s] %-30s x%-4d ex: %s' % (cat, rsn, len(labels), ex))
    # LUPA DO DEFAULT PASSIVO vs LIMPERS (item #2): o que a cobertura acima NÃO vê.
    leaks, ltot = audit_passive_leaks(adv)
    print()
    print('=' * 72)
    print('DEFAULT PASSIVO vs LIMPERS (iso-worthy NÃO-BB): %d/%d leaks' % (len(leaks), ltot))
    print('=' * 72)
    if leaks:
        print('  >>> %d VIOLAÇÕES do Padrão (iso-worthy limpou/completou vs limper):' % len(leaks))
        for x in leaks[:40]:
            print('    ', x)
    else:
        print('  >>> ZERO: nenhuma mão iso-worthy joga passivo vs limpers. <<<')
    return 0


if __name__ == '__main__':
    sys.exit(main())
