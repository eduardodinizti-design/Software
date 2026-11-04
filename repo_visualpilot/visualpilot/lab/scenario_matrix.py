"""Controlled Hold'em position/board matrix, grounded in explicit NVT preflop nodes."""
from .postflop import range_from_nvt,validate_cards

BOARDS={
    'top_pair_overcard':('Jc','7d','2s','Ah'),
    'paired':('9h','9c','2d','Ks'),
    'flush_draw':('Kh','8h','2c','3d'),
    'monotone':('Kh','8h','2h','3d'),
    'connected':('9c','8d','7s','Qh'),
    'four_flush':('Kh','8h','2h','3h'),
}
# Hero position, opponent position, Hero arrival node/action, opponent arrival node/action.
CONTEXTS={
    'BB_vs_BTN':('oop','BB','BTN','chip_ev|mid|25|vs_open|BB|BTN|-','call','chip_ev|mid|25|open_raise|BTN||-','raise'),
    'BTN_vs_BB':('ip','BTN','BB','chip_ev|mid|25|open_raise|BTN||-','raise','chip_ev|mid|25|vs_open|BB|BTN|-','call'),
    'BB_vs_CO':('oop','BB','CO','chip_ev|mid|25|vs_open|BB|CO|-','call','chip_ev|mid|25|open_raise|CO||-','raise'),
    'BB_vs_SB':('ip','BB','SB','chip_ev|mid|25|vs_open|BB|SB|-','call','chip_ev|mid|25|open_raise|SB||-','raise'),
    'SB_vs_BB':('oop','SB','BB','chip_ev|mid|25|open_raise|SB||-','raise','chip_ev|mid|25|vs_open|BB|SB|-','call'),
}


def make_case(book,context,texture,street='turn',hero=None):
    if street not in ('flop','turn'): raise ValueError('Rua não suportada pela matriz.')
    position,hero_seat,opponent_seat,hero_node,hero_action,villain_node,villain_action=CONTEXTS[context]
    hero=list(hero) if hero is not None else ['Jh','Th'];board=list(BOARDS[texture][:3] if street=='flop' else BOARDS[texture])
    validate_cards(hero+board)
    source_node=next(n for n in book.nodes.values() if n['id']==hero_node)
    from ..agent.connector import canonical_hand
    hand_index=book.hands[canonical_hand(hero)]
    if hand_index in source_node.get('outOfRange',[]) or source_node['freq'][hero_action][hand_index]<=0:
        raise ValueError('Mão do Hero não chega pela ação pré-flop declarada.')
    weights,source=range_from_nvt(book,villain_node,villain_action,hero+board)
    return dict(id=f'{context}:{texture}:{street}',hero=hero,board=board,range=weights,
        hero_position=position,opponent_checked=position=='ip',pot=10 if street=='turn' else 6,
        stack=16 if street=='turn' else 18,
        provenance=dict(opponent=source,hero_node=hero_node,hero_action=hero_action,
            hero_arrival_frequency=source_node['freq'][hero_action][hand_index],
            hero_seat=hero_seat,opponent_seat=opponent_seat),
        assumptions=['controlled_postflop_state_not_full_hand_reconstruction',
                     'range_conditioned_on_preflop_action_and_cards_only',
                     'IP_prior_check_does_not_condition_range_in_this_matrix',
                     'one_hero_hand_not_complete_169_hand_coverage'])


def condition_on_check(case,model,config):
    """Condition the IP scenario on the check already observed before Hero acts."""
    import math
    from copy import deepcopy
    from .range_state import normalize_range,condition
    from .multistreet import sizes
    result=deepcopy(case)
    result['range']=normalize_range(case['range'])
    if case['hero_position']!='ip':return result
    bets,_=sizes(case['pot'],case['stack'],config)
    legal=('check',)+tuple(f'bet:{b:g}' for b in bets)
    ctx=dict(pot=case['pot'],stack=case['stack'],hero_position='ip',pko=None)
    likelihood={}
    for combo in result['range']:
        row=model(combo,tuple(case['board']),(),legal,dict(ctx))
        if set(row)!=set(legal) or any(not math.isfinite(p) or not 0<=p<=1 for p in row.values()) or abs(sum(row.values())-1)>1e-9:
            raise ValueError('Modelo de check inválido.')
        likelihood[combo]=row['check']
    result['range'],probability=condition(result['range'],likelihood)
    result['provenance']['observed_check_probability_under_model']=probability
    result['assumptions']=[a for a in result['assumptions'] if a!='IP_prior_check_does_not_condition_range_in_this_matrix']
    result['assumptions'].append('observed_check_conditioned_using_synthetic_model')
    return result
