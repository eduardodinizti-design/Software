"""Testes do DB de field (stats por vilão a partir do texto das HHs)."""
from field_stats import build_field

_HH = """PPPoker Hand #1:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: AAA (10000 in chips)
Seat 2: BBB (10000 in chips)
Seat 3: CCC (10000 in chips)
BBB: posts small blind 50
CCC: posts big blind 100
*** HOLE CARDS ***
Dealt to AAA [Ah Kh]
AAA: raises 200 to 300
BBB: folds
CCC: calls 200
*** FLOP *** [2c 7d Js]
CCC: checks
AAA: bets 300
CCC: calls 300
*** TURN *** [2c 7d Js 5h]
CCC: checks
AAA: checks
*** SUMMARY ***
Total pot 1300 | Rake 0

PPPoker Hand #2:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: AAA (10000 in chips)
Seat 2: BBB (10000 in chips)
Seat 3: CCC (10000 in chips)
BBB: posts small blind 50
CCC: posts big blind 100
*** HOLE CARDS ***
Dealt to AAA [Qd Qs]
AAA: raises 200 to 300
BBB: raises 600 to 900
CCC: folds
AAA: calls 600
*** FLOP *** [Qh 3c 8d]
AAA: bets 500
BBB: folds
*** SUMMARY ***
Total pot 1900 | Rake 0
"""


def test_counts_hands():
    f = build_field(_HH)
    assert f.players['AAA'].hands == 2
    assert f.players['BBB'].hands == 2
    assert f.players['CCC'].hands == 2


def test_vpip_pfr():
    f = build_field(_HH)
    a = f.stats('AAA')
    # AAA abriu (raise) nas 2 mãos -> VPIP 100, PFR 100
    assert a['vpip'] == 100.0 and a['pfr'] == 100.0
    c = f.stats('CCC')
    # CCC: mão1 call (vpip), mão2 fold -> VPIP 50, PFR 0
    assert c['vpip'] == 50.0 and c['pfr'] == 0.0


def test_3bet():
    f = build_field(_HH)
    b = f.stats('BBB')
    # BBB enfrentou raise nas 2 mãos (AAA abriu); 3betou 1x (mão2) -> 3bet 50%
    assert b['threebet'] == 50.0
    assert f.players['BBB'].faced_raise == 2
    assert f.players['BBB'].threebet == 1


def test_postflop_af():
    f = build_field(_HH)
    a = f.stats('AAA')
    # AAA pós-flop: mão1 bet+check, mão2 bet -> aggr=2, call=0 -> af = 2.0
    assert a['af'] == 2.0


def test_posts_not_vpip():
    f = build_field(_HH)
    # BBB postou SB nas 2, foldou mão1, 3betou mão2 -> VPIP conta só a mão que agiu voluntário
    assert f.stats('BBB')['vpip'] == 50.0


def test_tag_small_sample():
    f = build_field(_HH)
    assert f.stats('AAA')['tag'] == '?'   # <25 mãos


# ---------- Tier 2: steal / fold3bet / cbet / foldcbet ----------
_STEAL_CBET = """PPPoker Hand #10:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: BTN (10000 in chips)
Seat 2: SB (10000 in chips)
Seat 3: BB (10000 in chips)
SB: posts small blind 50
BB: posts big blind 100
*** HOLE CARDS ***
Dealt to BTN [Ah Kh]
BTN: raises 200 to 300
SB: folds
BB: calls 200
*** FLOP *** [2c 7d Js]
BB: checks
BTN: bets 300
BB: folds
*** SUMMARY ***
Total pot 650 | Rake 0
"""

_FOLD3BET = """PPPoker Hand #11:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: BTN (10000 in chips)
Seat 2: SB (10000 in chips)
Seat 3: BB (10000 in chips)
Seat 4: UTG (10000 in chips)
SB: posts small blind 50
BB: posts big blind 100
*** HOLE CARDS ***
Dealt to UTG [Ah Kh]
UTG: raises 200 to 300
BTN: raises 600 to 900
SB: folds
BB: folds
UTG: folds
*** SUMMARY ***
Total pot 1350 | Rake 0
"""


def test_steal_attempt():
    f = build_field(_STEAL_CBET)
    s = f.stats('BTN')
    assert s['steal'] == 100.0          # BTN abriu roubo (pote não aberto, assento de roubo)


def test_cbet_and_foldcbet():
    f = build_field(_STEAL_CBET)
    assert f.stats('BTN')['cbet'] == 100.0        # PFR apostou o flop
    assert f.stats('BB')['foldcbet'] == 100.0     # BB foldou à c-bet


def test_fold_to_3bet():
    f = build_field(_FOLD3BET)
    s = f.stats('UTG')
    assert s['fold3bet'] == 100.0        # abriu e foldou ao 3bet
    assert f.players['UTG'].fold3bet_opp == 1 and f.players['UTG'].fold3bet_made == 1


def test_no_cbet_when_pfr_checks():
    hh = _STEAL_CBET.replace('BTN: bets 300\nBB: folds', 'BTN: checks\nBB: checks')
    f = build_field(hh)
    assert f.stats('BTN')['cbet'] == 0.0          # teve oportunidade mas deu check
    assert f.players['BTN'].cbet_opp == 1


# ---------- LIMP-RERAISE (tell de bot — nvt-exploit-anti-bot-pppoker) ----------
_LRR = """PPPoker Hand #20:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: Raiser (10000 in chips)
Seat 2: SB (10000 in chips)
Seat 3: BB (10000 in chips)
Seat 4: Bote (10000 in chips)
SB: posts small blind 50
BB: posts big blind 100
*** HOLE CARDS ***
Dealt to Bote [Ah As]
Bote: calls 100
Raiser: raises 300 to 400
SB: folds
BB: folds
Bote: raises 900 to 1300
Raiser: folds
*** SUMMARY ***
Total pot 1750 | Rake 0
"""

# limpou e NÃO re-raiseou (só call ao raise) -> opp mas not made
_LIMP_CALL = """PPPoker Hand #21:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: Raiser (10000 in chips)
Seat 4: Fish (10000 in chips)
Raiser: posts small blind 50
Fish: posts big blind 100
*** HOLE CARDS ***
Fish: calls 0
Raiser: raises 300 to 400
Fish: calls 300
*** SUMMARY ***
Total pot 800 | Rake 0
"""

# limpou e ninguém raiseou -> limp sem oportunidade de re-raise
_LIMP_NORAISE = """PPPoker Hand #22:  Tournament #9, $0 USD Hold'em No Limit - Level  (50/100 - Ante 0) -  UTC
Table 'T' 6-max Seat #1 is the button
Seat 1: Limper (10000 in chips)
Seat 2: SB (10000 in chips)
Seat 3: BB (10000 in chips)
SB: posts small blind 50
BB: posts big blind 100
*** HOLE CARDS ***
Limper: calls 100
SB: calls 50
BB: checks
*** FLOP *** [2c 7d Js]
SB: checks
BB: checks
Limper: checks
*** SUMMARY ***
Total pot 300 | Rake 0
"""


def test_limp_reraise_detected():
    f = build_field(_LRR)
    p = f.players['Bote']
    assert p.limp_made == 1
    assert p.limp_reraise_opp == 1 and p.limp_reraise_made == 1
    assert f.stats('Bote')['limp_reraise'] == 100.0
    assert f.stats('Bote')['limp_reraise_opp'] == 1


def test_limp_then_call_is_opp_not_made():
    f = build_field(_LIMP_CALL)
    p = f.players['Fish']
    assert p.limp_made == 1
    assert p.limp_reraise_opp == 1 and p.limp_reraise_made == 0
    assert f.stats('Fish')['limp_reraise'] == 0.0


def test_limp_no_raise_no_opportunity():
    f = build_field(_LIMP_NORAISE)
    p = f.players['Limper']
    assert p.limp_made == 1
    assert p.limp_reraise_opp == 0
    assert f.stats('Limper')['limp_reraise'] is None   # sem oportunidade -> None


def test_raiser_is_not_a_limper():
    f = build_field(_LRR)
    assert f.players['Raiser'].limp_made == 0          # abriu, não limpou
