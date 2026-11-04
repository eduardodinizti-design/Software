"""Fictitious tournament purchase laboratory. No OS clicks or client integration."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import json
import re
import sqlite3
import uuid


def number(value):
    try: result=Decimal(str(value))
    except InvalidOperation: raise ValueError('Valor inválido.')
    if not result.is_finite() or result<0: raise ValueError('Valor inválido.')
    return result


@dataclass(frozen=True)
class Offer:
    tournament_id: str
    offer_id: str
    kind: str
    price: str
    chips: int
    big_blind: int
    play_money_verified: bool
    open: bool = True
    source: str = 'laboratory'

    def validate(self):
        if not self.tournament_id or not self.offer_id or self.kind not in ('addon','rebuy'):
            raise ValueError('Oferta sem identidade ou tipo válido.')
        if self.source!='laboratory' or self.play_money_verified is not True:
            raise ValueError('Somente laboratório com fichas fictícias comprovadas.')
        number(self.price)
        if type(self.chips) is not int or self.chips<=0 or type(self.big_blind) is not int or self.big_blind<=0:
            raise ValueError('Quantidade de fichas ou blind inválido.')
        if type(self.open) is not bool: raise ValueError('Estado da oferta inválido.')


@dataclass(frozen=True)
class Rules:
    max_total_cost: str
    rebuy_min_bb: int = 50
    addon_min_bb: int | None = None
    enabled: bool = True

    def validate(self):
        number(self.max_total_cost)
        if type(self.enabled) is not bool: raise ValueError('Estado inválido.')
        for v in (self.rebuy_min_bb,self.addon_min_bb):
            if v is not None and (type(v) is not int or v<0): raise ValueError('Limite BB inválido.')
        if self.rebuy_min_bb is None: raise ValueError('Rebuy exige limite BB.')


def parse_addon_popup(rows):
    """OCR rows from an isolated simulator popup. Never infers a purchase from title alone.

    Supports a deliberately strict lab template, not arbitrary real PPPoker popups.
    Caller supplies tournament identity, blind and verifies play-money independently.
    """
    texts=[str(t).strip() for _,t,score in rows if score>=.95]
    headings=[t for t in texts if re.fullmatch(r'add[ -]?on',t,re.I)]
    costs=[m.group(1) for t in texts if (m:=re.fullmatch(r'Custo:\s*(\d+(?:[.,]\d{1,2})?)\s+fichas fict[ií]cias',t,re.I))]
    chips=[m.group(1) for t in texts if (m:=re.fullmatch(r'Receber:\s*(\d+)\s+fichas',t,re.I))]
    buttons=[t for t in texts if re.fullmatch(r'Comprar add[ -]?on',t,re.I)]
    if len(headings)!=1 or len(costs)!=1 or len(chips)!=1 or len(buttons)!=1:
        return dict(status='pending',reason='Oferta incompleta, ambígua ou pouco legível.',executable=False)
    if int(chips[0])<=0: return dict(status='pending',reason='Fichas inválidas.',executable=False)
    return dict(status='observed',kind='addon',price=costs[0].replace(',','.'),chips=int(chips[0]),
                executable=False,scope='isolated_laboratory_popup')


class PurchaseLedger:
    """Persistent reservation before simulated execution; uncertainty never retries."""
    def __init__(self,path):
        self.db=sqlite3.connect(path,timeout=10,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS tournaments(id TEXT PRIMARY KEY, bounty INTEGER NOT NULL, entry_cost TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS purchases(token TEXT PRIMARY KEY,tournament_id TEXT NOT NULL,offer_id TEXT NOT NULL,
              kind TEXT NOT NULL,price TEXT NOT NULL,chips INTEGER NOT NULL,status TEXT NOT NULL,
              UNIQUE(tournament_id,offer_id));
          CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY,event TEXT NOT NULL,payload TEXT NOT NULL);
        ''')

    def close(self): self.db.close()

    def register(self,tournament_id,entry_cost,bounty):
        if not tournament_id or type(bounty) is not bool: raise ValueError('Torneio inválido.')
        price=str(number(entry_cost))
        self.db.execute('INSERT OR IGNORE INTO tournaments VALUES(?,?,?)',(tournament_id,int(bounty),price))
        old=self.db.execute('SELECT * FROM tournaments WHERE id=?',(tournament_id,)).fetchone()
        if number(old['entry_cost'])!=number(price) or old['bounty']!=int(bounty):
            raise ValueError('Torneio já registrado com outra configuração.')

    def audit(self,event,payload):
        self.db.execute('INSERT INTO audit(event,payload) VALUES(?,?)',(event,json.dumps(payload)))

    def reserve(self,offer,rules):
        offer.validate();rules.validate()
        if not rules.enabled: return dict(status='blocked',reason='paused',should_execute=False)
        if not offer.open: return dict(status='blocked',reason='offer_closed',should_execute=False)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            tournament=self.db.execute('SELECT * FROM tournaments WHERE id=?',(offer.tournament_id,)).fetchone()
            if tournament is None: raise ValueError('Torneio não registrado.')
            old=self.db.execute('SELECT * FROM purchases WHERE tournament_id=? AND offer_id=?',
                                (offer.tournament_id,offer.offer_id)).fetchone()
            if old:
                if old['kind']!=offer.kind or number(old['price'])!=number(offer.price) or old['chips']!=offer.chips:
                    raise ValueError('Oferta mudou mantendo o mesmo ID; exige nova observação.')
                result=dict(status=old['status'],token=old['token'],should_execute=False,reason='already_seen')
            else:
                active=self.db.execute("SELECT * FROM purchases WHERE tournament_id=? AND status IN ('reserved','confirmed')",
                                       (offer.tournament_id,)).fetchall()
                reason=None
                minimum=rules.rebuy_min_bb if offer.kind=='rebuy' else rules.addon_min_bb
                if offer.kind=='rebuy' and not tournament['bounty']: reason='rebuy_requires_bounty'
                elif minimum is not None and offer.chips<minimum*offer.big_blind: reason='received_bb_below_minimum'
                elif any(r['kind']==offer.kind for r in active): reason='one_purchase_per_kind'
                elif number(tournament['entry_cost'])+sum((number(r['price']) for r in active),Decimal(0))+number(offer.price)>number(rules.max_total_cost):
                    reason='budget_exceeded'
                if reason: result=dict(status='blocked',reason=reason,should_execute=False)
                else:
                    token=uuid.uuid4().hex
                    self.db.execute('INSERT INTO purchases VALUES(?,?,?,?,?,?,?)',
                        (token,offer.tournament_id,offer.offer_id,offer.kind,str(number(offer.price)),offer.chips,'reserved'))
                    result=dict(status='reserved',token=token,should_execute=True,received_bb=offer.chips/offer.big_blind)
            self.audit('reservation',dict(tournament=offer.tournament_id,offer=offer.offer_id,result=result))
            self.db.execute('COMMIT');return result
        except Exception:
            self.db.execute('ROLLBACK');raise

    def confirm(self,token,tournament_id,kind,price,chips,accepted):
        """Explicit simulator receipt required. Disappearance of popup is not confirmation."""
        if type(accepted) is not bool: raise ValueError('Recibo sem resultado explícito.')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT * FROM purchases WHERE token=?',(token,)).fetchone()
            if row is None or (row['tournament_id'],row['kind'],number(row['price']),row['chips'])!=(tournament_id,kind,number(price),chips):
                raise ValueError('Recibo não corresponde à reserva.')
            status='confirmed' if accepted else 'rejected'
            if row['status'] not in ('reserved',status): raise ValueError('Recibo contraditório.')
            self.db.execute('UPDATE purchases SET status=? WHERE token=?',(status,token))
            self.audit('receipt',dict(token=token,status=status))
            self.db.execute('COMMIT');return dict(status=status,should_execute=False)
        except Exception:
            self.db.execute('ROLLBACK');raise
