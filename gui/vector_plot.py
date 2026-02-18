"""
Gráfico em tempo real do vetor de movimento.
Exibe ângulo (polar) e intensidade com mudança de cor ao ultrapassar o limiar de corte.
"""

import math
import numpy as np
from collections import deque
from typing import Optional

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPainterPath,
    QLinearGradient, QRadialGradient, QConicalGradient
)


class VectorPlotWidget(QWidget):
    """
    Widget que mostra dois gráficos:
    1. Polar (ângulo + magnitude em tempo real) — mostra a "rosa dos ventos" do movimento
    2. Histórico de magnitude ao longo do tempo com linha de corte colorida
    """

    def __init__(self, history_len: int = 120, parent=None):
        super().__init__(parent)
        self.history_len = history_len
        self.setMinimumSize(320, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Histórico
        self.angle_history: deque = deque(maxlen=history_len)
        self.magnitude_history: deque = deque(maxlen=history_len)
        self.cut_threshold: float = 3.0
        self.current_angle: float = 0.0
        self.current_magnitude: float = 0.0

        # Cores
        self.COLOR_BG = QColor(15, 17, 23)
        self.COLOR_GRID = QColor(40, 45, 60)
        self.COLOR_NORMAL = QColor(0, 200, 120)
        self.COLOR_CUT = QColor(255, 70, 70)
        self.COLOR_WARN = QColor(255, 180, 30)
        self.COLOR_TEXT = QColor(160, 170, 190)
        self.COLOR_VECTOR = QColor(80, 160, 255)

    def update_motion(self, angle: float, magnitude: float):
        """Atualiza com novos dados de fluxo óptico."""
        self.current_angle = angle
        self.current_magnitude = magnitude
        self.angle_history.append(angle)
        self.magnitude_history.append(magnitude)
        self.update()

    def set_cut_threshold(self, threshold: float):
        self.cut_threshold = threshold
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, self.COLOR_BG)

        half_w = w // 2
        # Divide horizontalmente: polar à esquerda, histórico à direita
        self._draw_polar(painter, 0, 0, half_w, h)
        self._draw_history(painter, half_w, 0, w - half_w, h)

    def _draw_polar(self, painter: QPainter, x: int, y: int, w: int, h: int):
        """Diagrama polar com ângulo e intensidade do movimento."""
        cx = x + w // 2
        cy = y + h // 2
        max_r = min(w, h) // 2 - 30

        # Título
        painter.setPen(QPen(self.COLOR_TEXT))
        font = QFont("Consolas", 8)
        painter.setFont(font)
        painter.drawText(x + 5, y + 14, "VETOR DE MOVIMENTO")

        # Círculos de referência
        for frac, label in [(0.33, ""), (0.66, ""), (1.0, "")]:
            r = int(max_r * frac)
            color = QColor(self.COLOR_GRID)
            painter.setPen(QPen(color, 1, Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(cx - r, cy - r, 2*r, 2*r)

        # Linhas de ângulo (8 direções)
        labels_8 = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]
        for i, lbl in enumerate(labels_8):
            angle_rad = math.radians(i * 45)
            ex = cx + int(max_r * math.cos(angle_rad))
            ey = cy - int(max_r * math.sin(angle_rad))
            painter.setPen(QPen(self.COLOR_GRID, 1))
            painter.drawLine(cx, cy, ex, ey)
            lx = cx + int((max_r + 14) * math.cos(angle_rad)) - 5
            ly = cy - int((max_r + 14) * math.sin(angle_rad)) + 5
            painter.setPen(QPen(self.COLOR_TEXT))
            painter.drawText(lx, ly, lbl)

        # Trilha histórica (últimos N vetores com fade)
        if len(self.angle_history) > 1:
            angles = list(self.angle_history)
            mags = list(self.magnitude_history)
            max_mag = max(mags) if mags else 1.0

            for i in range(1, len(angles)):
                alpha = int(200 * i / len(angles))
                mag_norm = min(1.0, mags[i] / (max_mag + 1e-6))
                r = int(max_r * mag_norm)

                angle_rad = math.radians(angles[i])
                px = cx + int(r * math.cos(angle_rad))
                py = cy - int(r * math.sin(angle_rad))

                # Cor muda conforme proximidade ao limiar
                if mags[i] >= self.cut_threshold:
                    color = QColor(self.COLOR_CUT)
                elif mags[i] >= self.cut_threshold * 0.7:
                    color = QColor(self.COLOR_WARN)
                else:
                    color = QColor(self.COLOR_NORMAL)
                color.setAlpha(alpha)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                dot_size = max(2, int(4 * mag_norm))
                painter.drawEllipse(px - dot_size//2, py - dot_size//2, dot_size, dot_size)

        # Vetor atual (seta grande)
        if self.current_magnitude > 0.1:
            mag_norm = min(1.0, self.current_magnitude / (self.cut_threshold * 1.5))
            r = int(max_r * mag_norm)
            angle_rad = math.radians(self.current_angle)
            ex = cx + int(r * math.cos(angle_rad))
            ey = cy - int(r * math.sin(angle_rad))

            if self.current_magnitude >= self.cut_threshold:
                arrow_color = self.COLOR_CUT
            elif self.current_magnitude >= self.cut_threshold * 0.7:
                arrow_color = self.COLOR_WARN
            else:
                arrow_color = self.COLOR_VECTOR

            painter.setPen(QPen(arrow_color, 2))
            painter.drawLine(cx, cy, ex, ey)

            # Ponta da seta
            arrow_len = 10
            arrow_angle = 25
            for sign in [1, -1]:
                tip_angle = angle_rad + math.pi + math.radians(sign * arrow_angle)
                tx = ex + int(arrow_len * math.cos(tip_angle))
                ty = ey - int(arrow_len * math.sin(tip_angle))
                painter.drawLine(ex, ey, tx, ty)

            # Ponto central
            painter.setBrush(QBrush(arrow_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(cx - 4, cy - 4, 8, 8)

        # Info numérica
        angle_str = f"{self.current_angle:.1f}°"
        mag_str = f"mag: {self.current_magnitude:.2f}"
        painter.setPen(QPen(self.COLOR_TEXT))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(x + 5, y + h - 18, angle_str)
        painter.drawText(x + 5, y + h - 5, mag_str)

    def _draw_history(self, painter: QPainter, x: int, y: int, w: int, h: int):
        """Gráfico de linha do histórico de magnitude com linha de corte."""
        margin = 28
        plot_x = x + margin
        plot_y = y + 20
        plot_w = w - margin - 8
        plot_h = h - 45

        # Título
        painter.setPen(QPen(self.COLOR_TEXT))
        painter.setFont(QFont("Consolas", 8))
        painter.drawText(x + 5, y + 14, "INTENSIDADE × TEMPO")

        # Fundo do plot
        painter.fillRect(plot_x, plot_y, plot_w, plot_h, QColor(20, 22, 30))

        # Grid horizontal
        mags = list(self.magnitude_history) if self.magnitude_history else [0]
        max_val = max(max(mags), self.cut_threshold * 1.3, 1.0)

        for frac in [0.25, 0.5, 0.75, 1.0]:
            gy = plot_y + plot_h - int(plot_h * frac)
            painter.setPen(QPen(self.COLOR_GRID, 1, Qt.PenStyle.DotLine))
            painter.drawLine(plot_x, gy, plot_x + plot_w, gy)
            val = max_val * frac
            painter.setPen(QPen(self.COLOR_TEXT))
            painter.setFont(QFont("Consolas", 7))
            painter.drawText(x + 2, gy + 4, f"{val:.1f}")

        # Linha de limiar de corte
        threshold_y = plot_y + plot_h - int(plot_h * min(1.0, self.cut_threshold / max_val))
        painter.setPen(QPen(self.COLOR_CUT, 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot_x, threshold_y, plot_x + plot_w, threshold_y)
        painter.setFont(QFont("Consolas", 7))
        painter.setPen(QPen(self.COLOR_CUT))
        painter.drawText(plot_x + plot_w - 30, threshold_y - 3, "CORTE")

        # Curva de magnitude
        if len(mags) > 1:
            n = len(mags)
            points_normal = []
            points_cut = []

            prev_pt = None
            for i, mag in enumerate(mags):
                px = plot_x + int(plot_w * i / (self.history_len - 1))
                py = plot_y + plot_h - int(plot_h * min(1.0, mag / max_val))
                pt = QPointF(px, py)

                if mag >= self.cut_threshold:
                    if prev_pt:
                        painter.setPen(QPen(self.COLOR_CUT, 2))
                        painter.drawLine(prev_pt, pt)
                    points_cut.append(pt)
                else:
                    ratio = mag / self.cut_threshold
                    if ratio > 0.7:
                        c = self.COLOR_WARN
                    else:
                        c = self.COLOR_NORMAL
                    if prev_pt:
                        painter.setPen(QPen(c, 2))
                        painter.drawLine(prev_pt, pt)

                prev_pt = pt

        # Linha vertical do momento atual
        if mags:
            curr_x = plot_x + plot_w - 1
            painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
            painter.drawLine(curr_x, plot_y, curr_x, plot_y + plot_h)

        # Valor atual destacado
        if mags:
            cur = mags[-1]
            cur_color = self.COLOR_CUT if cur >= self.cut_threshold else self.COLOR_NORMAL
            painter.setPen(QPen(cur_color))
            painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
            painter.drawText(x + 5, y + h - 5, f"atual: {cur:.2f}")
