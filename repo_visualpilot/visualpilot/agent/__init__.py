"""Integrações consultivas; nenhuma rotina executa ações na mesa."""

from .connector import RangeCoachConnector
from .bridge import RangeCoachEventBridge
from .strategy import RangeCoachStrategy

__all__ = ["RangeCoachConnector", "RangeCoachEventBridge", "RangeCoachStrategy"]
