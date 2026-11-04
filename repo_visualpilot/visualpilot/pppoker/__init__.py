"""Componentes de visão e automação do PPPoker."""
from visualpilot.pppoker.tournament_registration import (
    TournamentRegistrationManager,
    RegistrationStepResult,
    DEFAULT_REGISTRATION_ROIS,
)
from visualpilot.pppoker.lobby_orchestrator import (
    LobbyOrchestrator,
    LoopConfig,
    AntiDuplicationRegistry,
    AntiDupRecord,
    generate_tournament_key,
)

__all__ = [
    "TournamentRegistrationManager",
    "RegistrationStepResult",
    "DEFAULT_REGISTRATION_ROIS",
    "LobbyOrchestrator",
    "LoopConfig",
    "AntiDuplicationRegistry",
    "AntiDupRecord",
    "generate_tournament_key",
]
