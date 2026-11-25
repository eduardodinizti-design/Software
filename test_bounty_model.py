"""Modelo de bounty compartilhado (bounty_model) + bridge no bounty_reader do PPPoker.
Bounty = moeda-prêmio; base_bb (cabeça fresca) = stack_inicial·hf/(1-hf)/bb (correto p/ PKO)."""
import json
import sys
sys.path.insert(0, r"C:\Meus Projetos\Aplicativos\_repo_software")
import bounty_model as BM
import bounty_reader as BR


def test_base_bb_5050():
    # PKO 50/50: cabeça fresca compra 1 stack inicial -> base_bb = SS/bb
    assert BM.base_bb_from_structure(50000, 1000, 0.5) == 50.0


def test_base_bb_super_pko_7525():
    # super-PKO 75/25: cabeça fresca = 3 stacks -> 3×SS/bb
    assert BM.base_bb_from_structure(50000, 1000, 0.75) == 150.0


def test_base_bb_dado_faltando_vira_none():
    assert BM.base_bb_from_structure(None, 1000) is None
    assert BM.base_bb_from_structure(50000, 0) is None
    assert BM.base_bb_from_structure(50000, 1000, 1.0) is None


def _write(tmp, obj):
    import time
    obj.setdefault("ts", time.time())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    return tmp


def test_reader_bridge_vence_ratio_legado(tmp_path):
    # hero_bounty_chips/bb_chips daria 20 (errado, mistura unidade); o BRIDGE dá SS/bb=50 (correto)
    p = _write(str(tmp_path / "b.json"), {"bb_chips": 1000, "hero_bounty_chips": 20000})
    assert BR.read_bounty_bb(p, starting_stack=50000, head_fraction=0.5) == 50.0


def test_reader_sem_stack_cai_no_legado(tmp_path):
    p = _write(str(tmp_path / "b.json"), {"bb_chips": 1000, "hero_bounty_chips": 20000})
    assert BR.read_bounty_bb(p) == 20.0            # sem starting_stack -> ratio legado (20000/1000)


def test_reader_calibrado_tem_precedencia(tmp_path):
    p = _write(str(tmp_path / "b.json"), {"bb_chips": 1000, "bounty_bb": 7.5, "hero_bounty_chips": 20000})
    assert BR.read_bounty_bb(p, starting_stack=50000) == 7.5   # bounty_bb calibrado > bridge


if __name__ == "__main__":
    import tempfile, os
    for name in list(globals()):
        if name.startswith("test_"):
            fn = globals()[name]
            if "tmp_path" in fn.__code__.co_varnames:
                with tempfile.TemporaryDirectory() as d:
                    class _P:
                        def __truediv__(self, x): return os.path.join(d, x)
                    fn(_P())
            else:
                fn()
            print("OK", name)
    print("TODOS PASSARAM")
