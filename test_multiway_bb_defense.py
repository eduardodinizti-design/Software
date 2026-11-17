"""Audits the user's fixed BB hypothesis; no frequencies are called solver output."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from strategy.multiway_bb_defense import (PRESET, apply_to_plan, build_defense,
    frequencies, hand_classes, validate_defense)
from strategy.multiway_study import make_plan, checkdown_equity
from strategy.range_catalog import ComboRange
from strategy.state_contract import StrategyError, digest
from tools.prepare_multiway_pilot import main as prepare

ROOT = Path(__file__).resolve().parent


class BBDefenseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.references = json.loads((ROOT/'docs/multiway-mp-btn-bb40-20261116/referencias-nvt.json').read_text(encoding='utf-8'))

    def plan(self):
        return make_plan(self.references['chip_ev'], self.references['pko'])

    def test_all_169_classes_form_one_physical_deck_partition(self):
        d = build_defense()
        self.assertEqual(len(hand_classes()), 169)
        self.assertEqual(sum(r['physical_combos'] for r in d['rows']), 1326)
        for r in d['rows']:
            self.assertAlmostEqual(sum(r['frequencies'].values()), 1.)
        self.assertAlmostEqual(sum(d['effective_combo_mass'].values()), 1326)

    def test_ten_fifty_are_whole_deck_not_fifty_percent_of_remaining(self):
        d = build_defense()
        self.assertEqual(d['effective_combo_mass']['squeeze'], 132.5)
        self.assertAlmostEqual(d['effective_combo_mass']['call'], 663.1)
        self.assertAlmostEqual(d['unblocked_percent']['call'], 50.00754147812972)
        self.assertAlmostEqual(d['unblocked_percent']['call']+d['unblocked_percent']['squeeze'], 60.)
        self.assertEqual(d['unblocked_percent']['fold'], 40.)
        self.assertGreater(d['effective_combo_mass']['call']/(1326-132.5), .55)

    def test_core_is_removed_from_call_without_double_count(self):
        d = build_defense()
        sq, call = frequencies(d, 'squeeze'), frequencies(d, 'call')
        for h in ('AA', 'KK', 'QQ', 'JJ', 'TT', 'AKs', 'AQs', 'AKo', 'KQs'):
            self.assertEqual((sq[h], call[h]), (1., 0.), h)

    def test_light_mix_has_explicit_residual_call_and_weak_offsuit_can_fold(self):
        d = build_defense()
        rows = {r['hand']:r['frequencies'] for r in d['rows']}
        self.assertEqual(rows['A5s'], dict(squeeze=.75, call=.25, fold=0.))
        self.assertEqual(rows['76s'], dict(squeeze=.5, call=.5, fold=0.))
        self.assertEqual(rows['K8s'], dict(squeeze=.25, call=.75, fold=0.))
        self.assertEqual(rows['99'], dict(squeeze=.5, call=.5, fold=0.))
        self.assertEqual(rows['32s']['call'], 1.)
        self.assertEqual(rows['72o']['fold'], 1.)
        self.assertAlmostEqual(rows['J7o']['call'], .8)

    def test_call_uses_only_its_branch_and_retains_all_suits(self):
        d = build_defense()
        r = ComboRange.from_classes(frequencies(d, 'call'), d['sha256'])
        self.assertAlmostEqual(r.mass, 663.1)
        self.assertAlmostEqual(dict(r.weights)['2c3c'], 1.)
        self.assertAlmostEqual(dict(r.weights)['2h3h'], 1.)
        self.assertNotIn('AcAd', dict(r.weights))
        self.assertLess(r.without(('As', '7d', '2c')).mass, r.mass)

    def test_counterfactual_preserves_baseline_and_both_mp_btn_vectors(self):
        old = self.plan()
        before = json.dumps(old, sort_keys=True)
        changed = apply_to_plan(old, build_defense())
        self.assertEqual(json.dumps(old, sort_keys=True), before)
        for name, ref in changed['candidate_references'].items():
            original = old['candidate_references'][name]
            self.assertEqual(ref['ranges'][:2], original['ranges'][:2])
            self.assertEqual(ref['original_nvt_parent']['sha256'], original['sha256'])
            self.assertNotEqual(ref['sha256'], original['sha256'])
            self.assertAlmostEqual(ref['ranges'][2]['combo_mass'], 663.1)
            self.assertEqual(ref['ranges'][2]['source_table']['potBb'], 6.5)
            self.assertFalse(ref['ranges'][2]['exact_hrc_parent_confirmed'])
        self.assertEqual(changed['root'], old['root'])
        self.assertEqual(changed['solved_flops'], 0)
        self.assertFalse(changed['solver']['executed'])
        self.assertIsNone(changed['pko_economy']['bounties'])

    def test_composite_fingerprint_covers_the_user_call_prior(self):
        changed = apply_to_plan(self.plan(), build_defense())
        for ref in changed['candidate_references'].values():
            self.assertEqual(ref['sha256'], digest({k:v for k, v in ref.items() if k != 'sha256'}))

    def test_corruption_cannot_be_relabelled_solved_or_hide_nonprobabilities(self):
        for mutation, reason in (
            (lambda d:d.update(solver_executed=True), 'UNSOLVED'),
            (lambda d:d['rows'][0]['frequencies'].update(call=.5), 'SUM_TO_ONE'),
            (lambda d:d['unblocked_percent'].update(call=45.), 'PERCENT_MISMATCH'),
        ):
            d = build_defense()
            mutation(d)
            d['sha256'] = digest({k:v for k, v in d.items() if k != 'sha256'})
            with self.assertRaisesRegex(StrategyError, reason):
                validate_defense(d)

    def test_stale_fingerprint_and_duplicate_class_are_rejected(self):
        d = build_defense()
        d['rows'][0]['hand'] = 'KK'
        with self.assertRaisesRegex(StrategyError, 'FINGERPRINT'):
            validate_defense(d)
        d['sha256'] = digest({k:v for k, v in d.items() if k != 'sha256'})
        with self.assertRaisesRegex(StrategyError, 'DISTINCT_CLASSES'):
            validate_defense(d)

    def test_different_arrival_geometry_is_not_silently_reused(self):
        plan = self.plan()
        plan['root_pot_bb'] = 9.
        with self.assertRaisesRegex(StrategyError, 'FIXED_MP_BTN_BB40'):
            apply_to_plan(plan, build_defense())

    def test_diagnostic_remains_chip_checkdown_not_pko_action_policy(self):
        plan = apply_to_plan(self.plan(), build_defense())
        result = checkdown_equity(plan['candidate_references']['pko'], plan['board'], 200, 13)
        self.assertAlmostEqual(sum(r['showdown_share'] for r in result['roles']), 1.)
        self.assertFalse(result['optimal_actions_calculated'])
        self.assertFalse(result['pkobounty_utility_calculated'])

    def test_preparer_exports_same_call_prior_csv_txt_and_hashed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'bb10c50'
            self.assertEqual(prepare(['--bb-preset', PRESET, '--output', str(out), '--samples', '100']), 0)
            d = json.loads((out/'bb-defesa-169.json').read_text(encoding='utf-8'))
            plan = json.loads((out/'plano.json').read_text(encoding='utf-8'))
            with (out/'bb-defesa-169.csv').open(encoding='utf-8', newline='') as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 169)
            call_mass = sum(int(r['physical_combos'])*float(r['call_frequency']) for r in rows)
            self.assertAlmostEqual(call_mass, 663.1)
            self.assertEqual(plan['bb_defense_assumption']['sha256'], d['sha256'])
            self.assertIn('1326', (out/'bb-defesa-169.txt').read_text(encoding='utf-8'))
            for record in json.loads((out/'inventario.json').read_text(encoding='utf-8'))['files']:
                self.assertEqual(hashlib.sha256((out/record['file']).read_bytes()).hexdigest(), record['sha256'])


if __name__ == '__main__':
    unittest.main()
