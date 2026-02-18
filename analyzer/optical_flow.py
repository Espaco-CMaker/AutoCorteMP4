"""
Análise de fluxo óptico com suporte a 8 direções (incluindo diagonais).
Detecta: pan, tilt, diagonais, zoom, rotação e combinações.
"""

import cv2
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from typing import Tuple


class MovementDirection(Enum):
    NONE        = "parado"
    RIGHT       = "direita"
    LEFT        = "esquerda"
    UP          = "cima"
    DOWN        = "baixo"
    UP_RIGHT    = "diagonal_cima_direita"
    UP_LEFT     = "diagonal_cima_esquerda"
    DOWN_RIGHT  = "diagonal_baixo_direita"
    DOWN_LEFT   = "diagonal_baixo_esquerda"
    ZOOM_IN     = "aproximação"
    ZOOM_OUT    = "afastamento"
    ROTATION    = "rotação"
    MIXED       = "misto"


# Mapeamento de direção para ângulo central (graus, 0=direita, sentido anti-horário)
DIRECTION_ANGLES = {
    MovementDirection.RIGHT:      0.0,
    MovementDirection.UP_RIGHT:   45.0,
    MovementDirection.UP:         90.0,
    MovementDirection.UP_LEFT:    135.0,
    MovementDirection.LEFT:       180.0,
    MovementDirection.DOWN_LEFT:  225.0,
    MovementDirection.DOWN:       270.0,
    MovementDirection.DOWN_RIGHT: 315.0,
}


@dataclass
class FrameMotion:
    magnitude: float                    # Magnitude média do movimento
    direction: MovementDirection        # Direção dominante
    angle_degrees: float                # Ângulo médio ponderado (0-360)
    angle_std: float                    # Desvio padrão do ângulo (coerência do movimento)
    is_divergent: bool                  # Zoom in/out
    is_rotational: bool                 # Rotação do quadro
    dx_mean: float                      # Componente horizontal média
    dy_mean: float                      # Componente vertical média
    raw_flow: np.ndarray = field(repr=False)  # Fluxo bruto


def compute_optical_flow(prev_gray: np.ndarray, curr_gray: np.ndarray) -> np.ndarray:
    """Calcula fluxo óptico denso Farneback."""
    return cv2.calcOpticalFlowFarneback(
        prev_gray, curr_gray, None,
        pyr_scale=0.5,
        levels=4,
        winsize=15,
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0
    )


def analyze_flow(flow: np.ndarray, magnitude_threshold: float = 1.0) -> FrameMotion:
    """
    Analisa fluxo óptico e retorna informações completas sobre o movimento,
    incluindo ângulo exato, intensidade e tipo (translação, zoom, rotação).
    """
    fx, fy = flow[..., 0], flow[..., 1]

    dx_mean = float(np.mean(fx))
    dy_mean = float(np.mean(fy))

    # Magnitude e ângulo por pixel (ângulo em graus, 0=direita, anti-horário)
    magnitude, angle_rad = cv2.cartToPolar(fx, -fy)  # -fy para corrigir eixo Y invertido do OpenCV
    angle_deg = np.degrees(angle_rad) % 360

    mean_magnitude = float(np.mean(magnitude))

    if mean_magnitude < magnitude_threshold:
        return FrameMotion(
            magnitude=mean_magnitude,
            direction=MovementDirection.NONE,
            angle_degrees=0.0,
            angle_std=0.0,
            is_divergent=False,
            is_rotational=False,
            dx_mean=dx_mean,
            dy_mean=dy_mean,
            raw_flow=flow
        )

    # Ângulo médio ponderado pela magnitude
    weights = magnitude.flatten() + 1e-6
    angles_flat = angle_deg.flatten()

    # Média circular ponderada
    sin_mean = np.average(np.sin(np.radians(angles_flat)), weights=weights)
    cos_mean = np.average(np.cos(np.radians(angles_flat)), weights=weights)
    mean_angle = float(np.degrees(np.arctan2(sin_mean, cos_mean)) % 360)

    # Desvio padrão circular (coerência)
    R = np.sqrt(sin_mean**2 + cos_mean**2)
    angle_std = float(np.degrees(np.sqrt(-2 * np.log(R + 1e-6))))

    is_divergent, divergence_score = _detect_zoom(flow)
    is_rotational = _detect_rotation(fx, fy)

    if is_rotational and not is_divergent:
        direction = MovementDirection.ROTATION
    elif is_divergent:
        direction = MovementDirection.ZOOM_IN if divergence_score > 0 else MovementDirection.ZOOM_OUT
    else:
        direction = _angle_to_direction_8(mean_angle)

    return FrameMotion(
        magnitude=mean_magnitude,
        direction=direction,
        angle_degrees=mean_angle,
        angle_std=angle_std,
        is_divergent=is_divergent,
        is_rotational=is_rotational,
        dx_mean=dx_mean,
        dy_mean=dy_mean,
        raw_flow=flow
    )


def _angle_to_direction_8(angle: float) -> MovementDirection:
    """
    Mapeia ângulo para 8 direções (incluindo 4 diagonais).
    Cada setor tem 45°, centrado nas direções cardeais e diagonais.
    """
    angle = angle % 360
    # Setores de 45° cada, deslocados 22.5° para centralizar
    if angle < 22.5 or angle >= 337.5:
        return MovementDirection.RIGHT
    elif 22.5 <= angle < 67.5:
        return MovementDirection.UP_RIGHT
    elif 67.5 <= angle < 112.5:
        return MovementDirection.UP
    elif 112.5 <= angle < 157.5:
        return MovementDirection.UP_LEFT
    elif 157.5 <= angle < 202.5:
        return MovementDirection.LEFT
    elif 202.5 <= angle < 247.5:
        return MovementDirection.DOWN_LEFT
    elif 247.5 <= angle < 292.5:
        return MovementDirection.DOWN
    elif 292.5 <= angle < 337.5:
        return MovementDirection.DOWN_RIGHT
    return MovementDirection.MIXED


def _detect_zoom(flow: np.ndarray) -> Tuple[bool, float]:
    """
    Detecta zoom analisando divergência do fluxo em relação ao centro.
    Retorna (is_zoom, score): score > 0 = zoom in, < 0 = zoom out.
    """
    h, w = flow.shape[:2]
    cy, cx = h / 2, w / 2

    y_coords, x_coords = np.mgrid[0:h, 0:w].astype(np.float32)
    x_rel = x_coords - cx
    y_rel = y_coords - cy

    # Normaliza vetor radial
    radial_dist = np.sqrt(x_rel**2 + y_rel**2) + 1e-6
    x_norm = x_rel / radial_dist
    y_norm = y_rel / radial_dist

    fx, fy = flow[..., 0], flow[..., 1]
    dot_product = fx * x_norm + fy * y_norm
    mean_dot = float(np.mean(dot_product))

    magnitude_mean = float(np.mean(np.sqrt(fx**2 + fy**2)))
    if magnitude_mean < 0.3:
        return False, 0.0

    # Normaliza pelo magnitude para comparar com limiar fixo
    normalized_score = mean_dot / (magnitude_mean + 1e-6)
    is_zoom = abs(normalized_score) > 0.25

    return is_zoom, normalized_score


def _detect_rotation(fx: np.ndarray, fy: np.ndarray) -> bool:
    """
    Detecta rotação analisando padrão de curl (rotacional) do fluxo.
    """
    h, w = fx.shape
    cy, cx = h / 2, w / 2

    y_coords, x_coords = np.mgrid[0:h, 0:w].astype(np.float32)
    x_rel = x_coords - cx
    y_rel = y_coords - cy

    # Produto vetorial (cross product 2D) entre vetor radial e fluxo
    # Se positivo e consistente, há rotação
    cross = x_rel * fy - y_rel * fx
    mean_cross = float(np.mean(cross))
    magnitude_mean = float(np.mean(np.sqrt(fx**2 + fy**2)))

    if magnitude_mean < 0.3:
        return False

    normalized_curl = abs(mean_cross) / (magnitude_mean * max(h, w) / 2 + 1e-6)
    return normalized_curl > 0.15


def angle_difference(a1: float, a2: float) -> float:
    """Diferença angular mínima entre dois ângulos (0-180 graus)."""
    diff = abs(a1 - a2) % 360
    return min(diff, 360 - diff)
