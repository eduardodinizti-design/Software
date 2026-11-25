"""Testes da caça de BOUNTY PKO (suprema_bounty). O campo seat.bounty = cash de bounty ACUMULADO
(ganho), 0 p/ fresco; a CABEÇA de um jogador = base (kodata 2×min reward) + acumulado. O bounty é
moeda de PRÊMIO/buy-in (play-money), convertido p/ equivalente em fichas de stack via stack inicial."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import suprema_bounty as B


def _state(hero_bb, vill_bb, vill_collected, *, bb_chips=2000.0, pot_bb=5.0, to_call_bb=4.0,
           base=4.4, vill_ko=3, avg_stack=100000, players_left=100, players_total=200, rebuys=0):
    return dict(bb_chips=bb_chips, pot={'pot_bb': pot_bb}, to_call={'to_call_bb': to_call_bb},
                mtt=dict(bounty_base=base, avg_stack=avg_stack, players_left=players_left,
                         players_total=players_total, rebuys=rebuys),
                seats={'hero': dict(stack_bb=hero_bb, bounty_raw=6.6, ko=4),
                       'seat3': dict(stack_bb=vill_bb, bounty_raw=vill_collected, ko=vill_ko)})


def test_head_raw_base_mais_acumulado():
    assert B.head_raw(6.6, 4.4) == 11.0        # cabeça = base 4.4 + ganho 6.6
    assert B.head_raw(0, 4.4) == 4.4           # fresco (0 KO) = só a base
    assert B.head_raw(5.0, None) is None       # sem base -> não dá


def test_scale_from_structure_5050():
    sc = B.scale_from_structure(50000, 4.4)    # cabeça fresca 4.4 lê 1 stack inicial (50/50)
    assert abs(sc - 50000 / 4.4) < 1e-3, sc


def test_scale_from_structure_nao_5050():
    sc = B.scale_from_structure(30000, 3.0, head_fraction=0.4)
    assert abs(sc - (30000 * 0.4 / 0.6 / 3.0)) < 1e-3, sc


def test_raw_to_bb():
    sc = 50000 / 4.4
    assert abs(B.raw_to_bb(11.0, 2000.0, sc) - (11.0 * sc / 2000.0)) < 1e-2


def test_est_starting_stack_do_gameinfo():
    mtt = dict(avg_stack=100000, players_left=100, players_total=200, rebuys=0)
    assert B.est_starting_stack(mtt) == 50000


def test_tournament_base_do_kodata():
    assert B.tournament_base(dict(mtt=dict(bounty_base=4.4))) == 4.4
    assert B.tournament_base(dict(mtt={})) is None


def test_sem_base_nao_chuta():
    tg = B.bounty_targets(_state(80, 4, 6.6), scale=10000.0, base=None)
    v = next(t for t in tg if t['seat'] == 'seat3')
    assert v['head_bb'] is None and v['note'] == 'SEM_BASE' and v['pot_fraction'] == 0.0


def test_sem_calibracao_nao_chuta():
    tg = B.bounty_targets(_state(80, 4, 6.6), scale=None, base=4.4)
    v = next(t for t in tg if t['seat'] == 'seat3')
    assert v['head_bb'] is None and v['note'] == 'SEM_CALIBRACAO'


def test_vilao_curto_coberto_eh_juicy_e_desconta_equity():
    sc = B.scale_from_structure(50000, 4.4)
    tg = B.bounty_targets(_state(80, 4, 6.6), scale=sc, base=4.4)   # hero 80bb cobre vilão 4bb, cabeça 11
    v = next(t for t in tg if t['seat'] == 'seat3')
    assert v['covers'] and v['short'] and v['juicy'], v
    assert v['head_bb'] and v['head_bb'] > 0 and v['pot_fraction'] > 0


def test_vilao_cobre_hero_nao_realiza():
    sc = B.scale_from_structure(50000, 4.4)
    tg = B.bounty_targets(_state(80, 200, 6.6), scale=sc, base=4.4)   # vilão 200bb cobre hero 80bb
    v = next(t for t in tg if t['seat'] == 'seat3')
    assert not v['covers'] and v['pot_fraction'] == 0.0, v


def test_hunt_auto_resolve_do_estado():
    out = B.hunt(_state(80, 4, 6.6))             # base 4.4 (mtt) + SS estimado 50000
    assert out['bounty_base'] == 4.4 and out['starting_stack'] == 50000 and out['ss_estimated']
    assert out['calibrated'] and out['best_target'] and out['best_fraction'] > 0


def test_hunt_override_stack_manual_nao_estima():
    out = B.hunt(_state(80, 4, 6.6), starting_stack=50000)
    assert out['starting_stack'] == 50000 and out['ss_estimated'] is False and out['calibrated']


def test_hunt_sem_base_nao_calibra():
    st = _state(80, 4, 6.6); st['mtt']['bounty_base'] = None
    out = B.hunt(st)
    assert not out['calibrated'] and out['best_target'] is None


def test_resolve_ss_detectado_vence_estimativa():
    st = _state(80, 4, 6.6)
    st['mtt']['starting_stack'] = 48000; st['mtt']['ss_level'] = 1   # detectado no começo
    ss, src = B.resolve_starting_stack(st)
    assert ss == 48000 and src == 'detectado_L1'                     # vence a estimativa (50000)
    out = B.hunt(st)
    assert out['starting_stack'] == 48000 and out['ss_source'] == 'detectado_L1' and not out['ss_estimated']


def test_resolve_ss_override_manual_vence_tudo():
    st = _state(80, 4, 6.6); st['mtt']['starting_stack'] = 48000
    ss, src = B.resolve_starting_stack(st, override=50000)
    assert ss == 50000 and src == 'manual'


def test_deteccao_ss_menor_avgstack_no_comeco():
    from suprema_state import SupremaTable
    t = SupremaTable()
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'blindsLevel': 1, 'avgStack': 50000, 'blinds': 100}}})
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'blindsLevel': 5, 'avgStack': 130000, 'blinds': 600}}})
    assert t.mtt['starting_stack'] == 50000 and t.mtt['ss_level'] == 1   # pega o menor (começo, exato)


def test_deteccao_ss_join_tarde_usa_menor_disponivel():
    from suprema_state import SupremaTable
    t = SupremaTable()
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'blindsLevel': 9, 'avgStack': 160000}}})
    assert t.mtt['starting_stack'] == 160000 and t.mtt['ss_level'] == 9   # join tarde: melhor disponível


def test_super_pko_7525_cabeca_vale_mais():
    pko = B.hunt(_state(80, 4, 6.6), starting_stack=50000, head_fraction=0.5)
    spko = B.hunt(_state(80, 4, 6.6), starting_stack=50000, head_fraction=0.75)
    assert spko['best_target']['head_bb'] > pko['best_target']['head_bb']


if __name__ == "__main__":
    for name in list(globals()):
        if name.startswith("test_"):
            globals()[name]()
            print("OK", name)
    print("TODOS PASSARAM")
