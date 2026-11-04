"""Contratos comuns para leitores independentes de regiões."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseRegionReader(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def read_region(self, region_name: str, roi_img: np.ndarray, **context) -> dict[str, Any]:
        """Retorna dados estruturados; ambiguidades devem permanecer pendentes."""
        raise NotImplementedError


def valid_rgb(image: np.ndarray) -> bool:
    return bool(isinstance(image, np.ndarray) and image.size and
                image.ndim == 3 and image.shape[2] == 3)
