"""Robustez do operador p/ sessões de HORAS (puro: não lê tela, não clica).

Fecha dois gaps de estabilidade do loop (ver BACKLOG_GAPS.txt D2/D3):
- D3: estado por table_key (raise_done, tourneys_closed) crescia SEM LIMITE -> com
  rotação de mesas (balanceamento MTT) vira vazamento de memória lento. BoundedKeySet
  é um conjunto LRU com teto.
- D2: janela morta / captura None ficava em SILÊNCIO indefinido. CaptureWatch conta
  falhas CONSECUTIVAS por hwnd e sinaliza quando a janela parece morta (telemetria;
  nunca altera clique/decisão).
"""
from collections import OrderedDict


class BoundedKeySet:
    """Conjunto com limite LRU: suporta `add(key)` e `key in s` (mesma interface de
    set usada por raise_done/tourneys_closed). Ao exceder `maxlen`, descarta a chave
    MENOS recente. Reacessar/readicionar renova a idade (move_to_end)."""

    def __init__(self, maxlen=2048):
        if maxlen < 1:
            raise ValueError('maxlen deve ser >= 1')
        self.maxlen = maxlen
        self._d = OrderedDict()

    def add(self, key):
        if key in self._d:
            self._d.move_to_end(key)
        else:
            self._d[key] = True
            if len(self._d) > self.maxlen:
                self._d.popitem(last=False)   # descarta o mais antigo

    def discard(self, key):
        self._d.pop(key, None)

    def __contains__(self, key):
        if key in self._d:
            self._d.move_to_end(key)          # uso conta como recência
            return True
        return False

    def __len__(self):
        return len(self._d)


class CaptureWatch:
    """Vigia de captura por janela. `fail(hwnd)` conta falhas CONSECUTIVAS (frame None
    ou erro de captura) e devolve (contagem, alertar?). `ok(hwnd)` zera (captura voltou).
    Evita o silêncio indefinido de uma janela morta sem mexer em nenhuma ação."""

    def __init__(self, alert_after=5, repeat=30):
        if alert_after < 1 or repeat < 1:
            raise ValueError('alert_after e repeat devem ser >= 1')
        self.alert_after = alert_after
        self.repeat = repeat
        self._fails = {}

    def ok(self, hwnd):
        self._fails.pop(hwnd, None)

    def fail(self, hwnd):
        c = self._fails.get(hwnd, 0) + 1
        self._fails[hwnd] = c
        alert = c == self.alert_after or (c > self.alert_after
                                          and (c - self.alert_after) % self.repeat == 0)
        return c, alert

    def consecutive(self, hwnd):
        return self._fails.get(hwnd, 0)


MAX_RAISE_ATTEMPTS = 2   # tentativa original + 1 re-tentativa (exposição limitada)


def raise_outcome(res, attempts, *, max_attempts=MAX_RAISE_ATTEMPTS):
    """D4: classifica o resultado do RaiseSequencer p/ o loop, SEM risco de duplo-raise.

    INVARIANTE DE SEGURANÇA (verificada no raise_sequencer): res['ok']=True se e só se
    o clique de CONFIRMAR saiu -> a aposta FOI submetida (mesmo que o efeito só não
    tenha sido verificado). ok=False cobre _unknown ('confirmar não saiu') e _fail
    (falha antes do confirmar): NADA foi submetido. Como o passo 0 do sequenciador
    revalida a vez do hero antes de qualquer clique, uma RE-TENTATIVA (próximo ciclo,
    turno-gated) não pode duplicar uma aposta já submetida.

    Devolve (decision, attempts): 'done' (submetida/não re-tenta) | 'retry' (nada
    submetido, tenta de novo) | 'giveup' (atingiu o cap -> desiste, não trava)."""
    res = res or {}
    if res.get('ok'):
        return 'done', 0
    attempts = int(attempts) + 1
    if attempts >= max_attempts:
        return 'giveup', attempts
    return 'retry', attempts


def reconcile_targets(current_hwnds, discovered, *, allow=None, max_targets=12):
    """D1: re-descoberta de mesas p/ sessões de horas (balanceamento MTT abre mesas
    em HWNDs NOVOS; a mesa antiga fecha). Dado os HWNDs operados agora e as janelas
    DESCOBERTAS (lista de dicts com 'hwnd'...), devolve (to_add, to_drop, by_hwnd):
      to_add  : HWNDs descobertos ainda não operados (mesas novas) — respeita `allow`
                (allowlist opcional; None = aceita qualquer janela do cliente) e o teto
                `max_targets` (não adiciona além do limite).
      to_drop : HWNDs operados que SUMIRAM da descoberta (mesa fechada) — remover do
                round-robin p/ não girar em janela morta.
      by_hwnd : índice {hwnd: janela} da descoberta (p/ a geometria da nova mesa).
    Puro/determinístico: não descobre nem captura; recebe a descoberta pronta."""
    by_hwnd = {w['hwnd']: w for w in (discovered or [])
               if isinstance(w, dict) and 'hwnd' in w}
    cur = list(current_hwnds or [])
    cur_set = set(cur)
    drop = [h for h in cur if h not in by_hwnd]
    kept = len(cur_set) - len(drop)
    add = []
    for h in by_hwnd:
        if h in cur_set:
            continue
        if allow is not None and h not in allow:
            continue
        if kept + len(add) >= max_targets:
            break
        add.append(h)
    return add, drop, by_hwnd
