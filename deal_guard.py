"""DEAL-GUARD: trava de SEGURANÇA p/ propostas de DEAL/CHOP (EvChop) na mesa.

Quando há um deal/chop ativo (modal "Aceitar/Rejeitar" cobre a mesa), o operador NÃO pode
clicar em NADA — qualquer clique às cegas pode aceitar/rejeitar o deal (decisão de dinheiro)
ou acertar um botão errado. Este guard, alimentado pela detecção READ-ONLY do EvChop
(ver alerta_ft.js / hook_deal.js), diz ao operador: ABSTENHA-SE e entregue pro humano.

Eventos (classe da mensagem Pb, como vem do hook):
  proposta/vivo : EvChopInfoBRC, EvChopOperationBRC/RSP, MttDivideRewardBRC, HostDivideReward*
  fim/encerra   : EvChopOverBRC, *Refuse*, *Cancel*  -> libera

Failsafe: se perdermos o evento de fim, o guard EXPIRA sozinho após `max_seconds`
(default 2100s = 35 min, um pouco acima da janela de 30 min do deal) p/ não travar o bot
pra sempre. Também há limpeza manual (human assumiu o controle).
"""
from __future__ import annotations
import time

_ALIVE_RE = ('evchopinfo', 'evchopoperation', 'dividereward', 'hostdividereward', 'playervotedivide')
_END_RE = ('over', 'refuse', 'cancel')

BLOCK_REASON = 'DEAL_ATIVO_AGUARDA_HUMANO'
DEFAULT_MAX_SECONDS = 2100.0   # 35 min (janela do deal é ~30 min)


class DealGuard:
    def __init__(self, *, max_seconds=DEFAULT_MAX_SECONDS, clock=time.monotonic):
        self._max = float(max_seconds)
        self._clock = clock
        self._since = None          # timestamp em que o deal ficou ativo (None = inativo)
        self._last_msg = None

    # ---- alimentação pela detecção read-only ----
    def on_deal_event(self, msg_class: str):
        """Recebe a CLASSE da mensagem de deal (ex. 'EvChopInfoBRC'). Arma ou libera."""
        cn = (msg_class or '').lower()
        self._last_msg = msg_class
        if any(t in cn for t in _END_RE):
            self.clear()
            return
        if any(t in cn for t in _ALIVE_RE):
            if self._since is None:
                self._since = self._clock()

    def clear(self):
        """Libera (deal encerrado, ou humano assumiu o controle)."""
        self._since = None

    # ---- consulta pelo operador ----
    def active(self) -> bool:
        if self._since is None:
            return False
        if (self._clock() - self._since) >= self._max:   # failsafe: expira
            self._since = None
            return False
        return True

    def should_block_clicks(self) -> bool:
        """True = operador deve ABSTER-SE de qualquer clique nesta mesa."""
        return self.active()

    def block_reason(self):
        return BLOCK_REASON if self.active() else None

    @property
    def last_message(self):
        return self._last_msg

    def seconds_active(self):
        return None if self._since is None else (self._clock() - self._since)
