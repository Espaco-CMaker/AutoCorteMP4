"""
Detecção de cortes bruscos de cena via histograma HSV e SSIM.
"""

import cv2
import numpy as np
from typing import Tuple


def histogram_difference(frame1: np.ndarray, frame2: np.ndarray) -> float:
    hsv1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2HSV)
    hsv2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2HSV)
    scores = []
    for ch in range(3):
        h1 = cv2.calcHist([hsv1], [ch], None, [64], [0, 256])
        h2 = cv2.calcHist([hsv2], [ch], None, [64], [0, 256])
        cv2.normalize(h1, h1)
        cv2.normalize(h2, h2)
        corr = cv2.compareHist(h1, h2, cv2.HISTCMP_CORREL)
        scores.append(corr)
    return (1.0 - float(np.mean(scores))) / 2.0


def ssim_score(frame1: np.ndarray, frame2: np.ndarray) -> float:
    g1 = cv2.cvtColor(cv2.resize(frame1, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(cv2.resize(frame2, (320, 180)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    C1, C2 = 6.5025, 58.5225
    mu1 = cv2.GaussianBlur(g1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(g2, (11, 11), 1.5)
    mu1_sq, mu2_sq, mu1_mu2 = mu1**2, mu2**2, mu1*mu2
    s1 = cv2.GaussianBlur(g1**2, (11, 11), 1.5) - mu1_sq
    s2 = cv2.GaussianBlur(g2**2, (11, 11), 1.5) - mu2_sq
    s12 = cv2.GaussianBlur(g1*g2, (11, 11), 1.5) - mu1_mu2
    num = (2*mu1_mu2 + C1) * (2*s12 + C2)
    den = (mu1_sq + mu2_sq + C1) * (s1 + s2 + C2)
    return float(np.mean(num / (den + 1e-8)))


def is_scene_cut(
    frame1: np.ndarray,
    frame2: np.ndarray,
    histogram_threshold: float = 0.4,
    ssim_threshold: float = 0.7
) -> Tuple[bool, float]:
    hist_diff = histogram_difference(frame1, frame2)
    ssim = ssim_score(frame1, frame2)
    hist_ok = hist_diff > histogram_threshold
    ssim_ok = ssim < ssim_threshold
    if hist_ok and ssim_ok:
        conf = min(1.0, (hist_diff/histogram_threshold + (1-ssim)/(1-ssim_threshold+1e-6)) / 2)
        return True, conf
    elif hist_ok:
        return True, hist_diff / histogram_threshold * 0.7
    elif ssim_ok:
        return True, (1-ssim) / (1-ssim_threshold+1e-6) * 0.6
    return False, 0.0
