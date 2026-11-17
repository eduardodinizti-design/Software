"""Prepare reference ranges, legal three-player replays and HRC instructions.

This command performs NO CFR solve, GUI interaction, or gameplay input.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from strategy.multiway_study import checkdown_equity, extract_candidates, make_plan, replay_cases
from strategy.multiway_bb_defense import PRESET, apply_to_plan, build_defense, report_text

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'docs/multiway-mp-btn-bb40-20261116/referencias-nvt.json'


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chip-ranges', type=Path)
    parser.add_argument('--pko-ranges', type=Path)
    parser.add_argument('--output', type=Path, required=True, help='Pasta NOVA; nunca sobrescreve um estudo')
    parser.add_argument('--samples', type=int, default=5000)
    parser.add_argument('--bb-preset', choices=('nvt-reference', PRESET), default='nvt-reference',
        help='Hipotese BB10 squeeze/50 call e opcional; nao sobrescreve a referencia NVT original')
    args = parser.parse_args(argv)
    if bool(args.chip_ranges) != bool(args.pko_ranges):
        parser.error('Informe os dois packs ou use as referencias extraidas inclusas')
    if args.samples < 2:
        parser.error('--samples deve ser >= 2')
    if args.output.exists():
        parser.error('A pasta de saida ja existe; use outra pasta para preservar o estudo anterior')
    if args.chip_ranges:
        refs = dict(chip_ev=extract_candidates(args.chip_ranges, 'chip_ev', 'mid'),
            pko=extract_candidates(args.pko_ranges, 'pko_icm', 'pre_itm'))
    else:
        refs = json.loads(REFERENCE.read_text(encoding='utf-8'))
    plan = make_plan(refs['chip_ev'], refs['pko'])
    defense = None
    if args.bb_preset == PRESET:
        defense = build_defense()
        plan = apply_to_plan(plan, defense)
        refs = plan['candidate_references']
    histories = replay_cases()
    diagnostics = {name: checkdown_equity(ref, plan['board'], args.samples)
                   for name, ref in refs.items()}
    args.output.mkdir(parents=True)
    write_json(args.output / 'plano.json', plan)
    write_json(args.output / 'referencias-nvt.json', refs)
    write_json(args.output / 'historicos-sinteticos.json', histories)
    write_json(args.output / 'equidade-checkdown.json', diagnostics)
    if defense is not None:
        write_json(args.output / 'bb-defesa-169.json', defense)
        (args.output / 'bb-defesa-169.txt').write_text(report_text(defense), encoding='utf-8')
        with (args.output / 'bb-defesa-169.csv').open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, lineterminator='\n')
            writer.writerow(['hand', 'physical_combos', 'squeeze_frequency', 'call_frequency', 'fold_frequency'])
            for row in defense['rows']:
                p = row['frequencies']
                writer.writerow([row['hand'], row['physical_combos'], p['squeeze'], p['call'], p['fold']])
    script = ROOT / 'hrc/MP_BTN_BB40_MENU.js'
    (args.output / script.name).write_bytes(script.read_bytes())
    files = [p for p in args.output.iterdir() if p.is_file()]
    write_json(args.output / 'inventario.json', dict(schema='software.multiway-preparation-files.v1',
        status='PREPARED_NOT_SOLVED_NOT_OPERATIONAL', solved_flops=0, executable_policies=0,
        files=[dict(file=p.name, bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest())
               for p in sorted(files)]))
    print(json.dumps(dict(status=plan['status'], output=str(args.output),
        bb_preset=args.bb_preset,
        synthetic_histories=len(histories), samples_per_reference=args.samples,
        solved_flops=0, executable_policies=0,
        next=('Ver GUIA_BB10C50_20261117.txt; ainda requer HRC Pro e economia PKO' if defense
            else 'Configurar e executar o piloto no HRC Pro Windows; ver GUIA_MULTIWAY_MP_BTN_BB40_20261116.txt')),
        ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
