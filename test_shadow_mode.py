"""Shadow Mode / Monitoring — classificação bot×GTO, saúde da sessão, parser."""
import os
import tempfile
import unittest

import shadow_mode as sm


class ClassifyTests(unittest.TestCase):
    def test_follows_gto(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=True, gto_recommended='raise', bot_action='raise', authority='VALIDATED')),
            'segue_gto')

    def test_raise_matches_all_in_family(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=True, gto_recommended='raise', bot_action='all_in', authority='VALIDATED')),
            'segue_gto')

    def test_validated_commit_against_gto_is_off_rails(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=True, gto_recommended='fold', bot_action='call', authority='VALIDATED')),
            'fora_dos_trilhos')

    def test_safe_noncommit_deviation(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=True, gto_recommended='raise', bot_action='fold', authority='SAFETY_NONCOMMIT')),
            'desvio_seguro')

    def test_premium_commit_without_node_is_off_rails(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=False, gto_recommended=None, bot_action='call', authority='SAFETY_PREMIUM')),
            'fora_dos_trilhos')

    def test_noncommit_without_node_is_safe(self):
        self.assertEqual(sm.classify_decision(dict(
            validated=False, gto_recommended=None, bot_action='fold', authority='SAFETY_NONCOMMIT')),
            'desvio_seguro')

    def test_no_action_is_sem_no(self):
        self.assertEqual(sm.classify_decision(dict(validated=True, gto_recommended='raise',
                                                   bot_action=None)), 'sem_no')


class MonitorTests(unittest.TestCase):
    def _path(self):
        return os.path.join(tempfile.mkdtemp(), 'sub', 'decisoes.jsonl')

    def test_observe_writes_and_reads_back(self):
        p = self._path()
        mon = sm.ShadowMonitor(p)
        mon.observe(hero_cards=['As', 'Ac'], position='BTN', validated=True,
                    gto_recommended='raise', bot_action='raise', authority='VALIDATED')
        rows = sm.load_recent(p, 10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['verdict'], 'segue_gto')

    def test_rotaciona_jsonl_ao_exceder_tamanho(self):
        # D16: o log não cresce sem limite — ao passar de max_bytes, rotaciona p/ .1
        p = self._path()
        mon = sm.ShadowMonitor(p, max_bytes=400, backups=2)
        for _ in range(60):
            mon.observe(hero_cards=['As', 'Ac'], position='BTN', validated=True,
                        gto_recommended='raise', bot_action='raise', authority='VALIDATED')
        self.assertTrue(os.path.exists(p + '.1'))          # houve rotação
        self.assertLess(os.path.getsize(p), 10_000)        # o ativo recomeçou pequeno
        # nunca acumula mais que os backups configurados
        self.assertFalse(os.path.exists(p + '.3'))

    def test_sem_max_bytes_nao_rotaciona(self):
        p = self._path()
        mon = sm.ShadowMonitor(p, max_bytes=0)
        for _ in range(5):
            mon.observe(validated=True, gto_recommended='fold', bot_action='fold', authority='SAFETY_NONCOMMIT')
        self.assertFalse(os.path.exists(p + '.1'))

    def test_health_escalates_on_off_rails(self):
        mon = sm.ShadowMonitor(path=None, warn=2, off=3)   # path None -> não grava
        health = None
        for _ in range(3):
            _, health = mon.observe(validated=True, gto_recommended='fold',
                                    bot_action='call', authority='VALIDATED')  # fora dos trilhos
        self.assertEqual(health['status'], 'off_rails')
        self.assertEqual(health['off_rails'], 3)

    def test_health_on_rails_when_following_gto(self):
        mon = sm.ShadowMonitor(path=None)
        _, health = mon.observe(validated=True, gto_recommended='raise',
                                bot_action='raise', authority='VALIDATED')
        self.assertEqual(health['status'], 'on_rails')


class ParseTests(unittest.TestCase):
    LOG = (
        "[033] CEREBRO m29x3 hero=['Jh', '6h'] pos=SB to_call=None bets=[('BTN', 4.0)] | "
        "spot=vs_open node=chip_ev|mid|40|vs_open|SB|BTN|- val=True eq=None req=None -> ADVICE call\n"
        "[033] >>> AGIU: CALL em (926, 1180) | autoridade=VALIDATED estado=DONE REAL\n"
        "[174] CEREBRO m29x3 hero=['Th', 'Ah'] pos=CO to_call=None bets=[('HJ', 1.0)] | "
        "spot=open_raise node=chip_ev|mid|40|open_raise|CO||- val=True eq=None req=None -> ADVICE raise\n"
        "[174] >>> RAISE sequencia: preset 3.0x confirmado=True\n"
        "[376] CEREBRO m29x3 hero=['3d', '4h'] pos=BB to_call=None bets=[('CO', 0.6)] | "
        "spot=None node=None val=None eq=None req=None -> ABSTAIN NO_VALIDATED_NODE_FOR_CONTEXT\n"
        "[376] >>> FALLBACK anti-freeze: FOLD | autoridade=SAFETY_NONCOMMIT\n")

    def test_parses_records_with_actions(self):
        recs = sm.parse_operator_log(self.LOG)
        self.assertEqual(len(recs), 3)
        self.assertEqual((recs[0]['bot_action'], recs[0]['verdict']), ('call', 'segue_gto'))
        self.assertEqual((recs[1]['bot_action'], recs[1]['verdict']), ('raise', 'segue_gto'))
        self.assertEqual((recs[2]['bot_action'], recs[2]['verdict']), ('fold', 'desvio_seguro'))
        self.assertEqual(recs[0]['stack_bb'], 40)

    def test_skips_cards_unknown(self):
        recs = sm.parse_operator_log(
            "[9] CEREBRO m1 hero=None pos=BB to_call=None bets=[] | spot=None node=None "
            "val=None eq=None req=None -> ABSTAIN HERO_CARDS_UNKNOWN\n")
        self.assertEqual(recs, [])


if __name__ == '__main__':
    unittest.main()
