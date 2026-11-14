"""Núcleo de DECISÃO do grind autônomo (E7 agenda por horário + E8 stop-loss/orçamento).

PURO e testável (relógio/estado injetados): decide O QUE registrar e QUANDO, e QUANDO
PARAR. NÃO clica, NÃO registra, NÃO descobre janelas — a execução (clique de
'Registrar'/'Entrar', handoff de HWND ao operador) é a camada AO VIVO (wiring do
runner E1, fora deste módulo e pendente de validação ao vivo).

Respeita a POLÍTICA DO PILOTO: sem late-registration (só registra ANTES do início),
sem re-entry/rebuy/add-on/seleção-substituta (todos [POL], fora daqui). Serve de
decisão para um futuro runner mestre que apenas COMPÕE isto com o ledger/seletor
existentes e o operar_mesa.
"""


def hhmm_to_min(s):
    """'HH:MM' -> minutos desde a meia-noite, ou None se inválido."""
    try:
        h, m = str(s).split(':')
        h, m = int(h), int(m)
    except (ValueError, AttributeError):
        return None
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    return h * 60 + m


class GrindPlanner:
    """Decisões de inscrição/parada do grind. Tudo em BB e minutos; sem efeitos
    colaterais. `reg_lead_min` = quanto antes do início a inscrição abre (janela de
    registro = [start-reg_lead, start)). Registrar em now>=start seria LATE-REG, que
    o piloto NÃO permite -> nunca retornado."""

    def __init__(self, *, max_simultaneous=4, max_per_day=None, daily_budget_bb=None,
                 stop_loss_bb=None, reg_lead_min=60):
        self.max_simultaneous = int(max_simultaneous)
        self.max_per_day = max_per_day
        self.daily_budget_bb = daily_budget_bb
        self.stop_loss_bb = stop_loss_bb
        self.reg_lead_min = int(reg_lead_min)

    def should_stop(self, *, spent_bb=0.0, pnl_bb=0.0):
        """Para de registrar novos torneios? (orçamento diário estourado OU stop-loss).
        Devolve (stop: bool, reason|None). pnl_bb negativo = perda acumulada."""
        if self.daily_budget_bb is not None and spent_bb >= self.daily_budget_bb:
            return True, 'ORCAMENTO_DIARIO_ATINGIDO'
        if self.stop_loss_bb is not None and pnl_bb <= -abs(self.stop_loss_bb):
            return True, 'STOP_LOSS_ATINGIDO'
        return False, None

    def _window_open(self, now_min, entry):
        start = entry.get('start_min')
        if start is None:
            start = hhmm_to_min(entry.get('start'))
        if start is None or not isinstance(now_min, (int, float)):
            return False
        opens = entry.get('reg_opens_min', start - self.reg_lead_min)
        return opens <= now_min < start          # [abre, início) — sem late-reg

    def due_to_register(self, now_min, grade, *, active=0, registered_ids=(),
                        registered_today=0, spent_bb=0.0, pnl_bb=0.0):
        """Torneios a registrar AGORA, em ordem de início. grade: lista de dicts
        {id, start_min|start, buyin_bb, reg_opens_min?}. Respeita: janela de registro
        aberta (sem late-reg), não já registrado, max_simultaneous (active+escolhidos),
        max_per_day e orçamento diário/stop-loss. NÃO escolhe substituto (piloto)."""
        stop, _ = self.should_stop(spent_bb=spent_bb, pnl_bb=pnl_bb)
        if stop:
            return []
        done = set(registered_ids or ())
        slots = max(0, self.max_simultaneous - int(active))
        day_left = (None if self.max_per_day is None
                    else max(0, self.max_per_day - int(registered_today)))
        budget_left = (None if self.daily_budget_bb is None
                       else max(0.0, self.daily_budget_bb - float(spent_bb)))
        chosen, spend = [], 0.0
        for e in sorted((g for g in grade if isinstance(g, dict)),
                        key=lambda g: (g.get('start_min') if g.get('start_min') is not None
                                       else (hhmm_to_min(g.get('start')) or 0))):
            if len(chosen) >= slots:
                break
            if day_left is not None and len(chosen) >= day_left:
                break
            if e.get('id') in done or not self._window_open(now_min, e):
                continue
            cost = float(e.get('buyin_bb') or 0.0)
            if budget_left is not None and spend + cost > budget_left:
                continue                         # não cabe no orçamento restante
            chosen.append(e)
            spend += cost
        return chosen
