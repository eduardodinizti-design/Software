"""A native convergence label alone cannot substitute for actual consumer proof."""
import copy
import unittest

from tools.finalize_hu_campaign import checked_results,prior_pilot_statistics
from strategy.batch_archive import PILOT_TAG
from strategy.state_contract import StrategyError


class CampaignDeliveryTests(unittest.TestCase):
    def test_legacy_pilot_size_requires_the_exact_published_policy_hashes(self):
        pilot=dict(coverage={'public_nodes':345656},iterations=91,global_gap_bb=.046,
            file_sha256='a'*64,policy_sha256='b'*64)
        proof=dict(schema='software.hu-prior-pilot-size-proof.v1',source_release=PILOT_TAG,
            method='STAT_OF_RETAINED_FULL_PILOT_SQLITE_AFTER_MATCHING_ITS_PUBLISHED_SHA256',
            file_sha256=pilot['file_sha256'],policy_sha256=pilot['policy_sha256'],source_iterations=91,
            policy_file_bytes=2383261696)
        self.assertEqual(prior_pilot_statistics(pilot,proof)['policy_file_bytes'],2383261696)
        for field,value in (('file_sha256','c'*64),('policy_sha256','c'*64),('source_iterations',81),
                ('policy_file_bytes',0),('policy_file_bytes',True)):
            with self.subTest(field=field,value=value),self.assertRaises(StrategyError):
                prior_pilot_statistics(pilot,dict(proof,**{field:value}))
        self.assertNotIn('policy_file_bytes',pilot)

    def test_current_pilot_raw_size_is_preserved_without_requiring_legacy_proof(self):
        pilot=dict(coverage={'public_nodes':2},iterations=3,global_gap_bb=.04,policy_file_bytes=8192)
        self.assertEqual(prior_pilot_statistics(pilot,{}),pilot)

    def example(self,sb=False):
        case=dict(ordinal=1,board=['As','7d','2c'],policy_sha256='a'*64,file_sha256='b'*64,
            archive_sha256='c'*64,global_gap_bb=.04,
            independent_river=dict(runout=['Ts','2h'],joint_private_deals=100,nash_conv_bb=.02))
        settings=dict(ante_pot_bb=1.) if sb else {}
        row=dict(case,status='PASS',platform='Windows-laboratory',native_target_met=True,
            coverage=dict(structurally_complete=True),global_native_gap_bb=.04,
            pppoker_windows_validated=False,input_devices_used=False,
            all_json_responses_exactly_match_stored_policy=True,json_roundtrip_streets=['flop','turn','river'],
            source_lookup=dict(probes=dict(flop={},turn={},river={})),exact_suit_alias=dict(probes=dict(flop={},turn={},river={})),
            confirmed_hand=dict(status='PASS',policy_sha256='a'*64,event_counts=dict(action=6 if sb else 9,board=2),
                declared_hero_actions_by_street=[dict(street=s,action_id='bet:1') for s in ('FLOP','TURN','RIVER')],
                journal_chain_valid=True,complete_to_showdown=True,frequencies_and_sizes_exactly_match_stored_policy=True,
                hero_selected_actions_match_lab_actions=True,operational_profile_settings=settings))
        row['independent_river']=dict(case['independent_river'],exact_enumeration=True)
        catalog=dict(cases=[case],context=dict(positions=['SB' if sb else 'BTN','BB']),profile_settings=settings)
        return catalog,row

    def test_both_ip_and_oop_histories_are_verified_using_their_actual_action_counts(self):
        for sb in (False,True):
            catalog,row=self.example(sb);self.assertEqual(checked_results(catalog,[row]),[row])

    def test_final_report_rejects_no_history_even_with_converged_native_label(self):
        catalog,row=self.example();row.pop('confirmed_hand')
        with self.assertRaisesRegex(StrategyError,'HISTORY_INCOMPLETE'):checked_results(catalog,[row])

    def test_wrong_frequency_or_river_proof_cannot_be_called_pass(self):
        catalog,row=self.example();row['all_json_responses_exactly_match_stored_policy']=False
        with self.assertRaisesRegex(StrategyError,'PROOF_DIFFERS'):checked_results(catalog,[row])
        catalog,row=self.example();row['independent_river']['nash_conv_bb']+=.001
        with self.assertRaisesRegex(StrategyError,'RIVER_DIFFERS'):checked_results(catalog,[row])

    def test_small_blind_cannot_inherit_the_no_ante_profile(self):
        catalog,row=self.example(True);row['confirmed_hand']['operational_profile_settings']={}
        with self.assertRaisesRegex(StrategyError,'HISTORY_INCOMPLETE'):checked_results(catalog,[row])


if __name__=='__main__':unittest.main()
