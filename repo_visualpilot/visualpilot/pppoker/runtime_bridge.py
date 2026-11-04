"""Inicialização local sem módulos de navegação, estratégia ou cliques."""
from .observer.runtime import PerceptionSession


def session_factory(root, stop, events, exclusions=lambda: ()):
    return PerceptionSession(root, stop, events, exclusions, workers=2)
