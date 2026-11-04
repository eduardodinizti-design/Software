"""Auditable posterior range for one fictitious heads-up hand."""
import copy
import math
from .postflop import validate_cards


def normalize_range(weights, dead=()):
    validate_cards(dead)
    clean = {}
    seen = set()
    for combo, weight in weights.items():
        if len(combo) != 2: raise ValueError('Combo deve conter duas cartas.')
        validate_cards(combo)
        key = tuple(sorted(combo))
        if key in seen: raise ValueError('Combo duplicado com ordem invertida.')
        seen.add(key)
        if type(weight) not in (int, float) or not math.isfinite(weight) or weight < 0:
            raise ValueError('Peso inválido.')
        if weight and not set(combo) & set(dead): clean[tuple(combo)] = weight
    total = sum(clean.values())
    if not total: raise ValueError('Evidência incompatível: range vazio.')
    return {c:w/total for c,w in clean.items()}


def condition(weights, likelihood):
    """Bayes update. Missing likelihood is an error, never implicit zero."""
    if any(c not in likelihood for c in weights): raise ValueError('Modelo de ação incompleto.')
    if any(type(likelihood[c]) not in (int,float) or not math.isfinite(likelihood[c])
           or not 0 <= likelihood[c] <= 1 for c in weights):
        raise ValueError('Probabilidade inválida.')
    evidence = sum(w*likelihood[c] for c,w in weights.items())
    if evidence <= 0: raise ValueError('Ação impossível sob o modelo; requer revisão.')
    return {c:w*likelihood[c]/evidence for c,w in weights.items() if w*likelihood[c]>0}, evidence


class RangeState:
    def __init__(self, hand_id, hero, board, weights, provenance):
        if not hand_id or len(hero)!=2 or len(board) not in (3,4,5): raise ValueError('Estado inválido.')
        self.hand_id=hand_id; self.hero=tuple(hero); self.board=tuple(board)
        self.weights=normalize_range(weights, self.hero+self.board)
        self.provenance=copy.deepcopy(provenance); self.events=[]; self._ids=set()
        self.initial=dict(board=list(board),weights=[[*c,w] for c,w in self.weights.items()])

    def observe(self, event_id, action, likelihood, model_id):
        if not event_id or event_id in self._ids: raise ValueError('Evento repetido ou sem ID.')
        if not action or not model_id: raise ValueError('Ação e origem do modelo obrigatórias.')
        updated, probability=condition(self.weights, likelihood)
        self.events.append(dict(id=event_id,kind='villain_action',action=action,model_id=model_id,
                                probability=probability,before=len(self.weights),after=len(updated),
                                likelihood=[[*c,likelihood[c]] for c in self.weights]))
        self.weights=updated; self._ids.add(event_id)

    def reveal(self, event_id, board):
        board=tuple(board)
        if not event_id or event_id in self._ids: raise ValueError('Evento repetido ou sem ID.')
        if len(board)!=len(self.board)+1 or len(board)>5 or board[:-1]!=self.board:
            raise ValueError('Board deve avançar uma carta preservando a mão.')
        updated=normalize_range(self.weights,self.hero+board)
        self.events.append(dict(id=event_id,kind='board',board=list(board),
                                before=len(self.weights),after=len(updated)))
        self.weights=updated;self.board=board;self._ids.add(event_id)

    def snapshot(self):
        return copy.deepcopy(dict(hand_id=self.hand_id,hero=list(self.hero),board=list(self.board),
            weights=[[*c,w] for c,w in self.weights.items()],initial=self.initial,
            provenance=self.provenance,events=self.events))
