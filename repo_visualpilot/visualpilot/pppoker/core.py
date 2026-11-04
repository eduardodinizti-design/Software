"""Componente observacional recuperado do projeto enviado; ver docs/LEGACY_REUSE.md."""
from dataclasses import asdict, dataclass
import math
import cv2
import numpy as np

@dataclass(frozen=True)
class Region:
    left: int
    top: int
    width: int
    height: int

    def __post_init__(self):
        if any((type(v) is not int for v in asdict(self).values())):
            raise ValueError('As coordenadas devem ser números inteiros.')
        if self.width < 1 or self.height < 1:
            raise ValueError('A região deve ter largura e altura positivas.')
        if self.width * self.height > 20000000:
            raise ValueError('Selecione uma região menor que 20 milhões de pixels.')

    def to_dict(self):
        return asdict(self)

    def contains(self, other):
        return self.left <= other.left and self.top <= other.top and (other.left + other.width <= self.left + self.width) and (other.top + other.height <= self.top + self.height)

def require_rgb(image):
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError('A imagem precisa ser um array uint8.')
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 1:
        raise ValueError('A imagem precisa estar no formato RGB.')

def change_ratio(previous, current, pixel_threshold=25):
    """Fraction of pixels with a changed channel; independent of ROI size."""
    require_rgb(current)
    if previous is None or previous.shape != current.shape:
        return 1.0
    require_rgb(previous)
    diff = np.abs(current.astype(np.int16) - previous.astype(np.int16))
    return float(np.mean(np.any(diff > pixel_threshold, axis=2)))
