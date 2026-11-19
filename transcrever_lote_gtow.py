"""Transcreve em LOTE o subconjunto GAP-FILLER (aprovado por Eduardo) dos charts GTOWizard
-> strategy_data/ranges_gtow/*.json, com summary p/ conferência. NÃO toca no cérebro ainda
(ingestão é passo seguinte, pelo gate). Flaga qualquer chart cuja detecção pareça falha."""
import json
import os
import sys

import transcrever_range_gtow as tg

REPO = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(REPO, '..', 'Ranges E TEORIAS'))
OUT = os.path.join(REPO, 'strategy_data', 'ranges_gtow')

# Subconjunto OURO (gap-fillers). RFIs redundantes (10/20/40/100) ficam de fora.
POSICOES = ['UTG', 'UTG1', 'LJ', 'HJ', 'CO', 'BTN', 'SB']


def _targets():
    t = []
    # BB defende vs SB SHOVE (mata SHOVE_ZONE / NO_SHOVE_RANGE) — só 10/12/15/20 têm Shove
    for bb in (10, 12, 15, 20):
        t.append(('%d BB' % bb, 'BB %d vs SB Shove.jpg' % bb, 'bb_vs_sb_shove', bb))
    # RFI de stacks OFF-BUCKET (12/15/30/50/70) — tapa os vãos entre nossas âncoras
    for bb in (12, 15, 30, 50, 70):
        for pos in POSICOES:
            t.append(('%d BB' % bb, '%s %d.jpg' % (pos, bb), 'rfi_%s' % pos.lower(), bb))
        t.append(('%d BB' % bb, 'BB %d vs SB RFI.jpg' % bb, 'bb_vs_sb_rfi', bb))
        t.append(('%d BB' % bb, 'BB %d vs SB Limp.jpg' % bb, 'bb_vs_sb_limp', bb))
    return t


def _degenerate(summary):
    """Detecção suspeita: uma única ação ~100% e nada mais, ou soma fora de ~100%."""
    tot = sum(v['pct'] for v in summary.values())
    return (not summary) or abs(tot - 100) > 4


def main(write=True):
    os.makedirs(OUT, exist_ok=True)
    ok, flag, miss = [], [], []
    for folder, fname, spot, bb in _targets():
        p = os.path.join(SRC, folder, fname)
        if not os.path.exists(p):
            miss.append('%s/%s' % (folder, fname)); continue
        try:
            res = tg.read_range(p)
            s = tg.summary(res['hands'])
        except Exception as e:                       # noqa: BLE001
            flag.append('%s/%s  ERRO: %s' % (folder, fname, e)); continue
        tag = 'FLAG' if _degenerate(s) else 'ok'
        line = '%-28s %-16s %s' % ('%s/%s' % (folder, fname), spot,
                                   '  '.join('%s=%.1f%%' % (a, v['pct']) for a, v in s.items()))
        (flag if tag == 'FLAG' else ok).append(line)
        if write and tag != 'FLAG':
            out = os.path.join(OUT, '%s_%dbb.json' % (spot, bb))
            json.dump({'source': '%s/%s' % (folder, fname), 'spot': spot, 'stack_bb': bb,
                       'tool': 'gtowizard_chipev', 'summary': s, 'hands': res['hands']},
                      open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('=== OK (%d) ===' % len(ok))
    for l in ok:
        print('  ' + l)
    if flag:
        print('\n=== FLAG / revisar (%d) ===' % len(flag))
        for l in flag:
            print('  ' + l)
    if miss:
        print('\n=== ausentes (%d) ===' % len(miss))
        for l in miss:
            print('  ' + l)
    print('\nJSONs em:', OUT if write else '(dry-run)')


if __name__ == '__main__':
    main(write='--dry' not in sys.argv)
