"""SYNTHETIC passive lookup probe; no production range claim and no system input.

Run from VisualPilot repository root with PYTHONPATH=.
The two fabricated same-context nodes intentionally disagree about AA to expose
index collision behavior, not to recommend either poker action.
"""
from copy import deepcopy
import json

from preflop_advisor import PreflopAdvisor
from test_preflop_advisor import pack_with_node

pack = pack_with_node()
old = deepcopy(pack['nodes'][0])
old.update(id='SYNTHETIC_OLD', source='SYNTHETIC_TEST_ONLY_OLD')
new = deepcopy(old)
new.update(id='SYNTHETIC_NEW', source='SYNTHETIC_TEST_ONLY_NEW')
new['freq']['raise'] = [0.0] * 169
new['freq']['fold'] = [1.0] * 169

rows = []
for nodes in ([old, new], [new, old]):
    advisor = PreflopAdvisor(dict(pack, nodes=nodes))
    result = advisor.advise(hero_cards=['As', 'Ah'], hero_position='BTN', stack_bb=25)
    rows.append(dict(input_order=[n['id'] for n in nodes],
                     chosen_node=result['node_id'], action=result['recommended'],
                     nodes_loaded=len(advisor.nodes), index_keys=len(advisor._index)))
print(json.dumps(dict(scope='SYNTHETIC_LOOKUP_COLLISION_NOT_PRODUCTION_RANGE_AUDIT',
                      does_not_prove_deployed_packs_conflict=True,
                      no_capture_or_system_input=True, cases=rows), indent=2))
