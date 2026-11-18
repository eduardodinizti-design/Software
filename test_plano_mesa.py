"""Testes do plano_mesa (consulta do DB de exploração na mesa)."""
import json
import plano_mesa


def _db():
    return {
        'FISHY': {'hands': 500, 'category': 'fish', 'tags': ['station'],
                  'stats': {'vpip': 40, 'pfr': 12, 'threebet': 4, 'steal': 20,
                            'cbet': 30, 'foldcbet': 25},
                  'preflop': [{'situation': 'isolar_limp', 'direction': 'wider',
                               'strength': 'strong', 'why': 'fish'}],
                  'postflop': [{'situation': 'value_bet', 'direction': 'wider',
                                'strength': 'strong', 'why': 'paga demais'}]},
        'REGGY': {'hands': 3000, 'category': 'reg', 'tags': [],
                  'stats': {'vpip': 22, 'pfr': 16, 'threebet': 8, 'steal': 35,
                            'cbet': 55, 'foldcbet': 45},
                  'preflop': [], 'postflop': []},
    }


def test_unknown_villain():
    out = plano_mesa.format_villain('XXX', None)
    assert 'SEM LEITURA' in out and 'base GTO' in out


def test_known_villain_shows_tags_and_adjust():
    out = plano_mesa.format_villain('FISHY', _db()['FISHY'])
    assert 'FISH' in out and 'station' in out
    assert 'isolar_limp' in out and 'value_bet' in out
    assert 'V40' in out and 'FCB25' in out


def test_reg_without_exploit():
    out = plano_mesa.format_villain('REGGY', _db()['REGGY'])
    assert 'sem exploit claro' in out


def test_table_summary_counts():
    s = plano_mesa.table_summary(['FISHY', 'REGGY', 'NOVO'], _db())
    assert 'fish:1' in s and 'reg:1' in s and 'unknown:1' in s


def test_prio_orders_fish_first(tmp_path, capsys, monkeypatch):
    dbfile = tmp_path / 'db.json'
    dbfile.write_text(json.dumps(_db()), encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['plano_mesa.py', '--db', str(dbfile), 'REGGY', 'FISHY'])
    plano_mesa.main()
    out = capsys.readouterr().out
    # FISHY (fish) deve vir antes de REGGY (reg)
    assert out.index('FISHY') < out.index('REGGY')
