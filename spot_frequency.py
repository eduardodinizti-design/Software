"""CRUZAMENTO frequência × cobertura de solves (prioriza o trabalho de solver).

Para cada decisão PÓS-FLOP do herói nas HHs, classifica o SPOT por:
  pot (SRP / 3bet / multiway) × (HU/MW) × faixa de stack × rua
conta a frequência, e marca se JÁ TEMOS solve pra aquele tipo (cobertura atual do projeto).
Saída: ranking dos spots mais frequentes que NÃO temos solvados -> o que solvar a seguir.

Cobertura atual (pós-flop shadow do projeto, honesta): SRP heads-up, FLOP, ~20-45bb
(BTN vs BB 25bb, As7d2c, SB vs BB 40bb). Todo o resto (multiway, 3bet pots, turn/river,
outros stacks) está DESCOBERTO.
"""
from __future__ import annotations
from collections import Counter

from hand_history import parse_hand_histories


def stack_bucket(bb):
    if bb is None:
        return '?'
    if bb < 15:
        return '<15bb'
    if bb < 25:
        return '15-25bb'
    if bb < 40:
        return '25-40bb'
    if bb < 60:
        return '40-60bb'
    return '60bb+'


def pot_class(pot_type):
    if pot_type == 'multiway':
        return 'multiway'
    if pot_type == 'three_bet':
        return '3bet'
    return 'SRP'


def is_covered(pc, hu, bucket, street):
    """Temos solve shadow só p/ SRP heads-up, FLOP, ~20-45bb."""
    return (pc == 'SRP' and hu and street == 'FLOP'
            and bucket in ('15-25bb', '25-40bb', '40-60bb'))


def spot_key(d):
    pc = pot_class(d.get('pot_type'))
    hu = d.get('opponents', 0) == 1
    bucket = stack_bucket(d.get('hero_stack_bb'))
    street = d.get('street')
    return (pc, 'HU' if hu else 'MW', bucket, street)


def build_counts(raw_text, counter=None):
    counter = counter if counter is not None else Counter()
    for h in parse_hand_histories(raw_text):
        if not getattr(h, 'has_postflop', False):
            continue
        for d in h.hero_decisions:
            counter[spot_key(d)] += 1
    return counter


def report(counter, top=30):
    total = sum(counter.values()) or 1
    rows = counter.most_common()
    covered = sum(c for k, c in rows if is_covered(k[0], k[1] == 'HU', k[2], k[3]))
    out = [f"decisões pós-flop: {total}  |  cobertas por solve: {covered} ({100*covered/total:.0f}%)  "
           f"|  DESCOBERTAS: {total-covered} ({100*(total-covered)/total:.0f}%)",
           '',
           f"{'SPOT (pot/HU-MW/stack/rua)':<38}{'FREQ':>8}{'%':>6}  COBERTURA",
           '-' * 70]
    for k, c in rows[:top]:
        pc, hm, bucket, street = k
        cov = 'coberto' if is_covered(pc, hm == 'HU', bucket, street) else 'FALTA'
        label = f"{pc}/{hm}/{bucket}/{street}"
        out.append(f"{label:<38}{c:>8}{100*c/total:>5.0f}%  {cov}")
    # ranking do que FALTA (prioridade de solve)
    faltam = [(k, c) for k, c in rows if not is_covered(k[0], k[1] == 'HU', k[2], k[3])]
    out += ['', '=== PRIORIDADE DE SOLVE (spots mais frequentes SEM cobertura) ===']
    for k, c in faltam[:15]:
        out.append(f"  {k[0]}/{k[1]}/{k[2]}/{k[3]}: {c} ({100*c/total:.0f}%)")
    return '\n'.join(out)


def _main():
    import argparse, glob, os, sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='.txt ou pasta(s)')
    ap.add_argument('--top', type=int, default=30)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    files = []
    for p in a.paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, '**', '*.txt'), recursive=True)
        else:
            files += glob.glob(p)
    counter = Counter()
    for fp in files:
        try:
            build_counts(open(fp, encoding='utf-8', errors='replace').read(), counter)
        except OSError:
            pass
    rep = report(counter, top=a.top)
    print(rep)
    if a.out:
        open(a.out, 'w', encoding='utf-8').write(rep + '\n')
        print('\nsalvo em', a.out)


if __name__ == '__main__':
    _main()
