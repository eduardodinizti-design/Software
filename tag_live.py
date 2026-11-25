"""MARCAÇÃO AO VIVO + ponte TAG->decisão em SOMBRA — [[nvt-exploit-anti-bot-pppoker]].

(a) Durante o grind o Eduardo MARCA um jogador (por assento OU uid) com uma etiqueta. O
    assento->uid vem do emissor (logs/live_seats_rich.json). A marcação grava no `player_tags`
    (persistente). `cycle_seat` percorre as tags (p/ clicar e ciclar). `hit_seat` mapeia uma
    coordenada de clique -> assento (o overlay visual passa as caixas; o clique real pluga lá).
(b) `annotate_hud` anexa a cada assento do HUD a TAG manual + o PLANO + a SUGESTÃO automática;
    `attach_shadow` pendura em `advice['tag_plan_shadow']` o que o plano FARIA por vilão taggeado.
    SOMBRA: observável, NÃO troca o `recommended` (igual aos solver_shadow). Arma só após homologar.

Puro: não desenha, não clica, não lê tela. Lê o feed (JSON) e grava tags.
"""
from __future__ import annotations

import json
import os

from player_tags import TagStore
from tag_plan import canonical, plan_for_tag

_REPO = os.path.dirname(os.path.abspath(__file__))
_RICH = os.path.join(_REPO, 'logs', 'live_seats_rich.json')

# ordem do ciclo ao clicar/ciclar; depois da última volta ao "sem tag" (remove)
CYCLE = ('bote', 'station', 'bom', 'nvt')


# ---------------- (b) anotação do HUD + sombra no advice ----------------
def annotate_hud(hud, store):
    """Enriquece cada entry do HUD que tenha `_uid`: adiciona `tag` (manual), `tag_plan`
    (plano da tag) e `bot_suggestion` (auto, se os stats trouxerem limp_reraise e o uid
    AINDA não estiver marcado como bote). Muta e devolve o próprio `hud`. Seguro: sem store
    ou sem _uid, não faz nada."""
    if not hud or store is None:
        return hud
    for entry in hud.values():
        if not isinstance(entry, dict):
            continue
        uid = entry.get('_uid')
        if uid is None:
            continue
        tag = store.tag_of(uid)
        if tag:
            entry['tag'] = tag
            entry['tag_plan'] = plan_for_tag(tag)
        stats = entry.get('stats')
        if isinstance(stats, dict) and stats.get('limp_reraise') is not None:
            from bot_exploit import detect_bot
            sug = detect_bot(stats)
            if sug.get('is_bot_suspect') and canonical(tag) != 'bote':
                entry['bot_suggestion'] = sug
    return hud


def attach_shadow(advice, hud):
    """Pendura `advice['tag_plan_shadow']` = {seat: {uid, tag, label, aggression, apply,
    actionable}} p/ cada assento com tag manual, + `suggestions` p/ assentos que a auto-
    detecção sugere marcar. SOMBRA pura: não altera `recommended`. No-op se nada a dizer."""
    if not isinstance(advice, dict) or not hud:
        return advice
    seats, sugg = {}, {}
    for seat, entry in hud.items():
        if not isinstance(entry, dict):
            continue
        plan = entry.get('tag_plan')
        if plan:
            seats[seat] = dict(uid=entry.get('_uid'), tag=plan.get('tag'),
                               label=plan.get('label'), aggression=plan.get('aggression'),
                               apply=plan.get('apply'), hostile=plan.get('hostile', False),
                               actionable=bool(plan.get('apply')))
        if entry.get('bot_suggestion'):
            sugg[seat] = dict(uid=entry.get('_uid'),
                              confidence=entry['bot_suggestion'].get('confidence'),
                              reasons=entry['bot_suggestion'].get('reasons'),
                              suggest_tag='bote')
    if seats or sugg:
        advice['tag_plan_shadow'] = dict(seats=seats, suggestions=sugg, validated=False)
    return advice


# ---------------- (a) marcação ao vivo (por assento / uid) ----------------
class TagLive:
    """Marca jogadores no grind. `rich` = conteúdo de live_seats_rich.json
    ({ref:{room,players:[{seat,uid,name,...}]}}); `store` = TagStore."""

    def __init__(self, store, rich=None):
        self.store = store
        self.rich = rich or {}

    @classmethod
    def load(cls, *, tags_path=None, rich_path=_RICH):
        store = TagStore.load(tags_path) if tags_path else TagStore.load()
        try:
            with open(rich_path, encoding='utf-8') as fh:
                rich = json.load(fh)
        except (OSError, ValueError):
            rich = {}
        return cls(store, rich if isinstance(rich, dict) else {})

    def _players(self, table_ref=None):
        if table_ref is not None:
            info = self.rich.get(str(table_ref)) or {}
            return info.get('players', []) or []
        out = []
        for info in self.rich.values():
            out += (info or {}).get('players', []) or []
        return out

    def uid_at(self, seat, table_ref=None):
        """uid sentado no assento (str) ou None."""
        for p in self._players(table_ref):
            if p.get('seat') == seat and p.get('uid') is not None:
                return str(p['uid'])
        return None

    def tag_seat(self, seat, tag, *, table_ref=None, note=''):
        """Marca o jogador do assento. Retorna o uid marcado ou None se o assento vazio."""
        uid = self.uid_at(seat, table_ref)
        if uid is None:
            return None
        self.store.set(uid, tag, note=note)
        return uid

    def tag_uid(self, uid, tag, *, note=''):
        self.store.set(uid, tag, note=note)
        return str(uid)

    def cycle_seat(self, seat, *, table_ref=None, order=CYCLE):
        """Cicla a tag do assento: sem tag -> order[0] -> ... -> order[-1] -> remove.
        Retorna (uid, nova_tag|None). Útil p/ um único clique que avança a etiqueta."""
        uid = self.uid_at(seat, table_ref)
        if uid is None:
            return None, None
        cur = canonical(self.store.tag_of(uid))
        seq = list(order)
        if cur in seq:
            i = seq.index(cur) + 1
            nxt = seq[i] if i < len(seq) else None
        else:
            nxt = seq[0]
        if nxt is None:
            self.store.remove(uid)
        else:
            self.store.set(uid, nxt)
        return uid, nxt

    def overview(self, table_ref=None):
        """Lista [{seat,uid,name,tag}] da(s) mesa(s), p/ o painel/HUD mostrar."""
        rows = []
        for p in self._players(table_ref):
            uid = str(p['uid']) if p.get('uid') is not None else None
            rows.append(dict(seat=p.get('seat'), uid=uid, name=(p.get('name') or '').strip(),
                             tag=self.store.tag_of(uid) if uid else None))
        return rows

    def save(self):
        return self.store.save()


def hit_seat(x, y, boxes):
    """Mapeia o clique (x,y) -> assento, dado `boxes` {seat: (x0,y0,x1,y1)} que o overlay
    visual fornece. Retorna o seat cuja caixa contém o ponto, ou None. (O clique real é
    capturado pelo overlay; esta função é o miolo testável do roteamento.)"""
    for seat, (x0, y0, x1, y1) in (boxes or {}).items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            return seat
    return None


def _main():
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    ap = argparse.ArgumentParser(description='Marcar jogadores (tags) no grind.')
    ap.add_argument('--table', default=None, help='ref da mesa (chave do live_seats_rich)')
    ap.add_argument('--seat', type=int, default=None)
    ap.add_argument('--uid', default=None)
    ap.add_argument('--tag', default=None, help='bote|station|bom|nvt|<custom>')
    ap.add_argument('--cycle', action='store_true', help='cicla a tag do assento')
    ap.add_argument('--list', action='store_true', help='mostra a mesa com as tags atuais')
    a = ap.parse_args()
    tl = TagLive.load()
    if a.uid and a.tag:
        tl.tag_uid(a.uid, a.tag); tl.save()
        print('marcado uid %s -> %s' % (a.uid, a.tag))
    elif a.seat is not None and a.cycle:
        uid, nt = tl.cycle_seat(a.seat, table_ref=a.table)
        tl.save(); print('assento %s (uid %s) -> %s' % (a.seat, uid, nt or '(sem tag)'))
    elif a.seat is not None and a.tag:
        uid = tl.tag_seat(a.seat, a.tag, table_ref=a.table)
        tl.save(); print('assento %s -> uid %s -> %s' % (a.seat, uid, a.tag))
    if a.list or not (a.tag or a.cycle):
        for r in tl.overview(a.table):
            mark = ('  <%s>' % r['tag']) if r['tag'] else ''
            print('  assento %s · %s · uid %s%s' % (r['seat'], r['name'], r['uid'], mark))


if __name__ == '__main__':
    _main()
