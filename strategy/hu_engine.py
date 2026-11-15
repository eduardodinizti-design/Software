"""Offline HU engine CLI: train, study boards, query and replay confirmed actions.

Run `python -m strategy.hu_engine --help`. No platform/input dependencies.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import time

from strategy.action_tree import Action, BetMenu
from strategy.board_features import compare_distributions
from strategy.ev_evaluator import CFRTrainer, attach_evaluation, evaluate_profile, exact_river_gap, exact_hu_gap
from strategy.line_policy import LinePolicy
from strategy.policy_store import CompiledPolicy, save_policy
from strategy.range_catalog import ComboRange, RangeCatalog
from strategy.state_contract import BettingState, DecisionState, GameContext, StrategyError
from strategy.strategy_decision import choose

DEVELOPMENT_FLOPS = ('As 7d 2c', 'Kd 8h 3c', 'Ah Kd 7c', 'Qs 8d 3c',
                     'Js Td 4c', '9s 8s 7d', '8c 6d 3s', '7s 7h 2d',
                     'Kc Kd 5s', 'Qs 7s 2s', 'Jd 9d 4c', '5c 4d 3s')
# Frozen before developing/tuning a response model. Not solver validation.
HOLDOUT_FLOPS = ('Ac 9h 4d', 'Kh Jh 6c', 'Td 8d 5s', '6h 6s 3c')


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(value, path):
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + '\n', encoding='utf-8')
    else:
        print(text)


def load_game(path):
    value = read_json(path)
    if value.get('schema') != 'software.hu-game.v1':
        raise StrategyError('UNKNOWN_GAME_SCHEMA')
    ranges = []
    for r in value['ranges']:
        ranges.append(ComboRange.from_classes(r['class_frequencies'], r['source_id'])
                      if 'class_frequencies' in r else ComboRange.from_dict(r))
    if len(ranges) != 2:
        raise StrategyError('TWO_RANGES_REQUIRED')
    return (GameContext(**value['context']), BettingState.from_dict(value['root']),
            tuple(ranges), BetMenu(**value.get('menu', {})))


def train(args):
    context, root, ranges, menu = load_game(args.game)
    start = time.perf_counter()
    trainer = CFRTrainer(context, root, ranges, menu, seed=args.seed, max_nodes=args.max_nodes)
    trainer.train(args.iterations)
    bundle = trainer.export()
    if args.evaluate:
        evaluation = evaluate_profile(root, ranges, menu, trainer.probabilities,
                                      samples=args.evaluate, seed=args.seed + 1000003,
                                      exact_river=len(root.board) == 5)
        attach_evaluation(bundle, evaluation)
        bundle['evaluation']['unseen_information_sets_using_uniform_offline_only'] = len(trainer.unseen_evaluation_infosets)
    if args.river_gap:
        gap = exact_river_gap(root, ranges, menu, trainer.probabilities)
        bundle['gap'] = gap
        bundle['quality']['global_gap_bb'] = gap['nash_conv_bb']
        bundle['quality']['gap_scope'] = gap['scope']
        bundle['quality']['converged'] = args.target_gap is not None and gap['nash_conv_bb'] <= args.target_gap
    root_rows = bundle['nodes'].get(root.key(), {}).get('combos', {})
    root_range = ranges[root.actor].without(root.board)
    bundle['quality']['root_combo_coverage'] = len(root_rows) / len(root_range.weights)
    bundle['quality']['root_weighted_coverage'] = sum(w for k, w in root_range.weights if k in root_rows) / root_range.mass
    bundle['quality']['root_min_visits'] = min((r['visits'] for r in root_rows.values()), default=0)
    bundle['quality']['training_seconds'] = time.perf_counter() - start
    save_policy(bundle, args.out)
    print(json.dumps(dict(policy=str(args.out), **bundle['quality']), sort_keys=True))
    return 0


def native_train(args):
    from strategy.texassolver_backend import solve
    context, root, ranges, menu = load_game(args.game)
    bundle = solve(args.binary, args.resources, args.job_dir, context, root, ranges, menu,
                   iterations=args.iterations, threads=args.threads, accuracy_pct=args.accuracy_pct,
                   dump_rounds=args.dump_rounds, timeout_seconds=args.timeout_seconds, memory_mb=args.memory_mb)
    if args.verify_river or args.verify_all_streets:
        policy = CompiledPolicy(bundle)
        evaluation = evaluate_profile(root, ranges, menu, policy.probabilities,
                                      exact_river=args.verify_river,
                                      exact_runouts=args.verify_all_streets,
                                      actions_fn=policy.actions, max_exact_deals=args.max_exact_deals)
        attach_evaluation(bundle, evaluation)
        bundle['quality']['action_ev_available'] = True
        gap = exact_hu_gap(root, ranges, menu, policy.probabilities, actions_fn=policy.actions,
                           max_exact_deals=args.max_exact_deals)
        native_gap = bundle['quality']['global_gap_bb']
        delta = None if native_gap is None else abs(gap['nash_conv_bb'] - native_gap)
        bundle['gap'] = gap
        bundle['gap']['difference_from_native_bb'] = delta
        br = bundle['quality'].get('native_last_best_response_centered_bb')
        br_delta = None if br is None else max(abs(a - b) for a, b in zip(br, gap['best_response_centered_bb']))
        bundle['gap']['max_per_player_br_difference_bb'] = br_delta
        verified = delta is not None and delta < 1e-3 and br_delta is not None and br_delta < 1e-3
        bundle['quality']['native_metric_independently_verified'] = verified
        bundle['quality']['solver_reported_target_met'] = bundle['quality']['converged']
        bundle['quality']['converged'] = verified and gap['nash_conv_bb'] <= 2 * root.pot_bb * args.accuracy_pct / 100
    save_policy(bundle, args.out)
    print(json.dumps(dict(policy=str(args.out), **bundle['quality']), sort_keys=True))
    return 0


def study(args):
    catalog = RangeCatalog.from_reference(args.reference)
    ranges = (catalog.get(args.hero_range), catalog.get(args.villain_range))
    flops = DEVELOPMENT_FLOPS + (HOLDOUT_FLOPS if args.holdout else ())
    results = []
    for i, flop in enumerate(flops):
        result = compare_distributions(ranges, flop.split(), samples=args.samples, seed=args.seed + i)
        result['partition'] = 'development' if i < len(DEVELOPMENT_FLOPS) else 'frozen_holdout'
        results.append(result)
        print(json.dumps(dict(board=flop, samples=args.samples, equity=result['equity_player0'],
                              partition=result['partition'])), flush=True)
    write_json(dict(scope='HU range/board diagnostics, no action EV or solved games',
                    hero_range=args.hero_range, villain_range=args.villain_range,
                    unique_flops=len(results), results=results), args.out)
    return 0


def query(args):
    policy = CompiledPolicy.load(args.policy)
    decision = DecisionState.from_dict(read_json(args.state))
    write_json(choose(policy, decision, selection_mode=args.selection_mode), args.out)
    return 0


def replay(args):
    policy = CompiledPolicy.load(args.policy)
    line = LinePolicy(policy)
    for event in read_json(args.events):
        if event['type'] == 'board':
            line.reveal(event['card'])
        elif event['type'] == 'action':
            line.observe(Action(event['kind'], event.get('additional_bb', 0)))
        else:
            raise StrategyError('UNKNOWN_REPLAY_EVENT')
    write_json(dict(state=line.state.to_dict(), trace=line.trace,
                    public_ranges=[r.to_dict() for r in line.ranges],
                    range_sha256=[r.fingerprint for r in line.ranges]), args.out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('train', help='Offline sampled CFR; exports coverage/gap, not a blanket GTO claim')
    p.add_argument('--game', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--iterations', type=int, default=10000)
    p.add_argument('--seed', type=int, default=20261115)
    p.add_argument('--max-nodes', type=int, default=100000)
    p.add_argument('--evaluate', type=int, default=0, help='Independent frozen-profile MC samples (river is exact)')
    p.add_argument('--river-gap', action='store_true')
    p.add_argument('--target-gap', type=float, default=None)
    p.set_defaults(run=train)
    p = subs.add_parser('native-train', help='Optional separately installed TexasSolver, full tree offline')
    p.add_argument('--game', required=True)
    p.add_argument('--binary', required=True)
    p.add_argument('--resources', required=True)
    p.add_argument('--job-dir', required=True, help='New directory; preserves previous runs')
    p.add_argument('--out', required=True)
    p.add_argument('--iterations', type=int, default=101)
    p.add_argument('--threads', type=int, default=2)
    p.add_argument('--accuracy-pct', type=float, default=.5, help='Native exploitability as percent of initial pot')
    p.add_argument('--dump-rounds', type=int, default=1)
    p.add_argument('--timeout-seconds', type=int, default=900)
    p.add_argument('--memory-mb', type=int, default=4096, help='Linux address-space limit; enforcement recorded')
    p.add_argument('--verify-river', action='store_true', help='Independent exact BR and EV on small river games')
    p.add_argument('--verify-all-streets', action='store_true', help='Exact small-game runouts/BR; requires full export')
    p.add_argument('--max-exact-deals', type=int, default=20000)
    p.set_defaults(run=native_train)
    p = subs.add_parser('study', help='12 development flops and optionally 4 frozen holdouts')
    p.add_argument('--reference', required=True)
    p.add_argument('--hero-range', default='BTN_open_25')
    p.add_argument('--villain-range', default='BB_call_vs_BTN_25')
    p.add_argument('--samples', type=int, default=20000)
    p.add_argument('--seed', type=int, default=20261115)
    p.add_argument('--holdout', action='store_true')
    p.add_argument('--out', required=True)
    p.set_defaults(run=study)
    p = subs.add_parser('query', help='Exact public-node and private-combo lookup')
    p.add_argument('--policy', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--selection-mode', choices=('policy_mix', 'exact_response'), default='policy_mix')
    p.add_argument('--out')
    p.set_defaults(run=query)
    p = subs.add_parser('replay', help='Confirmed actions -> two conditioned ranges, no clicks')
    p.add_argument('--policy', required=True)
    p.add_argument('--events', required=True)
    p.add_argument('--out')
    p.set_defaults(run=replay)
    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except (StrategyError, ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, 'HU_ENGINE_ERROR: ' + str(exc) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
