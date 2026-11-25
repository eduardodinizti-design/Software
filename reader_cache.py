"""Cache de leituras ESTÁTICAS por mesa (HUD VIP e bounty PKO).

Motivação (avaliação do outro agente, 12/11): o leitor de HUD é CARO (~1s p/ 8
assentos: busca + template matching), e rodá-lo a cada frame no loop round-robin
estoura a latência (a última mesa do ciclo pode perder o time bank). Mas os stats do
HUD são ESTÁTICOS por vilão e o bounty só muda em KO — então o certo NÃO é reler a
cada frame nem confirmar em 3 frames (3× pior), e sim CACHEAR: ler 1× e reusar,
refrescando numa cadência lenta ou quando a OCUPAÇÃO do assento muda (novo jogador).

Também mitiga o risco de animação (fichas deslizando): a leitura cara acontece em 1 a
cada N frames, então um frame no meio de animação raramente é o lido, e o merge nunca
sobrescreve um valor bom por uma abstenção.
"""


def _default_hud_fn(crop, seats):
    from table_reading.hud_reader import read_seat_huds
    return read_seat_huds(crop, seats)


def _default_bounty_fn(crop, seats):
    from table_reading.bounty import read_seat_bounties
    return {s: v['value'] for s, v in read_seat_bounties(crop, seats=seats).items()
            if v.get('value') is not None}


class ReaderCache:
    """Estado por mesa. `huds`/`bounties` devolvem o cache, relendo só a cada N frames
    ou quando falta um assento ocupado (primeira vez / novo jogador). Funções de leitor
    injetáveis (`hud_fn`/`bounty_fn`) p/ teste; padrão = os leitores reais (lazy)."""

    def __init__(self, hud_every=24, bounty_every=12, hud_fn=None, bounty_fn=None):
        self.hud_every = max(1, int(hud_every))
        self.bounty_every = max(1, int(bounty_every))
        self._hud_fn = hud_fn or _default_hud_fn
        self._bounty_fn = bounty_fn or _default_bounty_fn
        self._hud = {}       # table_key -> {seat: read}
        self._bounty = {}    # table_key -> {seat: value}
        self._hc = {}        # table_key -> contador de frames (hud)
        self._bc = {}        # table_key -> contador (bounty)
        self._occ = {}       # table_key -> último conjunto de ocupados
        self._hud_age = {}   # table_key -> {seat: refreshes desde a última leitura OK (#A7)}
        self._bounty_age = {}  # table_key -> {seat: refreshes desde o último bounty OK (#A7)}

    def _invalidate(self, table_key, occupied):
        now = set(occupied)
        prev = self._occ.get(table_key)
        if prev is not None and prev != now:
            for seat in prev ^ now:                       # entrou/saiu -> possível novo jogador
                self._hud.get(table_key, {}).pop(seat, None)
                self._bounty.get(table_key, {}).pop(seat, None)
                self._hud_age.get(table_key, {}).pop(seat, None)
                self._bounty_age.get(table_key, {}).pop(seat, None)
        self._occ[table_key] = now

    def huds(self, crop, table_key, occupied_seats):
        self._invalidate(table_key, occupied_seats)
        cache = self._hud.setdefault(table_key, {})
        age = self._hud_age.setdefault(table_key, {})
        want = [s for s in occupied_seats if s != 'hero']
        n = self._hc.get(table_key, 0)
        self._hc[table_key] = n + 1
        if n % self.hud_every == 0 or any(s not in cache for s in want):
            fresh = self._hud_fn(crop, want)
            cache.update(fresh)                           # merge: abstidos mantêm o antigo valor
            # Idade (#A7): assento relido com sucesso zera; refresh TENTADO e falho (abstido)
            # envelhece o valor cacheado. Reuso ENTRE refreshes (cadência não disparou) não
            # envelhece — o valor segue confirmado da última leitura boa. Expor a idade deixa
            # o exploit bloquear leitura não-reconfirmada em vez de tratá-la como fresca.
            for s in want:
                if s in fresh:
                    age[s] = 0
                elif s in cache:
                    age[s] = age.get(s, 0) + 1
        # Cópia anotada com a idade; não muta o cache.
        return {s: {**cache[s], '_age': age.get(s, 0)} for s in want if s in cache}

    def bounties(self, crop, table_key, occupied_seats):
        self._invalidate(table_key, occupied_seats)
        cache = self._bounty.setdefault(table_key, {})
        age = self._bounty_age.setdefault(table_key, {})
        n = self._bc.get(table_key, 0)
        self._bc[table_key] = n + 1
        if n % self.bounty_every == 0 or any(s not in cache for s in occupied_seats):
            fresh = self._bounty_fn(crop, occupied_seats)
            for seat in occupied_seats:
                val = fresh.get(seat)
                if val is not None:
                    cache[seat] = val                     # mantém o bom; não zera por None
                    age[seat] = 0
                elif seat in cache:
                    age[seat] = age.get(seat, 0) + 1      # refresh TENTADO e falho: envelhece
        # Só serve bounties CONFIRMADOS (idade 0). Bounty muda por KO sem mudar a ocupação
        # do assento; um refresh que falhou (KO/animação/OCR) NÃO alimenta o overlay de
        # call-off como se fosse atual (#A7). O valor fica no cache p/ continuidade e volta
        # a ser servido quando reconfirmar. Reuso ENTRE refreshes (cadência não disparou)
        # segue servido: foi confirmado na última leitura boa.
        return {s: cache[s] for s in occupied_seats if s in cache and age.get(s, 0) == 0}
