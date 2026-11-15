"""Optional offline TexasSolver console adapter; no copied solver implementation.

Tested source: bupticybee/TexasSolver 02c8021ee1307c18aa1e76b772c6ae1451601bc6
(AGPL-3.0). Exact suit weights disable isomorphism. Money is scaled explicitly;
the native tree's ACTUAL rounded sizes are imported and legally checked.
"""
from dataclasses import asdict
import hashlib
import json
import math
import re
from pathlib import Path
import subprocess
import time

from strategy.action_tree import Action, is_legal, apply_action
from strategy.policy_store import CompiledPolicy
from strategy.range_catalog import combo_key, joint_deals
from preflop_equity import hand_to_combos, parse_card
from strategy.state_contract import StrategyError, digest, reveal, validate_game

SOURCE_COMMIT = '02c8021ee1307c18aa1e76b772c6ae1451601bc6'


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def native_range(range_):
    # This native parser discards weights <=.005. A COMMON scale preserves every
    # relative weight without silently pruning rare combos. It accepts weights >1.
    factor = max(1.0, .01 / min(w for _, w in range_.weights))
    if not math.isfinite(factor) or max(w for _, w in range_.weights) * factor > 1e30:
        raise StrategyError('NATIVE_FLOAT32_CANNOT_PRESERVE_RANGE_DYNAMIC_RANGE')
    groups = {}
    for combo, w in range_.weights:
        a, b = combo[:2], combo[2:]
        if parse_card(a)[0] < parse_card(b)[0]:
            a, b = b, a
        label = a[0] + b[0] + ('' if a[0] == b[0] else 's' if a[1] == b[1] else 'o')
        groups.setdefault(label, []).append((combo, w))
    symmetric = True
    compressed = []
    for label, values in groups.items():
        expected = {combo_key('23456789TJQKA'[r - 2] + s for r, s in c) for c in hand_to_combos(label)}
        weight = values[0][1]
        if {c for c, _ in values} != expected or any(abs(w - weight) > weight * 1e-12 for _, w in values):
            symmetric = False
            break
        compressed.append((label, weight))
    values = sorted(compressed) if symmetric else range_.weights
    return ','.join(k + ':' + format(w * factor, '.12g') for k, w in values), factor, symmetric


def input_commands(context, root, ranges, menu, *, units_per_bb=1000, iterations=101,
                   threads=2, accuracy_pct=.5, dump_rounds=1, raise_fractions=(1.0,), native_raise_limit=None):
    validate_game(context, root)
    if (root.actor != root.oop or any(root.committed) or any(root.acted)
            or root.terminal or root.needs_cards):
        raise StrategyError('NATIVE_ROOT_REQUIRES_STREET_START_OOP_FIRST')
    if type(units_per_bb) is not int or units_per_bb <= 0:
        raise StrategyError('INVALID_NATIVE_MONEY_SCALE')
    if type(iterations) is not int or iterations < 11 or type(threads) is not int or threads < 1:
        raise StrategyError('INVALID_NATIVE_ITERATION_OR_THREAD_BUDGET')
    if not math.isfinite(accuracy_pct) or accuracy_pct <= 0 or dump_rounds not in (1, 2, 3):
        raise StrategyError('INVALID_NATIVE_ACCURACY_OR_EXPORT_DEPTH')
    # End at a reported checkpoint so the metric describes the exported strategy.
    iterations = math.ceil((iterations - 1) / 10) * 10 + 1
    ip, oop = 1 - root.oop, root.oop
    # Symmetry is checked on the full PRIOR, not on combos already removed by the board.
    ip_text, ip_scale, ip_symmetric = native_range(ranges[ip])
    oop_text, oop_scale, oop_symmetric = native_range(ranges[oop])
    isomorphic = ip_symmetric and oop_symmetric
    sizes = ','.join(format(f * 100, '.10g') for f in menu.fractions)
    if not raise_fractions or any(not math.isfinite(f) or f <= 0 for f in raise_fractions):
        raise StrategyError('INVALID_NATIVE_RAISE_MENU')
    raise_sizes = ','.join(format(f * 100, '.10g') for f in raise_fractions)
    commands = ['set_pot ' + format(root.pot_bb * units_per_bb, '.12g'),
                'set_effective_stack ' + format(min(root.stacks) * units_per_bb, '.12g'),
                'set_board ' + ','.join(root.board), 'set_range_ip ' + ip_text,
                'set_range_oop ' + oop_text]
    if native_raise_limit is not None:
        if type(native_raise_limit) is not int or native_raise_limit < 1:
            raise StrategyError('INVALID_NATIVE_RAISE_LIMIT')
        commands.append('set_raise_limit ' + str(native_raise_limit))
    for side in ('oop', 'ip'):
        for street in ('flop', 'turn', 'river'):
            commands.append('set_bet_sizes ' + side + ',' + street + ',bet,' + sizes)
            commands.append('set_bet_sizes ' + side + ',' + street + ',raise,' + raise_sizes)
            if side == 'oop':
                commands.append('set_bet_sizes ' + side + ',' + street + ',donk,' + sizes)
            if menu.include_all_in:
                commands.append('set_bet_sizes ' + side + ',' + street + ',allin')
    # A high threshold avoids the backend replacing ordinary sizes with jam early.
    commands += ['set_allin_threshold 1000000', 'build_tree',
                 'set_thread_num ' + str(threads), 'set_accuracy ' + str(accuracy_pct),
                 'set_max_iteration ' + str(iterations), 'set_print_interval 10',
                 'set_use_isomorphism ' + str(int(isomorphic)), 'start_solve', 'set_dump_rounds ' + str(dump_rounds),
                 'dump_result strategy.json']
    return '\n'.join(commands) + '\n', dict(units_per_bb=units_per_bb, iterations=iterations,
            threads=threads, target_exploitability_pct_pot=accuracy_pct, dump_rounds=dump_rounds,
            ip_range_common_scale=ip_scale, oop_range_common_scale=oop_scale,
            native_raise_limit=native_raise_limit if native_raise_limit is not None else 4,
            python_menu_raise_limit_not_used=native_raise_limit is None,
            root_effective_stack_bb=min(root.stacks), suit_isomorphism=isomorphic,
            suit_symmetry_verified_on_both_priors=True, raise_fractions=list(raise_fractions))


def native_action(text, state, scale):
    words = text.split()
    kind = words[0].lower()
    if kind in ('check', 'fold') and len(words) == 1:
        action = Action(kind)
    elif kind == 'call' and len(words) == 1:
        action = Action('call', state.call_cost_bb)
    elif kind in ('bet', 'raise') and len(words) == 2:
        amount = float(words[1]) / scale
        action = Action('all_in' if abs(amount - state.stacks[state.actor]) < 1e-7 else kind, amount)
    else:
        raise StrategyError('UNKNOWN_NATIVE_ACTION:' + text)
    if not is_legal(state, action):
        raise StrategyError('NATIVE_ACTION_ILLEGAL_IN_DECLARED_POKER_STATE:' + text)
    return action


def import_strategy(raw, context, root, ranges, menu, settings, provenance, metrics):
    nodes, pruned_zero_reach = {}, 0
    native_to_local = {0: 1 - root.oop, 1: root.oop}

    def possible(board):
        try:
            return next(joint_deals(ranges, board), None) is not None
        except StrategyError as exc:
            if str(exc) == 'EMPTY_RANGE':
                return False
            raise

    def visit(value, state):
        nonlocal pruned_zero_reach
        if not value or state.terminal:
            return
        if value.get('node_type') == 'chance_node':
            if not state.needs_cards:
                raise StrategyError('NATIVE_CHANCE_STATE_MISMATCH')
            for c, child in (value.get('dealcards') or {}).items():
                if c in state.board or not possible(state.board + (c,)):
                    pruned_zero_reach += 1
                    continue
                visit(child, reveal(state, c))
            return
        if value.get('node_type') != 'action_node' or state.needs_cards:
            raise StrategyError('NATIVE_NODE_TYPE_MISMATCH')
        if native_to_local[value['player']] != state.actor:
            raise StrategyError('NATIVE_ACTOR_ORDER_MISMATCH')
        labels = value['actions']
        actions = tuple(native_action(a, state, settings['units_per_bb']) for a in labels)
        if not menu.include_all_in and any(a.kind == 'all_in' for a in actions):
            raise StrategyError('NATIVE_AUTO_JAM_OUTSIDE_REQUESTED_MENU')
        if len({a.id for a in actions}) != len(actions):
            raise StrategyError('DUPLICATE_NATIVE_ACTION')
        block = value.get('strategy')
        if block:
            if block['actions'] != labels:
                raise StrategyError('NATIVE_STRATEGY_ACTION_ORDER_MISMATCH')
            rows = {}
            permitted = dict(ranges[state.actor].without(state.board).weights)
            for combo, probabilities in block['strategy'].items():
                combo = combo_key(combo)
                if combo in rows:
                    raise StrategyError('DUPLICATE_NATIVE_COMBO')
                if combo not in permitted:
                    raise StrategyError('NATIVE_EXPORTED_COMBO_COLLIDES_OR_IS_OUTSIDE_PRIOR')
                if (len(probabilities) != len(actions) or any(not math.isfinite(p) or p < 0 for p in probabilities)
                        or abs(sum(probabilities) - 1) > 2e-5):
                    raise StrategyError('INVALID_NATIVE_PROBABILITIES')
                total = sum(probabilities)
                rows[combo] = {'frequencies': {a.id: p / total for a, p in zip(actions, probabilities)},
                               'visits': None, 'action_ev_bb': None}
            if rows:
                nodes[state.key()] = dict(state=state.to_dict(), actions=[a.to_dict() for a in actions], combos=rows)
        children = value.get('childrens') or {}
        for text, action in zip(labels, actions):
            if text in children:
                visit(children[text], apply_action(state, action))

    visit(raw, root)
    last = metrics[-1] if metrics else None
    gap = None if last is None else 2 * root.pot_bb * last['exploitibility'] / 100
    quality = dict(method='texassolver_discounted_cfr', settings=settings, provenance=provenance,
                   public_nodes=len(nodes), zero_reach_chance_branches_omitted=pruned_zero_reach,
                   iterations=None if last is None else last['iteration'] + 1,
                   global_gap_bb=gap, gap_scope='native_full_tree_declared_menu_and_ranges',
                   converged=last is not None and last['exploitibility'] <= settings['target_exploitability_pct_pot'],
                   export_depth_in_streets=settings['dump_rounds'],
                   exported_depth_is_not_full_tree_coverage=settings['dump_rounds'] < 6 - len(root.board),
                   windows_validated=False, action_ev_available=False,
                   actual_sizes='native_rounding_to_one_unit_then_legality_checked',
                   native_metric_independently_verified=False)
    result = dict(schema='software.hu-policy.v1', context=asdict(context), root=root.to_dict(),
                  ranges=[r.to_dict() for r in ranges], menu=asdict(menu), quality=quality, nodes=nodes)
    CompiledPolicy(result)
    return result


def solve(binary, resources, job_dir, context, root, ranges, menu, *, timeout_seconds=900,
          memory_mb=4096, **kwargs):
    binary, resources = Path(binary).resolve(), Path(resources).resolve()
    job = Path(job_dir).resolve()
    if job.exists():
        raise StrategyError('NATIVE_JOB_DIR_MUST_BE_NEW_TO_PRESERVE_PREVIOUS_RUNS')
    build_manifest = binary.with_name(binary.name + '.manifest.json')
    build = json.loads(build_manifest.read_text()) if build_manifest.exists() else {}
    if build.get('supports_set_raise_limit') and build.get('binary_sha256') == file_hash(binary):
        kwargs['native_raise_limit'] = max(1, menu.max_raises)
    commands, settings = input_commands(context, root, ranges, menu, **kwargs)
    job.mkdir(parents=True)
    (job / 'input.txt').write_text(commands, encoding='utf-8')
    provenance = dict(repository='https://github.com/bupticybee/TexasSolver', tested_source_commit=SOURCE_COMMIT,
                      binary_sha256=file_hash(binary),
                      evaluator_dictionary_sha256=file_hash(resources / 'compairer/card5_dic_sorted.txt'),
                      command_sha256=hashlib.sha256(commands.encode()).hexdigest(),
                      license='AGPL-3.0; backend installed separately')
    provenance['binary_source_commit'] = None
    if build:
        if build.get('binary_sha256') == provenance['binary_sha256']:
            provenance['binary_source_commit'] = build.get('source_commit')
            provenance['build_source_patch'] = build.get('source_patch')
            provenance['generated_console_sha256'] = build.get('generated_console_sha256')
            provenance['hu_chance_denominator_cards'] = build.get('hu_chance_denominator_cards')
            provenance['generated_chance_sources_sha256'] = build.get('generated_chance_sources_sha256')
    if type(memory_mb) is not int or memory_mb <= 0 or timeout_seconds <= 0:
        raise StrategyError('INVALID_NATIVE_MEMORY_OR_TIME_BUDGET')
    settings['memory_budget_mb'] = memory_mb
    settings['memory_limit_enforced'] = False
    start = time.perf_counter()
    with (job / 'solver.log').open('w', encoding='utf-8') as log:
        try:
            process = subprocess.Popen([str(binary), '-i', str(job / 'input.txt'), '-r', str(resources)],
                                       cwd=job, stdout=log, stderr=subprocess.STDOUT)
            try:
                import resource
                if hasattr(resource, 'prlimit'):
                    resource.prlimit(process.pid, resource.RLIMIT_AS, (memory_mb * 1024**2,) * 2)
                    settings['memory_limit_enforced'] = True
            except ImportError:
                pass  # Windows: explicit metadata, never claim an enforced Linux limit.
            except OSError as exc:
                process.kill()
                process.wait()
                raise StrategyError('NATIVE_MEMORY_LIMIT_SETUP_FAILED') from exc
            result_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise StrategyError('NATIVE_SOLVE_TIMEOUT_NO_POLICY_PUBLISHED') from exc
    if result_code != 0 or not (job / 'strategy.json').exists():
        raise StrategyError('NATIVE_SOLVE_FAILED_SEE_JOB_LOG')
    with (job / 'strategy.json').open(encoding='utf-8') as f:
        raw = json.load(f)
    metrics_path = job / 'tmp_log.txt'
    metrics = [json.loads(line) for line in metrics_path.read_text().splitlines() if line.strip()] if metrics_path.exists() else []
    bundle = import_strategy(raw, context, root, ranges, menu, settings, provenance, metrics)
    printed = (job / 'solver.log').read_text(errors='replace')
    br = {}
    for player, value in re.findall(r'player ([01]) exploitability ([\-+0-9.eE]+)', printed):
        br[int(player)] = float(value) / settings['units_per_bb']
    if len(br) == 2:
        local = [None, None]
        local[1 - root.oop], local[root.oop] = br[0], br[1]
        bundle['quality']['native_last_best_response_centered_bb'] = local
    bundle['quality']['solve_seconds'] = time.perf_counter() - start
    bundle['quality']['raw_export_sha256'] = file_hash(job / 'strategy.json')
    (job / 'manifest.json').write_text(json.dumps(bundle['quality'], indent=2) + '\n', encoding='utf-8')
    return bundle
