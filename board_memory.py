"""Memória temporal do BOARD, por mão (imutável e monotônico na mão).

PROBLEMA (visto ao vivo 16/11): o board piscou — um frame leu ['3d','Td','7s','8s']
(turn) e o seguinte caiu para `BOARD_INCOMPLETE` com candidatos mas sem cartas
(-> abstenção BOARD_PRESENT_BUT_UNREADABLE). O leitor é stateless: reler o board
do zero a cada frame deixa uma falha pontual de OCR apagar o board já confirmado.

SOLUÇÃO (mesmo princípio do [[hero_card_memory]]): o board é IMUTÁVEL na mão e só
CRESCE (flop 3 -> turn 4 -> river 5). Acumula por (mesa, mão, POSIÇÃO) as leituras
confiantes de cada carta e aceita a carta quando `votes` frames concordam e é líder
isolado. Devolve o PREFIXO CONTÍGUO aceito — e só quando tem tamanho de board real
(3/4/5), nunca 1-2 (que não é street). Uma carta aceita é imutável (leitura
divergente depois = conflito, não troca). NUNCA inventa: carta None é ignorada.

PURO: sem OCR, sem captura, sem clique, sem relógio. Só stdlib. O chamador passa as
cartas do board que o frame leu (`board['cards']` do advise_table) e recebe o board
estável para preencher um frame em que a leitura falhou.
"""
from collections import OrderedDict, Counter

VALID_LEN = (3, 4, 5)
STREET_BY_LEN = {3: 'FLOP', 4: 'TURN', 5: 'RIVER'}


class BoardMemory:
    """Loja por (mesa, mão) com votação por posição, crescendo com a street.
    Limitada (LRU). Contadores de auditoria."""

    def __init__(self, limit=256, votes=2):
        self._limit = max(1, int(limit))
        self._votes = max(1, int(votes))
        self._store = OrderedDict()   # (table_key, hand_id) -> {'pos':[Counter,...], 'accepted':[card|None,...]}
        self.stats = dict(grown=0, conflicts=0, ignored=0)

    @staticmethod
    def _key(table_key, hand_id):
        return (table_key, hand_id)

    def observe(self, table_key, hand_id, cards):
        """Registra as cartas do board lidas neste frame (lista ordenada; pode ser
        parcial/vazia). Vota por posição; aceita a carta ao atingir `votes` sendo
        líder isolado. Retorna o board estável (prefixo contíguo aceito, 3/4/5)."""
        if hand_id is None:
            return self.board(table_key, hand_id)
        key = self._key(table_key, hand_id)
        entry = self._store.get(key)
        if entry is None:
            entry = self._store[key] = dict(pos=[], accepted=[])
        self._store.move_to_end(key)
        for i, card in enumerate(cards or []):
            if not card:
                self.stats['ignored'] += 1
                continue
            while len(entry['pos']) <= i:
                entry['pos'].append(Counter())
                entry['accepted'].append(None)
            if entry['accepted'][i] is not None:
                if card != entry['accepted'][i]:
                    self.stats['conflicts'] += 1     # imutável: divergência é conflito
                continue
            counter = entry['pos'][i]
            counter[card] += 1
            top, top_n = counter.most_common(1)[0]
            runner_n = counter.most_common(2)[1][1] if len(counter) > 1 else 0
            if top_n >= self._votes and top_n > runner_n:
                entry['accepted'][i] = top
                self.stats['grown'] += 1
        while len(self._store) > self._limit:
            self._store.popitem(last=False)
        return self.board(table_key, hand_id)

    def board(self, table_key, hand_id):
        """Prefixo contíguo aceito, só se for um board real (3/4/5 cartas); senão []."""
        entry = self._store.get(self._key(table_key, hand_id))
        if entry is None:
            return []
        out = []
        for c in entry['accepted']:
            if c is None:
                break                                # só contíguo a partir do 0
            out.append(c)
        return out if len(out) in VALID_LEN else []

    def invalidate(self, table_key, hand_id=None):
        """Esquece uma mão, ou toda a mesa (hand_id=None)."""
        if hand_id is not None:
            self._store.pop(self._key(table_key, hand_id), None)
            return
        for key in [k for k in self._store if k[0] == table_key]:
            del self._store[key]

    def __len__(self):
        return len(self._store)
