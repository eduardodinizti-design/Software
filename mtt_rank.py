"""Percepção de MESA FINAL / fase de torneio a partir do MttMyRankInfoBRC do PPPoker
(capturado ao vivo via IL2CPP — ver NVT-Mesas-src/research/ppp_il2cpp/FINDINGS_HANDS.md).

Transforma os campos crus do broadcast num estado que o cérebro usa p/ ICM/bolha:
quantos faltam pra FT, se é bolha, se já está na mesa final, heads-up, etc.

Uso:
    info = MttRankInfo.from_fields(rank=3, itm_player_num=9, total_player_num=58,
                                   alive_player_num=8, current_reward_ppcoins=14640)
    info.phase          -> 'final_table'
    info.players_to_ft  -> 0
    info.on_bubble      -> False
    info.itm            -> True

Offsets crus (p/ o leitor Frida preencher): rank_@28, itmPlayerNum_@32,
totalPlayerNum_@36, currentRewardPpcoins_@40, currentRewardTicketPrice_@48,
currentRewardItemPrice_@56, alivePlayerNum_@64, satelliteRemainingTicketNum_@72,
targetStackAchievedPlayerNum_@80.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

# Tamanho padrão da mesa final no PPPoker (9-max; alguns formatos 8-max).
DEFAULT_FT_SIZE = 9

# Fases (ordem do torneio).
PHASE_EARLY = 'early'            # longe do dinheiro
PHASE_NEAR_MONEY = 'near_money'  # aproximando da bolha
PHASE_BUBBLE = 'bubble'          # bolha (1 bust = dinheiro)
PHASE_ITM = 'itm'               # no dinheiro, ainda multi-mesa
PHASE_FINAL_TABLE = 'final_table'  # mesa final formada
PHASE_FT_SHORT = 'ft_short'      # FT curta (<=4 vivos)
PHASE_HEADS_UP = 'heads_up'      # mano a mano
PHASE_WINNER = 'winner'          # acabou (1 vivo)
PHASE_UNKNOWN = 'unknown'


@dataclass
class MttRankInfo:
    rank: int = 0
    itm_player_num: int = 0
    total_player_num: int = 0
    alive_player_num: int = 0
    current_reward_ppcoins: int = 0
    current_reward_ticket_price: int = 0
    current_reward_item_price: int = 0
    satellite_remaining_ticket_num: int = 0
    target_stack_achieved_player_num: int = 0
    ft_size: int = DEFAULT_FT_SIZE

    @classmethod
    def from_fields(cls, *, rank=0, itm_player_num=0, total_player_num=0,
                    alive_player_num=0, current_reward_ppcoins=0,
                    current_reward_ticket_price=0, current_reward_item_price=0,
                    satellite_remaining_ticket_num=0,
                    target_stack_achieved_player_num=0, ft_size=DEFAULT_FT_SIZE):
        return cls(
            rank=int(rank or 0), itm_player_num=int(itm_player_num or 0),
            total_player_num=int(total_player_num or 0),
            alive_player_num=int(alive_player_num or 0),
            current_reward_ppcoins=int(current_reward_ppcoins or 0),
            current_reward_ticket_price=int(current_reward_ticket_price or 0),
            current_reward_item_price=int(current_reward_item_price or 0),
            satellite_remaining_ticket_num=int(satellite_remaining_ticket_num or 0),
            target_stack_achieved_player_num=int(target_stack_achieved_player_num or 0),
            ft_size=int(ft_size or DEFAULT_FT_SIZE),
        )

    # ---- derivados ----
    @property
    def alive(self) -> int:
        return self.alive_player_num

    @property
    def itm(self) -> bool:
        """Já garantiu dinheiro (vivos <= lugares pagos)."""
        return self.itm_player_num > 0 and self.alive_player_num <= self.itm_player_num

    @property
    def players_to_bubble(self) -> Optional[int]:
        """Quantos bustam até estourar a bolha (chegar ao dinheiro). 0 = bolha estourou."""
        if not self.itm_player_num or not self.alive_player_num:
            return None
        return max(0, self.alive_player_num - self.itm_player_num)

    @property
    def players_to_ft(self) -> Optional[int]:
        """Quantos faltam bustar pra formar a mesa final. 0 = já na FT."""
        if not self.alive_player_num:
            return None
        return max(0, self.alive_player_num - self.ft_size)

    @property
    def on_bubble(self) -> bool:
        """Bolha dura: exatamente 1 jogador a mais que os pagos, ainda fora do dinheiro."""
        ptb = self.players_to_bubble
        return ptb is not None and ptb == 1

    @property
    def at_final_table(self) -> bool:
        return self.alive_player_num > 0 and self.alive_player_num <= self.ft_size

    @property
    def has_reward(self) -> bool:
        return (self.current_reward_ppcoins > 0 or self.current_reward_ticket_price > 0
                or self.current_reward_item_price > 0)

    @property
    def phase(self) -> str:
        a = self.alive_player_num
        if a <= 0:
            return PHASE_UNKNOWN
        if a == 1:
            return PHASE_WINNER
        if a == 2:
            return PHASE_HEADS_UP
        if a <= 4:
            return PHASE_FT_SHORT
        if a <= self.ft_size:
            return PHASE_FINAL_TABLE
        # multi-mesa:
        ptb = self.players_to_bubble
        if ptb is not None:
            if ptb <= 0:
                return PHASE_ITM          # no dinheiro, ainda multi-mesa
            if ptb <= 1:
                return PHASE_BUBBLE
            if ptb <= max(3, self.itm_player_num // 5 + 1):
                return PHASE_NEAR_MONEY
        return PHASE_EARLY

    def summary(self) -> str:
        parts = [f"fase={self.phase}", f"vivos={self.alive_player_num}",
                 f"rank={self.rank}", f"itm={self.itm_player_num}",
                 f"total={self.total_player_num}"]
        if self.players_to_ft:
            parts.append(f"faltam_FT={self.players_to_ft}")
        if self.players_to_bubble:
            parts.append(f"ate_bolha={self.players_to_bubble}")
        if self.has_reward:
            parts.append(f"premio={self.current_reward_ppcoins}")
        return "  ".join(parts)
