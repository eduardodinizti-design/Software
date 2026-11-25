"""A3 — escalonador por PRAZO das vezes do hero (anti-timeout multi-mesa).

Com várias mesas, servir em round-robin cego arrisca estourar o relógio de uma mesa
enquanto se decide outra. Este escalonador ordena as mesas com vez PENDENTE pela
URGÊNCIA: a que vence primeiro é servida primeiro.

Como não há (ainda) leitor do relógio de AÇÃO do hero, a urgência vem do PRAZO
EFETIVO, que unifica dois casos sem inventar número:
  - relógio lido (`seconds_left`): prazo efetivo = instante da leitura + seconds_left
    (o instante real do timeout, fixo no tempo);
  - relógio desconhecido: prazo efetivo = primeiro-avistamento + `default_budget`
    (heurística de agendamento, NÃO reportada como o relógio real — regra A0 de
    não fabricar prazo; só serve para ordenar).
Entre mesas de prazo desconhecido, a de espera mais LONGA (first_seen mais antigo)
vence — justiça + anti-timeout. Uma mesa nova com relógio curto PULA a fila.

PURO: sem OCR, sem captura, sem clique. `clock` injetável e `now` opcional nos
métodos -> determinístico em teste. Pensado para o loop do operador consumir quando
houver multi-mesa (hoje o loop é round-robin de 1 janela; wiring fica para então).
Ver [[nvt-adendo-antecipacao-a0]], [[nvt-mesas-projeto]] (meta multi-login)."""
import time


class DeadlineScheduler:
    def __init__(self, default_budget_s=12.0, clock=time.monotonic):
        self._budget = float(default_budget_s)
        self._clock = clock
        self._pending = {}        # table_key -> dict(first_seen, deadline|None)

    def _now(self, now):
        return self._clock() if now is None else now

    def observe(self, table_key, pending, now=None, seconds_left=None):
        """Registra o estado de uma mesa. `pending=True` garante que ela está na fila
        (grava first_seen na 1ª vez; atualiza o prazo se vier um `seconds_left` novo,
        sempre pegando o mais URGENTE). `pending=False` tira da fila."""
        now = self._now(now)
        if not pending:
            self._pending.pop(table_key, None)
            return
        entry = self._pending.get(table_key)
        if entry is None:
            entry = self._pending[table_key] = dict(first_seen=now, deadline=None)
        if seconds_left is not None and seconds_left >= 0:
            d = now + float(seconds_left)
            # mantém o prazo MAIS cedo já conhecido (o relógio só aperta; não relaxa)
            entry['deadline'] = d if entry['deadline'] is None else min(entry['deadline'], d)

    def served(self, table_key):
        """Mesa agida / não é mais a vez -> sai da fila."""
        self._pending.pop(table_key, None)

    def effective_deadline(self, table_key):
        """Instante efetivo de vencimento (real se lido; senão first_seen+orçamento).
        None se a mesa não está pendente."""
        entry = self._pending.get(table_key)
        if entry is None:
            return None
        if entry['deadline'] is not None:
            return entry['deadline']
        return entry['first_seen'] + self._budget

    def order(self, now=None):
        """Mesas pendentes da MAIS urgente para a menos (prazo efetivo crescente;
        empate -> first_seen mais antigo -> table_key)."""
        return [k for k, _ in sorted(
            self._pending.items(),
            key=lambda kv: (self.effective_deadline(kv[0]), kv[1]['first_seen'], kv[0]))]

    def next_due(self, now=None):
        """A mesa que deve ser servida primeiro, ou None se a fila está vazia."""
        order = self.order(now)
        return order[0] if order else None

    def pending_keys(self):
        return list(self._pending)

    def __len__(self):
        return len(self._pending)
