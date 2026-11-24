"""Testes da marcação ao vivo + ponte tag->sombra."""
from player_tags import TagStore
from tag_live import TagLive, annotate_hud, attach_shadow, hit_seat

_RICH = {
    '14698178': {'room': 'BOUNTY PKO', 'players': [
        {'seat': 0, 'uid': 13978563, 'name': 'pp13978563'},
        {'seat': 3, 'uid': 13797173, 'name': 'Just do it'},
        {'seat': 5, 'uid': 11219937, 'name': 'Oakiee'},
    ]},
}


# ---------- (b) annotate_hud ----------
def test_annotate_marks_tag_and_plan():
    store = TagStore(); store.set('13797173', 'bote')
    hud = {'s3': {'stats': {}, '_uid': '13797173'}}
    annotate_hud(hud, store)
    assert hud['s3']['tag'] == 'bote'
    assert hud['s3']['tag_plan']['aggression'] == 'max'


def test_annotate_suggests_bot_when_untagged():
    store = TagStore()
    hud = {'s3': {'_uid': '999',
                  'stats': {'limp_reraise': 50.0, 'limp_reraise_opp': 6, 'limp_reraise_made': 3}}}
    annotate_hud(hud, store)
    assert hud['s3']['bot_suggestion']['confidence'] == 'high'
    assert 'tag' not in hud['s3']                      # sugere, não marca


def test_annotate_no_suggestion_when_already_bote():
    store = TagStore(); store.set('999', 'bote')
    hud = {'s3': {'_uid': '999',
                  'stats': {'limp_reraise': 50.0, 'limp_reraise_opp': 6, 'limp_reraise_made': 3}}}
    annotate_hud(hud, store)
    assert 'bot_suggestion' not in hud['s3']


def test_annotate_noop_without_store():
    hud = {'s3': {'_uid': '1', 'stats': {}}}
    annotate_hud(hud, None)
    assert hud['s3'] == {'_uid': '1', 'stats': {}}


# ---------- (b) attach_shadow ----------
def test_attach_shadow_lists_tagged_and_suggestions():
    store = TagStore(); store.set('13797173', 'nvt')
    hud = {
        's3': {'_uid': '13797173'},
        's5': {'_uid': '999', 'bot_suggestion': {'confidence': 'medium', 'reasons': ['x']}},
    }
    annotate_hud(hud, store)
    adv = {'status': 'ADVICE', 'recommended': 'call'}
    attach_shadow(adv, hud)
    sh = adv['tag_plan_shadow']
    assert sh['seats']['s3']['tag'] == 'nvt' and sh['seats']['s3']['actionable'] is True
    assert sh['suggestions']['s5']['suggest_tag'] == 'bote'
    assert adv['recommended'] == 'call'                # SOMBRA: não mexe na decisão


def test_attach_shadow_noop_when_nothing():
    adv = {'status': 'ADVICE', 'recommended': 'fold'}
    attach_shadow(adv, {'s1': {'_uid': '1'}})          # sem tag nem sugestão
    assert 'tag_plan_shadow' not in adv


# ---------- (a) marcação ao vivo ----------
def test_tag_seat_resolves_uid():
    tl = TagLive(TagStore(), _RICH)
    uid = tl.tag_seat(3, 'bote', table_ref='14698178')
    assert uid == '13797173' and tl.store.tag_of('13797173') == 'bote'


def test_tag_empty_seat_returns_none():
    tl = TagLive(TagStore(), _RICH)
    assert tl.tag_seat(7, 'bote', table_ref='14698178') is None


def test_cycle_seat_advances_and_clears():
    tl = TagLive(TagStore(), _RICH)
    assert tl.cycle_seat(3, table_ref='14698178') == ('13797173', 'bote')
    assert tl.cycle_seat(3, table_ref='14698178')[1] == 'station'
    # pula até o fim do ciclo -> remove
    tl.store.set('13797173', 'nvt')                    # última do CYCLE
    uid, nt = tl.cycle_seat(3, table_ref='14698178')
    assert nt is None and tl.store.tag_of('13797173') is None


def test_uid_at_and_overview():
    tl = TagLive(TagStore(), _RICH); tl.store.set('11219937', 'station')
    assert tl.uid_at(5, table_ref='14698178') == '11219937'
    ov = {r['seat']: r['tag'] for r in tl.overview('14698178')}
    assert ov[5] == 'station' and ov[0] is None


def test_hit_seat_maps_click():
    boxes = {'s0': (0, 0, 100, 50), 's3': (0, 60, 100, 110)}
    assert hit_seat(50, 30, boxes) == 's0'
    assert hit_seat(50, 80, boxes) == 's3'
    assert hit_seat(200, 200, boxes) is None
