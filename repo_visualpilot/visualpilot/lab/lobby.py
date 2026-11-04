"""Conservative OCR lobby selection for the explicitly calibrated laboratory layout."""
from dataclasses import dataclass
from decimal import Decimal
import json
import math
import re
from time import monotonic
import uuid

import cv2
import numpy as np

from .registration import field


def buyin_total(expression):
    """Sum every displayed component exactly. Never truncate at the first number."""
    if not isinstance(expression, str) or len(expression) > 100:
        raise ValueError('Buy-in inválido.')
    parts = re.split(r'\s*\+\s*', expression.strip())
    if not 1 <= len(parts) <= 4 or any(not re.fullmatch(r'[0-9]{1,6}(?:[.,][0-9]{1,2})?', p) for p in parts):
        raise ValueError('Buy-in incompleto, ambíguo ou formato não suportado.')
    return sum((Decimal(p.replace(',', '.')) for p in parts), Decimal(0))


def parse_card(rows):
    """An explicit ID, currency and registration state are required for selection."""
    result = dict(tournament=None, name=None, buyin=None, registration='unknown', readable=False)
    try:
        result['tournament'] = field(rows, r'Torneio: ([A-Z0-9-]{1,32})')
        result['name'] = field(rows, r'Nome: ([\w][\w .-]{0,60})')
        result['kind'] = field(rows, r'Tipo: (MTT|SNG)')
        price = field(join_price_lines(rows), r'Buy-in: ([0-9.,+\s]+)\s*fichas\s*ficticias')
        result['buyin'] = format(buyin_total(price), '.2f')
        result['stack'] = int(field(rows, r'Stack: ([0-9]{1,8})'))
        result['start_time'] = field(rows, r'Inicio: ((?:[01][0-9]|2[0-3]):[0-5][0-9])')
        state = field(rows, r'Registro: (ABERTO|ENCERRADO|EM BREVE)')
        result['registration'] = {'ABERTO':'open', 'ENCERRADO':'closed', 'EM BREVE':'scheduled'}[state]
        result['readable'] = True
    except (ValueError, TypeError) as exc:
        result['reason'] = str(exc)
    return result


def join_price_lines(rows):
    """Only adjacent price continuations inside one segmented card may join."""
    result = list(rows)
    starts = [i for i, (_, text, _) in enumerate(rows) if re.match(r'^Buy-in\s*:', str(text).strip())]
    if len(starts) != 1:
        return result
    index = starts[0]
    box, text, score = result[index]
    for _ in range(3):
        if re.search(r'fichas\s*ficticias$', str(text).strip()) or index+1 >= len(result):
            break
        _, following, confidence = result[index+1]
        if not re.fullmatch(r'[0-9.,+\s]+(?:fichas\s*ficticias)?', str(following).strip()):
            break
        text = str(text)+' '+str(following)
        if not all(math.isfinite(float(value)) and 0 <= float(value) <= 1 for value in (score, confidence)):
            raise ValueError('Confiança inválida no buy-in quebrado em linhas.')
        score = min(float(score), float(confidence))
        result[index] = (box, text, score)
        result.pop(index+1)
    return result


def segment_cards(image, origin=(0, 0)):
    """Detect complete blue-bordered lab cards, with no fixed height assumption.

    This calibration belongs to lobby_simulator.html, not to an arbitrary client.
    Partial edge cards and broken borders are excluded.
    """
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or not image.size or image.shape[0]*image.shape[1] > 16*1024*1024):
        raise ValueError('Imagem do lobby inválida.')
    if len(origin) != 2 or any(type(n) is not int for n in origin):
        raise ValueError('Origem inválida.')
    mask = cv2.inRange(image, np.array([160,113,56], np.uint8), np.array([180,133,76], np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if width < 300 or height < 150 or x <= 0 or y <= 0 or x+width >= image.shape[1] or y+height >= image.shape[0]:
            continue
        edge = mask[y:y+height, x:x+width]
        coverage = (np.any(edge[:4], axis=0).mean(), np.any(edge[-4:], axis=0).mean(),
                    np.any(edge[:, :4], axis=1).mean(), np.any(edge[:, -4:], axis=1).mean())
        if min(coverage) < .9:
            continue
        found.append(dict(local_box=[x,y,width,height], box=[x+origin[0],y+origin[1],width,height],
                          point=[x+origin[0]+width/2,y+origin[1]+height/2]))
    if len(found) > 24:
        raise ValueError('Número de cartões acima do limite do laboratório.')
    return sorted(found, key=lambda item: (item['box'][1], item['box'][0]))


@dataclass(frozen=True)
class LobbyRules:
    max_buyin: str = '50'
    allowed_types: tuple[str, ...] = ('MTT',)
    targets: tuple[str, ...] = ()
    minimum_stack: int = 1000
    max_candidates: int = 4

    def validate(self):
        if not isinstance(self.max_buyin, str) or not re.fullmatch(r'[0-9]+(?:[.,][0-9]{1,2})?', self.max_buyin):
            raise ValueError('Limite de buy-in inválido.')
        if not 0 <= buyin_total(self.max_buyin) <= 50:
            raise ValueError('Limite acima das 50 fichas autorizadas.')
        if (not isinstance(self.targets, tuple) or len(self.targets) > 4 or len(set(self.targets)) != len(self.targets)
                or any(not isinstance(t,str) or not re.fullmatch(r'[A-Z0-9-]{1,32}',t) for t in self.targets)):
            raise ValueError('Lista de alvos inválida.')
        if not isinstance(self.allowed_types, tuple) or not self.allowed_types or any(t not in ('MTT','SNG') for t in self.allowed_types):
            raise ValueError('Tipos inválidos.')
        if type(self.max_candidates) is not int or not 1 <= self.max_candidates <= 4:
            raise ValueError('Limite de candidatos inválido.')
        if type(self.minimum_stack) is not int or self.minimum_stack < 0:
            raise ValueError('Stack mínimo inválido.')


def filter_cards(cards, rules):
    rules.validate()
    seen = {}
    for card in cards:
        if card.get('tournament'):
            seen[card['tournament']] = seen.get(card['tournament'], 0)+1
    evaluated, eligible = [], []
    for card in cards:
        reason = None
        if not card.get('readable'): reason = 'unreadable'
        elif seen.get(card['tournament']) != 1: reason = 'duplicate_identity'
        elif card['registration'] != 'open': reason = 'registration_not_explicitly_open'
        elif rules.targets and card['tournament'] not in rules.targets: reason = 'outside_targets'
        elif card['kind'] not in rules.allowed_types: reason = 'type_filter'
        elif Decimal(card['buyin']) > buyin_total(rules.max_buyin): reason = 'buyin_limit'
        elif card['stack'] < rules.minimum_stack: reason = 'stack_filter'
        elif len(eligible) >= rules.max_candidates: reason = 'candidate_limit'
        row = dict(card, eligible=reason is None, rejection=reason)
        evaluated.append(row)
        if reason is None: eligible.append(row)
    return dict(cards=evaluated, eligible=eligible)


class LobbyHistory:
    def __init__(self, ledger):
        self.ledger = ledger
        self.db = ledger.db
        self.db.execute('''CREATE TABLE IF NOT EXISTS lobby_visits(
            tournament TEXT PRIMARY KEY, token TEXT NOT NULL, status TEXT NOT NULL, selection TEXT NOT NULL)''')

    def excluded(self):
        ids = {row[0] for row in self.db.execute('SELECT tournament FROM lobby_visits')}
        ids.update(row[0] for row in self.db.execute('SELECT id FROM tournaments'))
        ids.update(row[0] for row in self.db.execute("SELECT tournament FROM registrations WHERE status!='rejected'"))
        return ids

    def claim(self, selection):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if selection['tournament'] in self.excluded():
                result = dict(status='blocked', reason='already_visited_or_registered')
            else:
                token = uuid.uuid4().hex
                self.db.execute('INSERT INTO lobby_visits VALUES(?,?,?,?)',
                    (selection['tournament'],token,'opening',json.dumps(selection)))
                result = dict(status='opening',token=token)
            self.ledger.audit('lobby_claim',dict(selection=selection,result=result))
            self.db.execute('COMMIT')
            return result
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def complete(self, token, status):
        if status not in ('opened','unknown','cancelled'):
            raise ValueError('Resultado de navegação inválido.')
        self.db.execute('UPDATE lobby_visits SET status=? WHERE token=? AND status=?', (status,token,'opening'))
        self.ledger.audit('lobby_result',dict(token=token,status=status))


DETAIL_KEYS = ('tournament','name','kind','buyin','stack','start_time','registration')


def require_fresh(sample, *, clock=monotonic):
    if sample.get('source') != 'laboratory' or not 0 <= clock()-sample['observed'] <= 5:
        raise ValueError('Observação do lobby vencida ou inválida.')


def obter_torneios_validos(adapter, history, rules, *, clock=monotonic):
    """Return the scan together with its capture; coordinates never travel alone."""
    rules.validate()
    sample = adapter.capture_lobby()
    require_fresh(sample, clock=clock)
    excluded = history.excluded()
    candidates = [card for card in sample['cards'] if card.get('tournament') not in excluded]
    evaluated = filter_cards(candidates, rules)
    history.ledger.audit('lobby_scan',dict(image=sample['image'],result=evaluated,excluded=sorted(excluded)))
    return sample, evaluated


def validar_detalhes(selection, sample, *, clock=monotonic):
    """Return verified fields, or raise with a reason. A name substring is insufficient."""
    require_fresh(sample, clock=clock)
    details = parse_card(sample['rows'])
    if (selection.get('readable') is not True or selection.get('registration') != 'open'
            or not details['readable'] or any(details.get(k) != selection.get(k) for k in DETAIL_KEYS)):
        raise ValueError('Detalhes diferem do cartão selecionado; inscrição não autorizada.')
    return details


def clicar_posicao(adapter, selection, sample, control, revision, *, clock=monotonic):
    """Consume a captured card through the guarded adapter, never an arbitrary x/y."""
    if not isinstance(selection, dict):
        raise ValueError('Clique exige o cartão e sua observação, não coordenadas isoladas.')
    keys = DETAIL_KEYS + ('readable','box','point')
    if (selection.get('readable') is not True or selection.get('registration') != 'open'
            or not selection.get('point') or not selection.get('box')
            or not any(all(selection.get(k) == card.get(k) for k in keys) for card in sample['cards'])):
        raise ValueError('Cartão não pertence à captura fornecida.')
    def apply():
        require_fresh(sample, clock=clock)
        # The GUI adapter additionally checks current pixels/geometry, native
        # revision, and single use of coordinates before dispatching the click.
        return adapter.open_card(selection, sample['revision'])
    return control.perform(revision, apply)


def open_next_tournament(adapter, history, rules, control, *, clock=monotonic):
    """One selection per capture; never click a precomputed list after navigation."""
    rules.validate()
    adapter.sync_control()
    revision = control.revision
    token = None
    try:
        control.perform(revision, lambda: None)
        sample, evaluated = obter_torneios_validos(adapter, history, rules, clock=clock)
        if not evaluated['eligible']:
            return dict(status='empty', reason='no_eligible_unvisited_tournament', scan=evaluated)
        selection = evaluated['eligible'][0]
        control.perform(revision, lambda: None)
        claim = history.claim(selection)
        if claim['status'] != 'opening': return claim
        token = claim['token']
        if not clicar_posicao(adapter, selection, sample, control, revision, clock=clock):
            history.complete(token,'cancelled')
            return dict(status='blocked', reason=adapter.last_error, token=token)
        details_sample = adapter.capture_details()
        details = validar_detalhes(selection, details_sample, clock=clock)
        history.complete(token,'opened')
        return dict(status='opened', selection=selection, details=details, token=token, registered=False)
    except Exception as exc:
        if token: history.complete(token,'unknown')
        result = dict(status='unknown' if token else 'blocked', reason=str(exc)[:500], registered=False)
        history.ledger.audit('lobby_interrupted',result)
        return result
