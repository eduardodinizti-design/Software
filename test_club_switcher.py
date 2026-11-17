"""Coordenador de troca de clube: idempotente, verifica pós-troca, fail-safe, gated.
Primitivas vivas (ler clube / executar troca) são FAKES aqui — lógica pura testável."""
import unittest

from bot_control import BotControl
from club_switcher import ClubSwitcher, normalize_club_name, same_club


class _FakeLobby:
    """Simula o lobby: tem um clube atual; trocar muda o estado. `broken` faz a troca
    não surtir efeito (p/ testar não-confirmação); `read_none` faz a leitura falhar."""
    def __init__(self, current, broken=False, read_none=False):
        self.current = current
        self.broken = broken
        self.read_none = read_none
        self.switch_calls = []
        self.read_calls = 0

    def read(self):
        self.read_calls += 1
        return None if self.read_none else self.current

    def switch(self, target):
        self.switch_calls.append(target)
        if not self.broken:
            self.current = target


class NormalizeTests(unittest.TestCase):
    def test_same_club_insensivel_a_caixa_e_espacos(self):
        self.assertTrue(same_club('AK Ahakha club2', '  ak ahakha  CLUB2 '))
        self.assertFalse(same_club('Karekas', 'Veneza'))

    def test_vazio_nunca_casa(self):
        self.assertFalse(same_club('', ''))
        self.assertEqual(normalize_club_name(None), '')


class EnsureClubTests(unittest.TestCase):
    def test_noop_quando_ja_no_clube(self):
        lob = _FakeLobby('Karekas')
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch)
        r = sw.ensure_club('karekas', dry_run=False)
        self.assertTrue(r['ok'])
        self.assertEqual(r['action'], 'NOOP_JA_NO_CLUBE')
        self.assertEqual(lob.switch_calls, [])            # NÃO clicou

    def test_dry_run_planeja_sem_executar(self):
        lob = _FakeLobby('Karekas')
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch)
        r = sw.ensure_club('AK Ahakha club2', dry_run=True)
        self.assertTrue(r['ok'])
        self.assertEqual(r['action'], 'PLANO_TROCAR')
        self.assertFalse(r['verified'])
        self.assertEqual(lob.switch_calls, [])            # dry-run não executa

    def test_club_desconhecido_bloqueia(self):
        lob = _FakeLobby('Karekas', read_none=True)
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch)
        r = sw.ensure_club('AK', dry_run=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['action'], 'CLUB_DESCONHECIDO')
        self.assertEqual(lob.switch_calls, [])            # não age às cegas

    def test_alvo_invalido(self):
        lob = _FakeLobby('Karekas')
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch)
        for bad in ('', '   ', None):
            self.assertEqual(sw.ensure_club(bad, dry_run=False)['action'], 'ALVO_INVALIDO')

    def test_troca_real_confirmada(self):
        lob = _FakeLobby('Karekas')
        ctrl = BotControl(); ctrl.resume()                # PAUSED->RUNNING
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch, bot_control=ctrl)
        r = sw.ensure_club('AK Ahakha club2', dry_run=False)
        self.assertTrue(r['ok'])
        self.assertEqual(r['action'], 'TROCADO')
        self.assertTrue(r['verified'])
        self.assertEqual(r['from_club'], 'Karekas')
        self.assertEqual(lob.switch_calls, ['AK Ahakha club2'])

    def test_gate_fechado_nao_executa(self):
        lob = _FakeLobby('Karekas')
        ctrl = BotControl()                               # default PAUSED
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch, bot_control=ctrl)
        r = sw.ensure_club('AK', dry_run=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['action'], 'GATE_FECHADO')
        self.assertEqual(lob.switch_calls, [])

    def test_sem_executor_bloqueia(self):
        lob = _FakeLobby('Karekas')
        sw = ClubSwitcher(read_current_club=lob.read)     # do_switch=None
        r = sw.ensure_club('AK', dry_run=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['action'], 'SEM_EXECUTOR')

    def test_troca_nao_confirmada_apos_tentativas(self):
        lob = _FakeLobby('Karekas', broken=True)          # switch não surte efeito
        ctrl = BotControl(); ctrl.resume()
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=lob.switch,
                          bot_control=ctrl, max_attempts=3)
        r = sw.ensure_club('AK', dry_run=False)
        self.assertFalse(r['ok'])
        self.assertEqual(r['action'], 'TROCA_NAO_CONFIRMADA')
        self.assertEqual(r['attempts'], 3)
        self.assertEqual(len(lob.switch_calls), 3)        # tentou 3x, não mentiu sucesso

    def test_executor_que_levanta_nao_quebra(self):
        lob = _FakeLobby('Karekas')
        def boom(_): raise RuntimeError('clique falhou')
        ctrl = BotControl(); ctrl.resume()
        sw = ClubSwitcher(read_current_club=lob.read, do_switch=boom,
                          bot_control=ctrl, max_attempts=2)
        r = sw.ensure_club('AK', dry_run=False)
        self.assertFalse(r['ok'])                         # não confirmou, mas não explodiu
        self.assertEqual(r['action'], 'TROCA_NAO_CONFIRMADA')


if __name__ == '__main__':
    unittest.main()
