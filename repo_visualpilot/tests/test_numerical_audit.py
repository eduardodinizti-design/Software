import unittest
from visualpilot.lab.numerical_audit import audit_numerical_case


class NumericalAuditTests(unittest.TestCase):
    def test_agreeing_searches_can_all_be_wrong(self):
        ref=dict(status='experimental',exact_under_model=True,comparisons={'check':2.,'bet:1':1.})
        runs=[dict(status='experimental',chosen='bet:1') for _ in range(3)]
        result=audit_numerical_case(ref,runs)
        self.assertTrue(result['seed_stable']);self.assertFalse(result['numerically_accepted'])
        self.assertEqual(result['worst_regret'],1.)
        self.assertFalse(result['strategically_validated'])

    def test_different_actions_can_be_numerically_equivalent(self):
        ref=dict(status='experimental',exact_under_model=True,comparisons={'check':2.,'bet:1':1.99})
        runs=[dict(status='experimental',chosen=a) for a in ('check','bet:1','check')]
        result=audit_numerical_case(ref,runs)
        self.assertFalse(result['seed_stable']);self.assertTrue(result['numerically_accepted'])

    def test_missing_reference_or_budget_never_passes(self):
        self.assertFalse(audit_numerical_case({},[])['numerically_accepted'])
        ref=dict(status='experimental',exact_under_model=True,comparisons={'check':2.})
        self.assertFalse(audit_numerical_case(ref,[{'status':'pending'}])['numerically_accepted'])
        with self.assertRaises(ValueError):audit_numerical_case(ref,[],float('nan'))
