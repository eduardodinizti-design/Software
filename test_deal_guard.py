"""Testes do deal-guard (trava de segurança p/ EvChop/deal)."""
from deal_guard import DealGuard, BLOCK_REASON


class _Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t
    def advance(self, s): self.t += s


def test_inactive_by_default():
    g = DealGuard()
    assert g.active() is False
    assert g.should_block_clicks() is False
    assert g.block_reason() is None


def test_evchop_info_arms_block():
    g = DealGuard()
    g.on_deal_event('EvChopInfoBRC')      # proposta de chop
    assert g.active() is True
    assert g.should_block_clicks() is True
    assert g.block_reason() == BLOCK_REASON


def test_evchop_over_releases():
    g = DealGuard()
    g.on_deal_event('EvChopInfoBRC')
    assert g.active()
    g.on_deal_event('EvChopOverBRC')      # chop encerrado/cancelado
    assert g.active() is False
    assert g.should_block_clicks() is False


def test_refuse_releases():
    g = DealGuard()
    g.on_deal_event('MttDivideRewardBRC')
    assert g.active()
    g.on_deal_event('PlayerRefuseDivideBRC')
    assert g.active() is False


def test_operation_keeps_active():
    g = DealGuard()
    g.on_deal_event('EvChopInfoBRC')
    g.on_deal_event('EvChopOperationBRC')  # alguém votou; ainda ativo
    assert g.active() is True


def test_failsafe_expira_apos_max():
    clk = _Clock()
    g = DealGuard(max_seconds=2100.0, clock=clk)
    g.on_deal_event('EvChopInfoBRC')
    assert g.active() is True
    clk.advance(2099)
    assert g.active() is True              # ainda dentro da janela
    clk.advance(2)                         # passou dos 2100s
    assert g.active() is False             # expirou sozinho (não trava pra sempre)


def test_clear_manual_humano_assumiu():
    g = DealGuard()
    g.on_deal_event('EvChopInfoBRC')
    g.clear()                              # humano assumiu o controle
    assert g.active() is False


def test_mensagens_irrelevantes_nao_armam():
    g = DealGuard()
    g.on_deal_event('MultipleTableHoleCardRSP')  # ruído do code-sharing
    assert g.active() is False


def test_seconds_active_tracks():
    clk = _Clock()
    g = DealGuard(clock=clk)
    assert g.seconds_active() is None
    g.on_deal_event('EvChopInfoBRC')
    clk.advance(45)
    assert g.seconds_active() == 45
