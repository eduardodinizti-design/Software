"""Testes do sink de texto Hand2Note (pasta/dia, arquivo/torneio)."""
import os
from hand_text_sink import HandTextSink, text_path
from hand_history import parse_hand_histories


def test_path_pattern(tmp_path):
    p = text_path(str(tmp_path), 'PPP 13745315', ts='2026-11-18T01:00:00')
    assert p.replace('\\', '/').endswith('2026/11/18/PPP_13745315.txt')


def test_write_appends_and_parseable(tmp_path):
    s = HandTextSink(base=str(tmp_path))
    hh = ("PPPoker Hand #1:  Tournament #9, $0 USD Hold'em No Limit - Level  (0/0 - Ante 0) -  UTC\n"
          "Table 'ClubId:,Table:T' 9-max Seat #1 is the button\n"
          "Seat 1: 111 (1000 in chips)\n"
          "*** HOLE CARDS ***\n"
          "Dealt to 111 [Ah Kh]\n"
          "*** SUMMARY ***\nTotal pot 0 | Rake 0")
    p1 = s.write(hh, tournament='T1', ts='2026-11-18T01:00:00')
    p2 = s.write(hh, tournament='T1', ts='2026-11-18T01:05:00')
    assert p1 == p2 and s.count == 2        # mesmo arquivo (mesmo dia/torneio)
    assert os.path.exists(p1)
    txt = open(p1, encoding='utf-8').read()
    hands = parse_hand_histories(txt)
    assert len(hands) == 2                   # duas mãos no arquivo, re-parseáveis


def test_separate_tournaments(tmp_path):
    s = HandTextSink(base=str(tmp_path))
    a = s.write("PPPoker Hand #1:  x\nTable 'x' 9-max Seat #1 is the button\nSeat 1: 1 (1 in chips)",
                tournament='TA', ts='2026-11-18T01:00:00')
    b = s.write("PPPoker Hand #2:  x\nTable 'x' 9-max Seat #1 is the button\nSeat 1: 1 (1 in chips)",
                tournament='TB', ts='2026-11-18T01:00:00')
    assert a != b and len(s.written) == 2    # arquivos diferentes por torneio


def test_empty_text_noop(tmp_path):
    s = HandTextSink(base=str(tmp_path))
    assert s.write('', tournament='T') is None
    assert s.count == 0
