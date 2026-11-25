"""Bug QQ (Eduardo 25/11, pós-mortem): CÉREBRO=all_in NÃO pode virar um flat CALL.
Quando não há botão all-in, o jam deve sair pelo TOPO do slider; se o slider não foi lido mas há
botão de aumentar, jamma pelo STACK do hero; só cai p/ call se não houver como aumentar (jamais folda)."""
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
from suprema_state import SupremaTable
import suprema_act as A

ADV = lambda rec, **kw: dict(status='ADVICE', recommended=rec, **kw)


def _table(gamer_prompt, bb_chips=500, hero_chips=None):
    t = SupremaTable(bb_chips=bb_chips)
    t.feed_json({"event": "prompt", "data": {"gamer_prompt": gamer_prompt}})
    if hero_chips is not None:
        t.hero_seat = 2
        t.players[2] = {'chips': hero_chips}
    return t


# facing-bet SEM botão all-in, mas COM slider (raise_range lido)
FACING_NO_ALLIN = {"fold": True, "check": None, "call": 500,
                   "raise": "range,1000,10000,2X,1000,3X,1500,4X,2000", "all_in": None}
# facing-bet SEM all-in E SEM slider lido (raise=True booleano) -> o cenário exato do bug QQ
FACING_NO_SLIDER = {"fold": True, "check": None, "call": 500, "raise": True, "all_in": None}
# só fold/call (nenhum botão de aumentar) -> jam impossível, mas JAMAIS folda o premium
ONLY_CALL = {"fold": True, "check": None, "call": 500, "raise": None, "all_in": None}


def test_allin_sem_botao_jamma_no_topo_do_slider():
    p = A.plan_action(ADV('all_in'), _table(FACING_NO_ALLIN))
    assert p['action'] == A.RAISE                     # sem botão all-in, jamma via Aumentar
    assert p['chips'] == 10000.0                       # TOPO do slider (não o min, não um flat)
    assert p['reason'] == 'jam_slider_max'


def test_allin_slider_nao_lido_jamma_pelo_stack():
    # BUG QQ: aqui virava CALL (flat). Agora jamma pelo stack do hero.
    p = A.plan_action(ADV('all_in'), _table(FACING_NO_SLIDER, hero_chips=9000))
    assert p['action'] == A.RAISE
    assert p['chips'] == 9000.0                        # stack do hero = all-in
    assert 'STACK' in p['reason']
    assert p['action'] != A.CALL                       # NUNCA mais um flat silencioso


def test_allin_sem_aumento_cai_pra_call_nunca_folda():
    # sem qualquer botão de aumentar: a única forma de pôr fichas é pagar. JAMAIS folda o premium.
    p = A.plan_action(ADV('all_in'), _table(ONLY_CALL))
    assert p['action'] == A.CALL
    assert 'JAM_SEM_AUMENTO' in p['reason']


def test_allin_com_botao_continua_allin():
    # regressão: com botão all-in legal, segue all-in direto
    FACING = {"fold": True, "call": 500, "raise": "range,1000,10000,2X,1000", "all_in": True}
    p = A.plan_action(ADV('all_in'), _table(FACING))
    assert p['action'] == A.ALL_IN


def test_raise_normal_sem_size_ainda_usa_min():
    # regressão: raise NORMAL (não-jam) sem sizing continua min-raise (não vira jam)
    FACING = {"fold": True, "call": 500, "raise": "range,1000,10000,2X,1000,3X,1500", "all_in": True}
    p = A.plan_action(ADV('raise'), _table(FACING))
    assert p['action'] == A.RAISE
    assert p['chips'] == 1000.0                         # min, não o topo


if __name__ == '__main__':
    for n in list(globals()):
        if n.startswith('test_'):
            globals()[n]()
            print('OK', n)
    print('TODOS PASSARAM')
