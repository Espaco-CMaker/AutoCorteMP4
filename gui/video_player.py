"""
Player de vídeo embutido com marcações de corte sobrepostas.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSlider,
    QPushButton, QLabel, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QFont


class VideoCanvas(QWidget):
    """Área de renderização do frame de vídeo."""
    clicked_position = pyqtSignal(float)  # posição relativa (0-1) clicada

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap = None
        self._cut_markers: list = []       # timestamps normalizados (0-1)
        self._current_pos: float = 0.0
        self.setMinimumSize(400, 225)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #0a0b0e;")

    def set_frame(self, rgb_array: np.ndarray):
        h, w, ch = rgb_array.shape
        img = QImage(rgb_array.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        self.update()

    def set_cut_markers(self, normalized_positions: list):
        self._cut_markers = normalized_positions
        self.update()

    def set_current_position(self, pos: float):
        self._current_pos = pos
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(10, 11, 14))

        if self._pixmap:
            # Mantém aspect ratio
            scaled = self._pixmap.scaled(
                QSize(w, h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            ox = (w - scaled.width()) // 2
            oy = (h - scaled.height()) // 2
            painter.drawPixmap(ox, oy, scaled)

            # Marcadores de corte sobre o frame (linha vertical no topo)
            bar_h = 5
            for pos in self._cut_markers:
                bx = ox + int(scaled.width() * pos)
                painter.fillRect(bx - 1, oy, 3, bar_h, QColor(255, 70, 70))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_position.emit(event.position().x() / self.width())


class VideoPlayerWidget(QWidget):
    """Player de vídeo completo com controles e marcações de corte."""

    seek_requested = pyqtSignal(int)    # frame solicitado
    play_pause_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._total_frames = 1
        self._current_frame = 0
        self._is_playing = False
        self._cut_frames: list = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Canvas do vídeo
        self.canvas = VideoCanvas()
        layout.addWidget(self.canvas)

        # Barra de progresso / seek
        self.seek_bar = QSlider(Qt.Orientation.Horizontal)
        self.seek_bar.setRange(0, 1000)
        self.seek_bar.setValue(0)
        self.seek_bar.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px; background: #1e2030; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 14px; height: 14px; background: #4080ff;
                border-radius: 7px; margin: -4px 0;
            }
            QSlider::sub-page:horizontal {
                background: #3060cc; border-radius: 3px;
            }
        """)
        self.seek_bar.sliderMoved.connect(self._on_seek)
        layout.addWidget(self.seek_bar)

        # Controles
        controls = QHBoxLayout()
        controls.setSpacing(6)

        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedHeight(28)
        self.btn_play.setStyleSheet("""
            QPushButton {
                background: #1e2030; color: #c0c8e0;
                border: 1px solid #2a2f45; border-radius: 4px;
                padding: 0 12px; font-size: 12px;
            }
            QPushButton:hover { background: #252840; }
            QPushButton:pressed { background: #3060cc; }
        """)
        self.btn_play.clicked.connect(self._on_play_pause)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #6070a0; font-size: 11px; font-family: Consolas;")

        self.lbl_cuts = QLabel("0 cortes")
        self.lbl_cuts.setStyleSheet("color: #ff4646; font-size: 11px;")

        controls.addWidget(self.btn_play)
        controls.addWidget(self.lbl_time)
        controls.addStretch()
        controls.addWidget(self.lbl_cuts)
        layout.addLayout(controls)

    def load_video(self, total_frames: int, fps: float):
        self._total_frames = max(1, total_frames)
        self._fps = fps

    def update_frame(self, rgb_array: np.ndarray, frame_num: int, total_frames: int):
        self._current_frame = frame_num
        self._total_frames = total_frames
        self.canvas.set_frame(rgb_array)

        # Atualiza seek bar
        pos = int(1000 * frame_num / max(1, total_frames))
        self.seek_bar.blockSignals(True)
        self.seek_bar.setValue(pos)
        self.seek_bar.blockSignals(False)

        self.canvas.set_current_position(frame_num / max(1, total_frames))

        # Tempo
        fps = getattr(self, '_fps', 30.0)
        cur_sec = frame_num / fps
        tot_sec = total_frames / fps
        self.lbl_time.setText(f"{self._fmt(cur_sec)} / {self._fmt(tot_sec)}")

    def add_cut_marker(self, timestamp: float, total_duration: float):
        if total_duration > 0:
            self._cut_frames.append(timestamp / total_duration)
            self.canvas.set_cut_markers(self._cut_frames)
            self.lbl_cuts.setText(f"{len(self._cut_frames)} cortes")

    def clear_cuts(self):
        self._cut_frames.clear()
        self.canvas.set_cut_markers([])
        self.lbl_cuts.setText("0 cortes")

    def set_playing(self, playing: bool):
        self._is_playing = playing
        self.btn_play.setText("Pause" if self._is_playing else "Play")

    def _on_play_pause(self):
        self._is_playing = not self._is_playing
        self.btn_play.setText("Pause" if self._is_playing else "Play")
        self.play_pause_toggled.emit(self._is_playing)

    def _on_seek(self, value: int):
        frame = int(self._total_frames * value / 1000)
        self.seek_requested.emit(frame)

    def _fmt(self, seconds: float) -> str:
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"



