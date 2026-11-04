"""Mapeia observações para ranges remotos; não executa ações."""
from __future__ import annotations


class RangeCoachStrategy:
    def __init__(self, connector, laboratory_book=None, nvt_ranges=None):
        self.connector = connector
        self.laboratory_book = laboratory_book
        self.nvt_ranges = nvt_ranges

    def theoretical_action(self, partial_cards, context):
        if self.nvt_ranges is not None:
            return self.nvt_ranges.recommend(partial_cards, context)
        if self.laboratory_book is not None:
            return self.laboratory_book.recommend(partial_cards, context)
        hero = partial_cards.get("hero") or partial_cards.get("hero_cards") or []
        if len(hero) != 2:
            return {"status": "pending", "reason": "Cartas do Hero incompletas."}
        if partial_cards.get('street') != 'preflop' or partial_cards.get('board'):
            return {"status": "pending", "reason": "Consulta remota disponível apenas para pré-flop comprovado."}
        return self.connector.lookup_range(
            hero, context.get("position"), context.get("tournament_type", "freezeout"))

    def audit_consolidated(self, snapshot, tournament):
        return self.connector.upload_audit(snapshot, tournament)
