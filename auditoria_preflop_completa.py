"""AUDITORIA COMPLETA do PRE-FLOP (Eduardo: 'nao aceito nenhum erro mais de range').
Varre TODAS as posicoes x TODOS os stacks, carregando os DOIS pacotes (validados+
deep, como o operador). Reporta: cobertura (decidiu vs abstem) e ERROS de sanidade
(premium que folda, lixo que abre de EP). Fonte da verdade = ranges do Eduardo."""
import os
import sys

from preflop_advisor import PreflopAdvisor

_VAL = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
_DEEP = r'C:\Meus Projetos\Aplicativos\nvt-ranges-deep.json'
try:
    from app_paths import find_data
    _VAL = find_data('nvt-ranges-validados.json')
    _DEEP = find_data('nvt-ranges-deep.json')
except Exception:
    pass

POS = ('UTG', 'UTG+1', 'UTG+2', 'LJ', 'HJ', 'CO', 'BTN', 'SB')
STACKS = (5, 8, 10, 12, 15, 20, 25, 30, 40, 100)
PREMIUM = ('AA', 'KK', 'QQ', 'AKs', 'AKo')          # tem que AGIR (raise/shove) sempre
TRASH_EP = ('72o', '82o', '32o', '92o', '42o')      # tem que FOLDAR de EP (UTG..LJ)


def cards(h):
    if len(h) == 2:
        return [h[0] + 'h', h[1] + 'd']
    return [h[0] + 'h', h[1] + ('h' if h[2] == 's' else 'd')]


def first_in(adv, hand, pos, stk):
    try:
        r = adv.advise_first_in(hero_cards=cards(hand), hero_position=pos, stack_bb=stk,
                                mode='chip_ev', stage='mid', players=9)
        return (r.get('status'), r.get('recommended'))
    except Exception as e:
        return ('ERR', str(e)[:30])


def main():
    if not (os.path.exists(_VAL) and os.path.exists(_DEEP)):
        print('[audit] pacotes nao encontrados:', _VAL, _DEEP); return
    adv = PreflopAdvisor.from_files(_VAL, _DEEP)
    print('AUDITORIA PRE-FLOP COMPLETA — first_in (open), chip_ev 9-max')
    print('pacotes: validados + deep |', len(POS), 'posicoes x', len(STACKS), 'stacks')
    print('=' * 70)
    buracos, erros_premium, erros_trash = [], [], []
    acoes = {'raise': 0, 'all_in': 0, 'fold': 0, 'limp': 0, 'check': 0, 'call': 0, 'other': 0, 'abstain': 0}
    total = 0
    for stk in STACKS:
        for pos in POS:
            # PREMIUM sempre age
            for h in PREMIUM:
                st, rec = first_in(adv, h, pos, stk)
                if rec not in ('raise', 'all_in', '3bet', 'bet'):
                    erros_premium.append(f'{h} {pos} {stk}bb -> {st}/{rec} (premium NAO agiu!)')
            # TRASH de EP sempre folda
            if pos in ('UTG', 'UTG+1', 'UTG+2', 'LJ'):
                for h in TRASH_EP:
                    st, rec = first_in(adv, h, pos, stk)
                    if rec not in ('fold', None):
                        erros_trash.append(f'{h} {pos} {stk}bb -> {rec} (lixo EP NAO foldou!)')
            # cobertura: um grid de maos representativas nao pode ABSTER
            for h in ('AJo', 'KQo', 'QJs', 'T9s', '55', 'A5s', 'K9s', '98s', 'A2o', 'J9o'):
                total += 1
                st, rec = first_in(adv, h, pos, stk)
                if st == 'ABSTAIN' or rec is None or st == 'ERR':
                    buracos.append(f'{h} {pos} {stk}bb -> {st}/{rec}')
                    acoes['abstain'] += 1
                else:
                    acoes[rec if rec in acoes else 'other'] += 1

    cob = 100.0 * (total - len(buracos)) / max(total, 1)
    print('COBERTURA first_in: %.1f%% (%d de %d spots decididos)' % (cob, total - len(buracos), total))
    print('acoes:', {k: v for k, v in acoes.items() if v})
    print('-' * 70)
    print('ERROS PREMIUM (premium que nao agiu):', len(erros_premium))
    for e in erros_premium[:20]:
        print('   X', e)
    print('ERROS LIXO-EP (lixo que abriu de EP):', len(erros_trash))
    for e in erros_trash[:20]:
        print('   X', e)
    print('BURACOS DE COBERTURA (abstencao no grid):', len(buracos))
    for b in buracos[:30]:
        print('   .', b)
    ok = not erros_premium and not erros_trash and not buracos
    print('=' * 70)
    print('RESULTADO:', 'VERDE — sem erro de range no grid auditado' if ok
          else 'ACHOU PROBLEMAS (ver acima)')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main() or 0)
