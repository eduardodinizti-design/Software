"""GUARDAS do PPPoker (Henrique) — decisões PURAS de BUST e SIT-OUT a partir do ESTADO
protobuf (o mesmo dict que o emitter grava em logs/estado_mesa.json / logs/live_seats.json).

NÃO clica, NÃO captura tela: estas funções só DECIDEM. Quem executa (clica Voltar / para a
mesa) é o agente (pppoker_agente), que chama estas guardas e age conforme a decisão. Módulo
PRÓPRIO do PPPoker — a Suprema tem o seu equivalente por VISÃO (suprema_bust/suprema_sitout),
mas aqui a percepção vem dos DADOS (protobuf), então a guarda é puramente lógica/testável.

LEIS do Eduardo respeitadas (alinhadas com suprema_sitout / busted_table):
  - NUNCA foldar para dar sit-out: a guarda de sit-out manda VOLTAR ('SITOUT_RETURN'),
    jamais desistir/foldar. [[nvt-regra-sitout-nunca-walk]]
  - BUST = PARAR aquela mesa ('STOP'); não reabrir sozinho. [[nvt-suprema-nao-matar-multitable]]
  - Conservador no bust: só declara BUST com SINAL CLARO; qualquer sinal de vida (herói com
    cartas / mão em andamento) VETA o bust (espírito de table_reading.busted_table).

FORMATO do estado (descoberto em protobuf_state / emitir_seats / captura de exemplo):
  estado = {
    "<roomid>": {"ts", "room", "table": {dealer, sbseat, bbseat, sb, board:[int], stage,
                                         tocall, pot}, "players": [player, ...],
                 "hero_cards_mt": [...]?},
    "_hero_turn": {...},        # metachaves começam com '_' -> ignoradas
  }
  player = {seat, uid, name, stack(_handChips), sit(_isSittingOut), bet(_betChips),
            act(_actionType), hascard, cards:[int,...]}
  - O HERÓI é o assento com 2 cartas FACE-UP decodificáveis (as únicas visíveis); seu `uid`
    pode ser APRENDIDO e reusado (robusto a showdown, quando vários revelam cartas).
  - sit (_isSittingOut) truthy = hero SIT-OUT.
"""
from __future__ import annotations

from ppp_cards import decode_cards

# metachaves do estado_mesa.json que NÃO são mesas (ex. "_hero_turn")
_META_PREFIX = "_"


def table_entry(estado, roomid):
    """Devolve a entry (dict com 'players'/'table') da mesa `roomid`, ou None.
    Tolerante: aceita o estado multitable {roomid: entry} ou uma entry solta."""
    if not isinstance(estado, dict):
        return None
    if "players" in estado:                     # já é uma entry solta
        return estado
    e = estado.get(str(roomid)) if roomid is not None else None
    if e is None and roomid is not None:
        e = estado.get(roomid)                  # tolera chave não-str
    return e if isinstance(e, dict) and "players" in e else None


def _players(entry):
    return [p for p in (entry.get("players") or []) if isinstance(p, dict)]


def _has_two_faceup(p):
    """True se o jogador tem 2 cartas FACE-UP decodificáveis (sinal do herói)."""
    return len(decode_cards(p.get("cards") or [])) == 2


def learn_hero_uid(estado, roomid=None):
    """Aprende o `uid` do herói a partir do assento com 2 cartas face-up (ÚNICO). Procura na
    mesa `roomid` se dada; senão varre todas as mesas. Devolve o uid (int) ou None se
    ambíguo (0 ou >1 candidatos -> não chuta). Reutiliza a mesma lógica de identidade do
    protobuf_state.hero_seat, mas devolvendo o uid (estável entre mãos/mesas)."""
    entries = []
    if roomid is not None:
        e = table_entry(estado, roomid)
        if e is not None:
            entries = [e]
    else:
        if isinstance(estado, dict) and "players" in estado:
            entries = [estado]
        elif isinstance(estado, dict):
            entries = [v for k, v in estado.items()
                       if not str(k).startswith(_META_PREFIX)
                       and isinstance(v, dict) and "players" in v]
    for e in entries:
        cand = [p for p in _players(e) if _has_two_faceup(p) and p.get("uid") is not None]
        if len(cand) == 1:
            return cand[0].get("uid")
    return None


def resolve_hero(entry, hero_uid=None):
    """Devolve o dict do jogador HERÓI na mesa, ou None se não der p/ identificar.
    Preferência: por `hero_uid` (DEFINITIVO, robusto a showdown); senão pelo assento único
    com 2 cartas face-up. None quando ambíguo/ausente — o chamador então ABSTÉM."""
    if entry is None:
        return None
    ps = _players(entry)
    if hero_uid is not None:
        for p in ps:
            if p.get("uid") == hero_uid:
                return p
        return None                             # uid conhecido e AUSENTE -> não está na mesa
    cand = [p for p in ps if _has_two_faceup(p)]
    return cand[0] if len(cand) == 1 else None


def _alive_signal(p):
    """Sinal de VIDA que VETA qualquer diagnóstico de bust: herói com cartas desta mão
    (hascard) ou com 2 cartas face-up. Espelha a trava de busted_table."""
    return bool(p.get("hascard")) or _has_two_faceup(p)


def detect_bust(estado, roomid, hero_uid=None):
    """True se o HERÓI foi ELIMINADO da mesa `roomid` — SÓ com sinal CLARO (conservador).

    Sinais de BUST aceitos:
      (1) `hero_uid` conhecido e AUSENTE dos jogadores da mesa -> assento removido = eliminado
          (é o caso "mesa bustada ainda aberta em modo observador"); OU
      (2) herói presente com stack <= 0 E SEM carta nesta mão (hascard falsy e sem face-up)
          -> fichas zeradas e fora da mão = eliminado (não é all-in, que teria hascard=1).

    VETO (nunca True): qualquer sinal de vida do herói (hascard / 2 cartas face-up) = ALL-IN
    ou mão em andamento. AMBÍGUO (herói não identificável: sem uid e sem 2 cartas únicas) ->
    False (não dá p/ afirmar bust sem saber quem é o herói). Devolve bool."""
    entry = table_entry(estado, roomid)
    if entry is None:
        # mesa sumiu do estado: sem uid não dá p/ afirmar que foi o herói que caiu.
        return False
    ps = _players(entry)
    if hero_uid is not None:
        hero = next((p for p in ps if p.get("uid") == hero_uid), None)
        if hero is None:
            return len(ps) > 0                  # mesa viva, herói sumiu -> eliminado
        if _alive_signal(hero):
            return False                        # all-in / na mão -> VIVO
        stack = hero.get("stack")
        return isinstance(stack, (int, float)) and stack <= 0
    # sem uid: só pelo assento único com 2 cartas face-up (= VIVO por definição) -> nunca bust.
    hero = resolve_hero(entry)
    if hero is None:
        return False                            # ambíguo -> conservador
    return False                                # tem 2 cartas face-up = está vivo nesta mão


def detect_sitout(estado, roomid, hero_uid=None):
    """True se o HERÓI está em SIT-OUT na mesa `roomid` (flag _isSittingOut truthy).
    Precisa identificar o herói (por uid ou 2 cartas face-up); se não identificar, False
    (não chuta). Bust tem precedência lógica no guard_decision; aqui só o flag de sit."""
    entry = table_entry(estado, roomid)
    if entry is None:
        return False
    hero = resolve_hero(entry, hero_uid)
    if hero is None:
        return False
    return bool(hero.get("sit"))


def guard_decision(estado, roomid, hero_uid=None):
    """DECISÃO da guarda para a mesa `roomid`. Devolve dict:
        {'action': 'STOP'|'SITOUT_RETURN'|'OK', 'reason': str, 'roomid': str}

      - 'STOP'          : herói bustou -> PARAR aquela mesa (não reabrir sozinho).
      - 'SITOUT_RETURN' : herói em sit-out -> VOLTAR (clicar reentrada); JAMAIS foldar p/ walk.
      - 'OK'            : nada a fazer (jogando normal / estado não identificável).

    Precedência: BUST > SIT-OUT > OK (se bustou, não adianta voltar). Pura/determinística."""
    rid = str(roomid)
    if detect_bust(estado, roomid, hero_uid):
        return {"action": "STOP", "reason": "BUST", "roomid": rid}
    if detect_sitout(estado, roomid, hero_uid):
        return {"action": "SITOUT_RETURN", "reason": "SITOUT", "roomid": rid}
    return {"action": "OK", "reason": "ALIVE", "roomid": rid}


class GuardMonitor:
    """Camada OPCIONAL com estado: aprende o `hero_uid` conforme as cartas aparecem e aplica
    DEBOUNCE no bust (N frames BUST seguidos) p/ um frame parcial do emitter não parar a mesa
    por engano. Reusa table_reading.busted_table.BustedConfirmer (mesma disciplina da Suprema).

    Uso pelo agente (por tick, com o estado já lido):
        mon = GuardMonitor(need=3)
        for roomid in mesas:
            dec = mon.update(estado, roomid)   # {'action', 'reason', 'roomid'}
            if dec['action'] == 'STOP': ...     # parar/fechar aquela mesa (1x)
            elif dec['action'] == 'SITOUT_RETURN': ...  # clicar Voltar
    Sit-out NÃO tem debounce (voltar quanto antes é seguro e idempotente); só o bust debouce."""

    def __init__(self, need: int = 3, hero_uid=None):
        from table_reading.busted_table import BustedConfirmer
        self.hero_uid = hero_uid
        self._conf = BustedConfirmer(need=need)

    def _ensure_uid(self, estado, roomid):
        if self.hero_uid is None:
            uid = learn_hero_uid(estado, roomid)
            if uid is None:
                uid = learn_hero_uid(estado)        # qualquer mesa (uid é o mesmo em todas)
            if uid is not None:
                self.hero_uid = uid
        return self.hero_uid

    def update(self, estado, roomid):
        """Alimenta um frame p/ a mesa `roomid` e devolve a decisão JÁ debounced no bust.
        Enquanto o bust não confirma `need` vezes seguidas, o STOP não é emitido (fica OK/sit)."""
        uid = self._ensure_uid(estado, roomid)
        rid = str(roomid)
        is_bust = detect_bust(estado, roomid, uid)
        det = {"status": "BUSTED"} if is_bust else {"status": "ALIVE"}
        if self._conf.update(rid, det):             # confirmou (N seguidas) e ainda não tratado
            self._conf.mark_done(rid)
            return {"action": "STOP", "reason": "BUST", "roomid": rid}
        if self._conf.is_done(rid):
            return {"action": "STOP", "reason": "BUST_DONE", "roomid": rid}
        if detect_sitout(estado, roomid, uid):
            return {"action": "SITOUT_RETURN", "reason": "SITOUT", "roomid": rid}
        return {"action": "OK", "reason": "ALIVE", "roomid": rid}
