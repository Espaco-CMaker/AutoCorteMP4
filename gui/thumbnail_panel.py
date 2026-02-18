"""
Painel de miniaturas dos segmentos gerados.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QColor, QPainter, QFont, QPen


class ThumbnailCard(QFrame):
    """Cartão de miniatura de um único segmento."""
    clicked = pyqtSignal(str)  # emite o caminho do vídeo

    def __init__(self, seg_info: dict, parent=None):
        super().__init__(parent)
        self.video_path = seg_info.get("path", "")
        self.setFixedSize(170, 130)
        self.setStyleSheet("""
            QFrame {
                background: #13151f;
                border: 1px solid #1e2235;
                border-radius: 6px;
            }
            QFrame:hover {
                border: 1px solid #3060cc;
                background: #171928;
            }
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Miniatura
        self.lbl_thumb = QLabel()
        self.lbl_thumb.setFixedSize(162, 91)
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setStyleSheet("background: #0a0b0e; border-radius: 3px;")

        thumb = seg_info.get("thumbnail")
        if thumb is not None:
            self._set_thumbnail(thumb)
        else:
            self.lbl_thumb.setText("⏳")
            self.lbl_thumb.setStyleSheet(
                "background: #0a0b0e; border-radius: 3px; color: #404060; font-size: 20px;"
            )

        # Índice e duração
        idx = seg_info.get("index", "?")
        dur = seg_info.get("duration", 0)
        cut_type = seg_info.get("cut_type", "")

        lbl_info = QLabel(f"#{idx:03d}  {dur:.1f}s")
        lbl_info.setStyleSheet("color: #8090b0; font-size: 10px; font-family: Consolas;")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Tipo de corte (abreviado)
        short_type = self._shorten_type(cut_type)
        lbl_type = QLabel(short_type)
        lbl_type.setStyleSheet("color: #ff6060; font-size: 9px; font-family: Consolas;")
        lbl_type.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.lbl_thumb)
        layout.addWidget(lbl_info)
        layout.addWidget(lbl_type)

    def _set_thumbnail(self, rgb_array: np.ndarray):
        h, w, ch = rgb_array.shape
        img = QImage(rgb_array.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(img).scaled(
            162, 91,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.lbl_thumb.setPixmap(pixmap)

    def _shorten_type(self, t: str) -> str:
        mapping = {
            "corte_de_cena": "✂ cena",
            "parada": "⏹ parada",
            "inicio": "▶ início",
            "mudança": "↔ mudança",
            "fim": "🏁 fim",
        }
        for key, val in mapping.items():
            if key in t:
                return val
        return t[:18] if t else ""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.video_path)
        super().mousePressEvent(event)


class ThumbnailPanel(QWidget):
    """Painel horizontal com scroll mostrando as miniaturas de todos os segmentos."""
    segment_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(150)
        self.setStyleSheet("background: #0d0f17;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(0)

        # Header
        hdr = QLabel("  SEGMENTOS GERADOS")
        hdr.setStyleSheet("color: #404060; font-size: 9px; font-family: Consolas; letter-spacing: 2px;")
        outer.addWidget(hdr)

        # Scroll area
        self.scroll = QScrollArea()
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(False)
        self.scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:horizontal {
                height: 6px; background: #0d0f17;
            }
            QScrollBar::handle:horizontal {
                background: #2a2f45; border-radius: 3px; min-width: 20px;
            }
        """)

        self.container = QWidget()
        self.container.setStyleSheet("background: transparent;")
        self.cards_layout = QHBoxLayout(self.container)
        self.cards_layout.setContentsMargins(2, 2, 2, 2)
        self.cards_layout.setSpacing(6)
        self.cards_layout.addStretch()

        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll)

        self._card_count = 0

    def add_segment(self, seg_info: dict):
        """Adiciona cartão de miniatura ao painel."""
        card = ThumbnailCard(seg_info)
        card.clicked.connect(self.segment_clicked.emit)
        # Insere antes do stretch
        self.cards_layout.insertWidget(self._card_count, card)
        self._card_count += 1
        self.container.setFixedWidth(max(400, self._card_count * 178 + 20))

    def clear(self):
        while self._card_count > 0:
            item = self.cards_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
            self._card_count -= 1
