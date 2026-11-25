"""Testes do registro manual de tags (uid -> tag)."""
import os

from player_tags import TagStore


def test_set_get_tag_of():
    s = TagStore()
    s.set('11592929', 'Bote', note='limp-reraise clássico')
    r = s.get('11592929')
    assert r['tag'] == 'bote' and r['note'] == 'limp-reraise clássico'
    assert r['source'] == 'manual' and 'updated' in r
    assert s.tag_of('11592929') == 'bote'


def test_unknown_uid_is_none():
    assert TagStore().get('nope') is None and TagStore().tag_of('nope') is None


def test_by_tag_and_tags_in_use():
    s = TagStore()
    s.set('1', 'bote'); s.set('2', 'station'); s.set('3', 'bote')
    assert sorted(s.by_tag('bote')) == ['1', '3']
    assert s.tags_in_use() == ['bote', 'station']


def test_overwrite_and_remove():
    s = TagStore()
    s.set('1', 'bote')
    s.set('1', 'bom')                       # re-marca
    assert s.tag_of('1') == 'bom'
    assert s.remove('1') is True and s.get('1') is None
    assert s.remove('1') is False


def test_uid_coerced_to_str():
    s = TagStore()
    s.set(11592929, 'bote')                 # uid numérico
    assert s.tag_of('11592929') == 'bote'


def test_save_load_roundtrip(tmp_path):
    p = os.path.join(str(tmp_path), 'tags.json')
    s = TagStore(path=p)
    s.set('1', 'bote', note='x'); s.set('2', 'nvt')
    s.save()
    s2 = TagStore.load(p)
    assert s2.tag_of('1') == 'bote' and s2.get('1')['note'] == 'x'
    assert s2.tag_of('2') == 'nvt'


def test_load_missing_file_is_empty(tmp_path):
    s = TagStore.load(os.path.join(str(tmp_path), 'none.json'))
    assert s.all() == {}
