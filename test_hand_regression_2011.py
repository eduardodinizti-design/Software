"""Regressão 20/11: trava o comportamento do acumulador/emissor fechado nesta sessão —
room agnóstico, chips=incremento (to do raise), uncalled bet, herói resolvido/omitido,
filtro _clean (mão parcial de attach descartada), semear assentos do DealerInfo, e
seat->uid do WinnerRSP (que resolve os rótulos no finalize). Puro (sem Frida)."""
from hand_accumulator import HandAccumulator
from ppp_actions import to_hh_action


def _acc(**kw):
    return HandAccumulator(tournament_id="1", table_tag="T_1 0", max_seats=9, **kw)


def _hand_foldout():
    """SB/BB + open raise, todos foldam: gera uncalled bet devolvido ao raiser.
    Rótulos vêm do seat_uids do WinnerRSP (111/333/555); stacks do DealerInfo."""
    a = _acc()
    a.on_dealer(button_seat=2, seats=[{"seat": 2, "stack": 100000}, {"seat": 3, "stack": 100000},
                                      {"seat": 5, "stack": 100000}])
    a.on_round_start(1, cur_blind=50, hero_cards=[771, 782], hero_seat=3)
    a.on_action(3, 8, 50)      # SB
    a.on_action(5, 9, 100)     # BB
    a.on_action(2, 7, 300)     # open -> raises (preflop já tem "agressão" = o BB)
    a.on_action(3, 1, 0)       # fold
    a.on_action(5, 1, 0)       # fold
    a.on_winner(collected=[(2, 250)], total_pot=250,
                seat_uids=[{"seat": 2, "uid": 111}, {"seat": 3, "uid": 333}, {"seat": 5, "uid": 555}])
    return a.on_hand_over()


def test_room_agnostico_no_cabecalho():
    a = HandAccumulator(room="SupremaPoker", tournament_id="9", table_tag="S 0")
    a.on_round_start(1, cur_blind=10)
    a.on_action(1, 1, 0)
    assert a.on_hand_over().startswith("SupremaPoker Hand #")


def test_preflop_open_vira_raise_com_to_correto():
    # chips=incremento: o open de 300 (seat2=uid111, sem blind) -> "raises 300 to 300"
    assert "111: raises 300 to 300" in _hand_foldout()


def test_uncalled_bet_devolvido_ao_raiser():
    txt = _hand_foldout()
    assert "Uncalled bet (200) returned to 111" in txt     # 450 gross - 250 pote
    assert "111 collected 250 from pot" in txt


def test_dealer_semeia_assentos_mesmo_sem_agir():
    txt = _hand_foldout()
    for uid in ("111", "333", "555"):                      # os 3 do DealerInfo viram Seat:
        assert f": {uid} (" in txt


def test_hero_omitido_quando_assento_desconhecido():
    a = _acc()
    a.on_round_start(1, cur_blind=10, hero_cards=[771, 782])   # sem hero_seat
    a.on_action(1, 1, 0)
    assert "Dealt to" not in a.on_hand_over()      # não emite Dealt sem assento (evita unknown_player)


def test_hero_resolvido_quando_assento_conhecido():
    assert "Dealt to 333 [" in _hand_foldout()     # hero_seat=3 -> uid 333


def test_clean_descarta_mao_de_attach_no_meio():
    a = _acc()
    a.on_action(1, 3, 500)     # começou no MEIO (sem RoundStart stage1) -> mão "suja"
    a.on_action(2, 1, 0)
    assert a.on_hand_over() is None     # descartada, não emitida


def test_action_types_4_5_6_sao_agressao():
    for code in (4, 5, 6, 7):
        assert to_hh_action(code, 2000, street_has_aggression=False) == {"action": "bets", "amount": 2000}
        assert to_hh_action(code, 5000, street_has_aggression=True) == {"action": "raises", "to": 5000}
