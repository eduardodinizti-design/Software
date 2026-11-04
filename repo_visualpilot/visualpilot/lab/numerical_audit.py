"""Separate agreement between searches from accuracy against a model reference."""
import math


def audit_numerical_case(reference,runs,tolerance=.03):
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance<0:
        raise ValueError('Tolerância inválida.')
    if not reference.get('exact_under_model') or reference.get('status')!='experimental':
        return dict(status='pending',reason='no_exact_reference',numerically_accepted=False)
    values=reference.get('comparisons',{})
    if not values or any(type(v) not in (int,float) or not math.isfinite(v) for v in values.values()):
        raise ValueError('Referência inválida.')
    if not runs or any(r.get('status')!='experimental' or r.get('chosen') not in values for r in runs):
        return dict(status='pending',reason='incomplete_search',numerically_accepted=False)
    best=max(values.values());regrets=[best-values[r['chosen']] for r in runs]
    stable=len({r['chosen'] for r in runs})==1
    accepted=max(regrets)<=tolerance
    return dict(status='accepted_under_model' if accepted else 'needs_refinement',
        numerically_accepted=accepted,seed_stable=stable,regrets=regrets,worst_regret=max(regrets),
        tolerance=tolerance,strategically_validated=False,
        reason='within_reference_tolerance' if accepted else 'reference_disagreement')
