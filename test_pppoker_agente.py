"""TRAVA do agente PPPoker por dados (protobuf): anti-thrash 1-tentativa, DRY vs ARMADO, plano.

Lógica determinística com advisor FAKE (sem depender do pack) + um smoke de integração com o pack
real (skip se ausente). Offline: sem tela, sem clique, sem rede."""
import os
import unittest

import pppoker_agente as A
from bot_control import BotControl


def _card(rank, suit):
    return suit * 256 + rank


AA = [_card(14, 4), _card(14, 3)]     # A♠ A♥
KK = [_card(13, 4), _card(13, 3)]     # K♠ K♥


def _entry(hero_cards, tocall=100, board=None):
    """3-handed preflop, hero=BTN(seat2), SB=0/BB=1. sb=50 -> bb=100. tocall em fichas."""
    return {
        'ts': 0, 'room': 'T',
        'table': {'dealer': 2, 'sbseat': 0, 'bbseat': 1, 'sb': 50, 'minraise': 100,
                  'maxraise': 10000, 'board': board or [], 'stage': 0, 'tocall': tocall, 'pot': 150},
        'players': [
            {'seat': 0, 'uid': 1, 'name': 'sb', 'stack': 10000, 'sit': 0, 'bet': 50, 'act': 0, 'hascard': 1, 'cards': []},
            {'seat': 1, 'uid': 2, 'name': 'bb', 'stack': 10000, 'sit': 0, 'bet': 100, 'act': 0, 'hascard': 1, 'cards': []},
            {'seat': 2, 'uid': 3, 'name': 'hero', 'stack': 10000, 'sit': 0, 'bet': 0, 'act': 0, 'hascard': 1, 'cards': hero_cards},
        ],
    }


class FakeAdvisor:
    """Cérebro fake: devolve sempre a mesma recomendação (isola a lógica do agente do pack)."""
    def __init__(self, rec, size=None):
        self.rec, self.size = rec, size

    def advise_from_reading(self, state, hero, **kw):
        return {'status': 'ADVICE', 'recommended': self.rec,
                'sizing': ({'size_bb': self.size} if self.size else {})}


def _emit(advisor, *, armed=False, execute=None):
    c = BotControl()
    if armed:
        c.resume()                      # PAUSED -> RUNNING
    return A.make_table_emit(advisor, control=c, execute=execute, log=lambda *a, **k: None)


class Puras(unittest.TestCase):
    def test_street_of(self):
        self.assertEqual(A.street_of(_entry(AA)), 'PRE')
        self.assertEqual(A.street_of(_entry(AA, board=[1, 2, 3])), 'FLOP')
        self.assertEqual(A.street_of(_entry(AA, board=[1, 2, 3, 4])), 'TURN')
        self.assertEqual(A.street_of(_entry(AA, board=[1, 2, 3, 4, 5])), 'RIVER')

    def test_plan_from_decision(self):
        p = A.plan_from_decision({'recommended': 'raise', 'size': 3})
        self.assertEqual(p['action'], 'RAISE')
        self.assertIn('REQUIRES_SIZING_MULTISTEP', p['caveats'])
        self.assertEqual(A.plan_from_decision({'recommended': 'fold'})['action'], 'FOLD')
        self.assertIsNone(A.plan_from_decision({'recommended': None}))


class AntiThrash(unittest.TestCase):
    def test_uma_acao_por_mesa_mao_rua(self):
        calls = []
        emit = _emit(FakeAdvisor('raise', 3), armed=True,
                     execute=lambda plan, k, e: calls.append((k, plan['action'])))
        e = _entry(AA, tocall=100)
        emit('m', e)
        emit('m', e)                     # mesmo spot -> IGNORA
        self.assertEqual(calls, [('m', 'RAISE')])    # clicou UMA vez

    def test_refire_so_com_aposta_maior(self):
        calls = []
        emit = _emit(FakeAdvisor('call'), armed=True,
                     execute=lambda plan, k, e: calls.append(plan['action']))
        emit('m', _entry(AA, tocall=100))            # to_call 1bb
        emit('m', _entry(AA, tocall=150))            # 1.5bb <= 1+1 -> IGNORA
        emit('m', _entry(AA, tocall=400))            # 4bb > 1+1 -> re-age
        self.assertEqual(calls, ['CALL', 'CALL'])

    def test_nova_mao_reseta(self):
        calls = []
        emit = _emit(FakeAdvisor('raise', 3), armed=True,
                     execute=lambda plan, k, e: calls.append(tuple(e['players'][2]['cards'])))
        emit('m', _entry(AA, tocall=100))
        emit('m', _entry(KK, tocall=100))            # mão nova (cartas mudaram) -> age de novo
        self.assertEqual(len(calls), 2)


class Gate(unittest.TestCase):
    def test_dry_decide_mas_nao_clica(self):
        calls = []
        emit = _emit(FakeAdvisor('raise', 3), armed=False,      # DRY (PAUSED)
                     execute=lambda plan, k, e: calls.append(1))
        d = emit('m', _entry(AA))
        self.assertEqual(calls, [])                  # NÃO clicou
        self.assertEqual(d['plan']['action'], 'RAISE')   # mas decidiu/planejou
        self.assertFalse(d['fired'])

    def test_armado_clica(self):
        calls = []
        emit = _emit(FakeAdvisor('raise', 3), armed=True,
                     execute=lambda plan, k, e: calls.append(plan['action']))
        d = emit('m', _entry(AA))
        self.assertEqual(calls, ['RAISE'])
        self.assertTrue(d['fired'])

    def test_guarda_anticross_multi_mesa_nao_clica(self):
        # 2+ mesas vivas e SEM binding por tile -> não clica (nunca cruza mesa)
        calls = []
        c = BotControl(); c.resume()
        env = {'n_tables': 2}
        emit = A.make_table_emit(FakeAdvisor('call'), control=c, env=env, multi_bind=False,
                                 execute=lambda plan, k, e: calls.append(1), log=lambda *a, **k: None)
        d = emit('m', _entry(AA, tocall=200))
        self.assertEqual(calls, [])          # abstém do clique
        self.assertFalse(d['fired'])
        env['n_tables'] = 1                  # 1 mesa -> volta a clicar
        emit('m', _entry(KK, tocall=200))
        self.assertEqual(calls, [1])

    def test_abstain_hero_desconhecido_nao_age(self):
        # nenhum assento com 2 cartas -> build_table_state abstém -> sem plano, sem clique
        calls = []
        e = _entry(AA)
        e['players'][2]['cards'] = []                # hero perde as cartas -> ninguém com 2
        emit = _emit(FakeAdvisor('raise', 3), armed=True,
                     execute=lambda plan, k, ent: calls.append(1))
        d = emit('m', e)
        self.assertEqual(calls, [])
        self.assertIsNone(d['plan'])
        self.assertEqual(d['status'], 'ABSTAIN')


class GuardasEH2N(unittest.TestCase):
    class _Guards:
        def __init__(self, action): self.action = action
        def update(self, entry, key): return {'action': self.action, 'reason': 'x', 'roomid': key}

    class _Rec:
        def __init__(self): self.seen = []
        def observe_table(self, key, entry): self.seen.append(key)

    def _emit_g(self, *, guards=None, recorder=None, execute=None):
        c = BotControl(); c.resume()
        return A.make_table_emit(FakeAdvisor('call'), control=c, execute=execute,
                                 guards=guards, recorder=recorder, log=lambda *a, **k: None)

    def test_bust_para_a_mesa_e_nao_clica(self):
        fired = []
        emit = self._emit_g(guards=self._Guards('STOP'), execute=lambda *a: fired.append(1))
        d = emit('R1', _entry(AA))
        self.assertEqual(d['status'], 'GUARD_STOP')
        self.assertFalse(d['fired'])
        self.assertEqual(fired, [])                 # bust -> NUNCA clica

    def test_sitout_sinaliza_voltar(self):
        d = self._emit_g(guards=self._Guards('SITOUT_RETURN'))('R1', _entry(AA))
        self.assertEqual(d['status'], 'GUARD_SITOUT')

    def test_ok_segue_decidindo(self):
        d = self._emit_g(guards=self._Guards('OK'))('R1', _entry(AA))
        self.assertEqual(d['status'], 'ADVICE')     # guarda OK -> fluxo normal

    def test_recorder_observa_cada_mesa(self):
        r = self._Rec()
        self._emit_g(recorder=r)('R1', _entry(AA))
        self.assertEqual(r.seen, ['R1'])

    def test_guarda_que_explode_nao_quebra_o_emit(self):
        class Bad:
            def update(self, *a): raise RuntimeError('boom')
        d = self._emit_g(guards=Bad())('R1', _entry(AA))
        self.assertEqual(d['status'], 'ADVICE')     # falha na guarda -> segue decidindo (nunca lança)


class IntegracaoPackReal(unittest.TestCase):
    PACK = r'C:\Meus Projetos\Aplicativos\nvt-ranges-validados.json'
    CAPTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'research', 'ppp_il2cpp', 'estado_mesa_multitable_20261120.json')

    def test_run_once_captura_real_dry(self):
        if not (os.path.exists(self.PACK) and os.path.exists(self.CAPTURE)):
            self.skipTest('pack ou captura ausente')
        from pppoker_replay import load_capture
        calls = []
        emit = _emit(A._load_advisor(), armed=False,       # DRY
                     execute=lambda *a: calls.append(1))
        out = A.run_once(load_capture(self.CAPTURE), emit)
        self.assertEqual(len(out), 2)
        self.assertEqual(calls, [])                        # DRY: nunca clica


if __name__ == '__main__':
    unittest.main()
