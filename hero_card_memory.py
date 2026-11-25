"""Memória temporal das cartas do hero, por mão (imutáveis na mão).

PROBLEMA (medido ao vivo 13/11): o leitor de rank piscou AMBÍGUO ('5' vs 'J', 2x1)
num slot enquanto o outro lia — resultado HERO_CARDS_UNKNOWN. O cache antigo só
semeia quando UM frame lê AS DUAS cartas; se nenhum frame único lê as duas juntas
(cada frame falha num slot diferente), ele nunca semeia.

SOLUÇÃO: acumula, por (mesa, mão, slot), as leituras CONFIANTES de cada carta ao
longo dos frames e monta o par quando os dois slots têm leitura. Como a carta é
imutável na mão, somar evidência entre frames é seguro. VOTAÇÃO: exige `votes`
leituras concordando no mesmo card por slot antes de aceitar — uma leitura
pontual errada (ou ambígua=None) não envenena. NUNCA inventa: só entra
card_candidate não-nulo; ambíguo (None) é ignorado, não contado.

PURO: sem OCR, sem captura, sem clique, sem relógio. Só stdlib. O chamador passa os
candidatos por slot que já leu (ex.: `hero_slots` do advise_table)."""
from collections import OrderedDict, Counter


class HeroCardMemory:
    """Loja por (mesa, mão) com votação por slot. Limitada (LRU). Contadores de
    auditoria (quantos pares montados, slots em conflito)."""

    def __init__(self, limit=256, votes=2):
        self._limit = max(1, int(limit))
        self._votes = max(1, int(votes))
        self._store = OrderedDict()          # (table_key, hand_id) -> {'slots':[Counter,Counter], 'accepted':[card|None,card|None]}
        self.stats = dict(assembled=0, conflicts=0, ignored_ambiguous=0)

    @staticmethod
    def _key(table_key, hand_id):
        return (table_key, hand_id)

    def observe(self, table_key, hand_id, slot_candidates):
        """Registra os candidatos deste frame (lista de 2: card_candidate ou None).
        Conta um voto por slot que veio com leitura confiante; aceita o card quando
        atinge `votes` e é líder isolado. Retorna o par montado (ou None)."""
        if hand_id is None or not isinstance(slot_candidates, (list, tuple)) or len(slot_candidates) != 2:
            return self.pair(table_key, hand_id)
        key = self._key(table_key, hand_id)
        entry = self._store.get(key)
        if entry is None:
            entry = self._store[key] = dict(slots=[Counter(), Counter()], accepted=[None, None], assembled=False)
        self._store.move_to_end(key)
        for i, cand in enumerate(slot_candidates):
            if not cand:
                self.stats['ignored_ambiguous'] += 1
                continue
            if entry['accepted'][i] is not None:
                # já aceito (imutável): leitura divergente posterior é conflito, não troca.
                if cand != entry['accepted'][i]:
                    self.stats['conflicts'] += 1
                continue
            counter = entry['slots'][i]
            counter[cand] += 1
            top, top_n = counter.most_common(1)[0]
            runner_n = counter.most_common(2)[1][1] if len(counter) > 1 else 0
            if top_n >= self._votes and top_n > runner_n:
                entry['accepted'][i] = top
        pair = self.pair(table_key, hand_id)
        if pair is not None and not entry['assembled']:
            entry['assembled'] = True
            self.stats['assembled'] += 1
        while len(self._store) > self._limit:
            self._store.popitem(last=False)
        return pair

    def pair(self, table_key, hand_id):
        """Par [c0, c1] se os dois slots foram aceitos e são distintos; senão None."""
        entry = self._store.get(self._key(table_key, hand_id))
        if entry is None:
            return None
        c0, c1 = entry['accepted']
        if c0 and c1 and c0 != c1:
            return [c0, c1]
        return None

    def invalidate(self, table_key, hand_id=None):
        """Esquece uma mão, ou toda a mesa (hand_id=None)."""
        if hand_id is not None:
            self._store.pop(self._key(table_key, hand_id), None)
            return
        for key in [k for k in self._store if k[0] == table_key]:
            del self._store[key]

    def __len__(self):
        return len(self._store)
