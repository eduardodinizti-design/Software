"""A native convergence label alone cannot substitute for actual consumer proof."""
import copy
import unittest

from tools.finalize_hu_campaign import checked_results
from strategy.state_contract import StrategyError


class CampaignDeliveryTests(unittest.TestCase):
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
