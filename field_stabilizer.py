"""Memória temporal dos campos numéricos do leitor de mesa (observação; sem
captura, sem clique).

`read_table_state` é STATELESS: pot, to_call e stacks são re-derivados do OCR a
cada frame. Uma falha pontual de leitura num frame vira o valor JÁ confirmado em
`None` e força uma abstenção (POT_UNKNOWN / TO_CALL_UNKNOWN / STACK_UNKNOWN) mesmo
tendo acabado de ler o número. Dentro de UMA mão esses valores são estáveis ou
monotônicos (o pote só cresce; um stack só diminui quando compromete), então o
último valor confirmado é um preenchimento PRINCIPIADO de um buraco momentâneo —
a mesma ideia do `hero_override` para as cartas do hero ([[hero_card_memory]]) e
do `PositionStabilizer` para o dealer.

Este estabilizador segura o último `pot_bb`, `to_call_bb` e `stack_bb` por assento
por mesa, DENTRO da mesma mão, por no máximo `max_age` frames, e marca um valor
reusado com `held=True` e sua `age`. Uma MÃO NOVA (ou mesa nova) zera tudo — um
valor seguro NUNCA cruza a fronteira de mão (onde o pote legitimamente reseta e o
stack recarrega). Nunca sobrescreve um valor que o frame REALMENTE leu; só
preenche um `None`. Desconhecido continua desconhecido quando o hold expira.

Opt-in: `advise_table(..., field_memory=FieldStabilizer())`. Sem ele, nada muda.
"""

# Idade máxima do hold por campo (frames desde a última leitura confirmada).
# Pote é monotônico na mão -> hold mais longo é seguro (valor segurado é piso).
# to_call muda com a ação -> hold curto. Stack é ~constante na mão -> intermediário.
MAX_AGE = dict(pot=4, to_call=2, stack=3)


class _TableMem:
    __slots__ = ('hand', 'fields', 'seats')

    def __init__(self):
        self.hand = None
        self.fields = {}   # nome -> {'value', 'age'}
        self.seats = {}    # seat -> {'value', 'age'}


class FieldStabilizer:
    """Mantém o último valor legível de pot/to_call/stack por mesa e preenche
    buracos de 1+ frame DENTRO da mesma mão (fill-only, marcado como held)."""

    def __init__(self, *, max_age=None):
        self.max_age = dict(MAX_AGE, **(max_age or {}))
        self._tables = {}

    def _mem(self, table_key):
        m = self._tables.get(table_key)
        if m is None:
            m = self._tables[table_key] = _TableMem()
        return m

    def reset(self, table_key=None):
        if table_key is None:
            self._tables.clear()
        else:
            self._tables.pop(table_key, None)

    def _roll(self, slot, value, cap):
        """Decide o valor a emitir para um campo e atualiza sua memória.

        Devolve (emit_value, held, age). `slot` é o dict de memória do campo
        ({'value','age'}) ou None. Regra: leitura presente -> grava, age=0, não
        held. Ausente -> segura o último se existir e age<cap; senão expira."""
        if value is not None:
            slot['value'], slot['age'] = value, 0
            return value, False, 0
        if slot.get('value') is not None and slot['age'] < cap:
            slot['age'] += 1
            return slot['value'], True, slot['age']
        # expirou: esquece p/ não ressuscitar mais tarde no mesmo frame-gap longo
        slot['value'] = None
        return None, False, 0

    def apply(self, *, table_key, hand_key, state):
        """Recebe o `state` de `read_table_state` e devolve um novo `state` com
        pot/to_call/stacks preenchidos pela memória quando o frame leu `None`.

        `hand_key` é o sinal de troca: uma mão NOVA confirmada (hand_key != o
        guardado) zera a memória da mesa na hora — nada é herdado da mão anterior.
        hand_key None (ilegível) é tratado como a MESMA mão (não reseta), igual ao
        tracker/stabilizer. Só preenche; nunca sobrescreve leitura presente."""
        mem = self._mem(table_key)
        if hand_key is not None and mem.hand is not None and hand_key != mem.hand:
            mem.fields.clear()
            mem.seats.clear()
        if hand_key is not None:
            mem.hand = hand_key

        new_state = dict(state)

        # --- pot e to_call -------------------------------------------------
        for name, sub in (('pot', 'pot_bb'), ('to_call', 'to_call_bb')):
            field = dict(state.get(name) or {})
            cur = field.get(sub)
            slot = mem.fields.setdefault(name, {'value': None, 'age': 0})
            emit, held, age = self._roll(slot, cur, self.max_age[name])
            if held:
                conf = field.get('confidence')
                field = dict(field, **{sub: emit})
                field['confidence'] = conf if conf not in (None, 'abstain') else 'medium'
                field['source'] = 'held'
                field['held'] = True
                field['age'] = age
                new_state[name] = field
        # (quando não held, mantém o dict original intacto)

        # --- stacks por assento (só os ocupados; vazio não guarda) ---------
        seats = state.get('seats') or {}
        if seats:
            new_seats = dict(seats)
            cap = self.max_age['stack']
            for seat, sd in seats.items():
                if not sd.get('occupied'):
                    mem.seats.pop(seat, None)
                    continue
                slot = mem.seats.setdefault(seat, {'value': None, 'age': 0})
                emit, held, age = self._roll(slot, sd.get('stack_bb'), cap)
                if held:
                    nd = dict(sd, stack_bb=emit, source='held', held=True, age=age)
                    conf = sd.get('confidence')
                    nd['confidence'] = conf if conf not in (None, 'abstain') else 'medium'
                    new_seats[seat] = nd
            new_state['seats'] = new_seats

        return new_state
