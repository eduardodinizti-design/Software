"""Human-readable decision evidence; never invent unavailable action EVs."""


def explain(decision, candidates, selected, quality):
    state, context = decision.betting, decision.context
    position = 'OOP' if state.oop == 0 else 'IP'
    comparisons = []
    for c in candidates:
        ev = 'EV ainda nao avaliado' if c['ev_bb'] is None else 'EV %.4f BB' % c['ev_bb']
        frequency = 'mix %.1f%%' % (c['frequency'] * 100)
        if quality.get('selection_mode') == 'exact_response':
            frequency += ', selecao %.1f%%' % (c['selection_frequency'] * 100)
        comparisons.append('%s %.3f BB: %s, %s' % (
            c['action'], c['additional_bb'], frequency, ev))
    return dict(situation='%s %s vs %s; %s %s; pote %.3f BB; stacks %.3f/%.3f BB' % (
                context.positions[0], position, context.positions[1], state.street,
                ' '.join(state.board), state.pot_bb, *state.stacks),
                selected_action=selected.id, comparisons=comparisons,
                public_history=list(state.history), arrival_model=context.arrival_id,
                method=quality.get('method'), gap_bb=quality.get('global_gap_bb'),
                gap_scope=quality.get('gap_scope'),
                reason='Frequencia do combo no no exato da politica; sorteio estavel por decisao.',
                limitation='Ausencia de EV nao significa EV zero; gap do modelo nao comprova lucro real.')
