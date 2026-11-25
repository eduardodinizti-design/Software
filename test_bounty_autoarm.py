"""AUTO-ARME da caça de bounty (Eduardo 24/11): o advise_from_suprema DETECTA PKO pelo stream e LIGA
hunt_bounty + modo pko + calibra o scale sozinho (sem flag). Resultado: contra o open-shove de um
shortie BOUNTIADO que o hero COBRE, o DROP EQUITY do bounty ALARGA o call (caça). Fora de PKO, nada
muda. Antes a caça ficava PARADA no default (chip_ev, hunt off)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import suprema_bounty
from suprema_state import SupremaTable, advise_from_suprema, _table_is_pko
from assistir_suprema import load_advisor

_ADV = load_advisor()


def _table(with_bounty, bounty_raw=200):
    suprema_bounty.set_scale(None)
    t = SupremaTable(bb_chips=500)
    t.feed_json({'event': 'gameinfo', 'data': {'game_info': {'dealer_seat': 6, 'avgStack': 10000, 'pot': 5500}}})
    sb = {'seat': 6, 'uid': 3, 'coins': 0, 'chips': 5000, 'chips_round': 5000, 'role': 82}
    if with_bounty:
        sb['bounty'] = bounty_raw
    gs = {'1': {'seat': 2, 'uid': 1, 'coins': 19500, 'chips': 500, 'chips_round': 500, 'role': 93, 'cards': [59, 56]},
          '2': sb}
    t.feed_json({'uid': 1, 'event': 'gamestart', 'data': {
        'game_info': {'game_counter': 7, 'dealer_seat': 6, 'avgStack': 10000, 'pot': 5500}, 'game_seat': gs}})
    if with_bounty:
        t.feed_json({'uid': 1, 'event': 'gamestart', 'data': {'kodata': [{'reward': 50}]}})
    t.feed_json({'uid': 1, 'event': 'gameinfo', 'data': {'game_info': {'pot': 5500}}})
    t.feed_json({'uid': 1, 'event': 'prompt', 'data': {'game_seat': gs, 'gamer_prompt': {'call': 4500}}})
    return t


def _advise(with_bounty, cards):
    t = _table(with_bounty)
    t.players[t.hero_seat]['cards'] = cards
    return advise_from_suprema(t, _ADV)     # SEM hunt_bounty: auto-arma se PKO


def test_detecta_pko():
    assert _table_is_pko(_table(True)) is True
    assert _table_is_pko(_table(False)) is False


def test_calibra_scale_auto():
    _advise(True, ['Kd', '9c'])             # dispara o auto-arme (calibra o scale)
    assert suprema_bounty.BOUNTY_CHIP_SCALE                       # calibrado (starting/base)


def test_bounty_alarga_call_do_shove():
    r = _advise(True, ['Kd', '9c'])         # K9o cobre shortie bountiado -> caça (call)
    assert r.get('recommended') == 'call'
    assert 'BOUNTY_ALARGA_CALL_SHOVE' in r.get('caveats', [])


def test_sem_pko_nao_alarga():
    r = _advise(False, ['Kd', '9c'])        # mesma mão sem bounty -> fold (nó chip-EV)
    assert r.get('recommended') == 'fold'
    assert 'BOUNTY_ALARGA_CALL_SHOVE' not in r.get('caveats', [])


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
