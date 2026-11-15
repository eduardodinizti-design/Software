"""Exact suit renaming of a stored policy, only when BOTH priors are preserved.

This is a bijection of the same game. It is not a nearest-board heuristic, a
new solve or permission to use a model for different ranks/stacks/formats.
Public node IDs stay canonical; consumers use node_key(state), as with flop
order aliases. The derived policy fingerprint binds the source and bijection.
"""
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import replace
import itertools

from strategy.range_catalog import combo_key
from strategy.state_contract import BettingState,StrategyError,cards,digest

SUITS='cdhs'


def rename_card(card,mapping):return card[0]+mapping[card[1]]


def flop_signature(board):
    board=cards(board,(3,))
    return min(tuple(sorted(rename_card(c,dict(zip(SUITS,p))) for c in board)) for p in itertools.permutations(SUITS))


def exact_suit_map(source_board,observed_board,ranges):
    source=cards(source_board,(3,));observed=set(cards(observed_board,(3,)))
    for permutation in itertools.permutations(SUITS):
        mapping=dict(zip(SUITS,permutation))
        if {rename_card(c,mapping) for c in source}!=observed:continue
        if all({combo_key((rename_card(k[:2],mapping),rename_card(k[2:],mapping))):w for k,w in r.weights}
               ==dict(r.weights) for r in ranges):return mapping
    raise StrategyError('SUIT_EQUIVALENCE_DOES_NOT_PRESERVE_BOTH_PRIORS')


def rename_state(state,mapping):
    return replace(state,board=tuple(rename_card(c,mapping) for c in state.board),
        history=tuple('BOARD:'+rename_card(h[6:],mapping) if h.startswith('BOARD:') else h for h in state.history))


class _SuitNodes(Mapping):
    def __init__(self,view):self.view=view
    def __len__(self):return len(self.view.source.nodes)
    def __iter__(self):return iter(self.view.source.nodes)
    def __getitem__(self,key):return self.view.get_node(key)


class SuitPolicy:
    def __init__(self,source,mapping):
        if set(mapping)!=set(SUITS) or set(mapping.values())!=set(SUITS):raise StrategyError('SUIT_MAP_MUST_BE_A_BIJECTION')
        if any({combo_key((rename_card(k[:2],mapping),rename_card(k[2:],mapping))):w for k,w in r.weights}!=dict(r.weights) for r in source.ranges):
            raise StrategyError('SUIT_EQUIVALENCE_DOES_NOT_PRESERVE_BOTH_PRIORS')
        self.source,self.mapping=source,dict(mapping);self.inverse={v:k for k,v in mapping.items()}
        self.context,self.ranges,self.menu=source.context,source.ranges,source.menu
        self.root=rename_state(source.root,self.mapping);self.native_menu=getattr(source,'native_menu',False)
        self.data=dict(schema='software.hu-exact-suit-view.v1',source_policy_sha256=source.fingerprint,
            source_to_observed_suits=self.mapping,evaluation=source.data.get('evaluation'))
        self.fingerprint=digest(self.data)
        self.quality=dict(source.quality,source_policy_sha256=source.fingerprint,
            exact_suit_renaming=True,priors_invariance_verified=True,new_solve=False)
        self.nodes=_SuitNodes(self);self._cache=OrderedDict()

    def get_node(self,key):
        if key not in self._cache:
            source=self.source.nodes[key]
            node=dict(source,state=rename_state(BettingState.from_dict(source['state']),self.mapping).to_dict(),
                combos={combo_key((rename_card(k[:2],self.mapping),rename_card(k[2:],self.mapping))):row
                        for k,row in source['combos'].items()})
            self._cache[key]=node
            if len(self._cache)>8:self._cache.popitem(last=False)
        self._cache.move_to_end(key);return self._cache[key]

    def node_key(self,state):return self.source.node_key(rename_state(state,self.inverse))

    def actions(self,state):return self.source.actions(rename_state(state,self.inverse))

    def row(self,state,hand):
        node=self.get_node(self.node_key(state));key=combo_key(hand)
        if key not in node['combos']:raise StrategyError('POLICY_COMBO_MISS_OR_OFF_POLICY')
        return node,node['combos'][key]

    def probabilities(self,state,hand):
        _,row=self.row(state,hand)
        return [row['frequencies'][a.id] for a in self.actions(state)]

    def close(self):
        self._cache.clear()
        if hasattr(self.source,'close'):self.source.close()
