"""
Janela principal do Drone Cutter GUI.
Layout: Player | Gráfico de vetores | Painel de cortes
Barra inferior: sensibilidade + progresso + miniaturas
"""

import os
from pathlib import Path

import yaml
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QLabel, QSlider, QProgressBar,
    QFileDialog, QListWidget, QListWidgetItem, QGroupBox,
    QStatusBar, QFrame, QDoubleSpinBox, QMessageBox,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon

from .video_player import VideoPlayerWidget
from .vector_plot import VectorPlotWidget
from .thumbnail_panel import ThumbnailPanel
from .worker_threads import AnalysisWorker, ExportWorker, VideoFrameWorker


STYLE = """
QMainWindow, QWidget {
    background-color: #0d0f17;
    color: #c0c8e0;
    font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #1e2235;
    border-radius: 6px;
    margin-top: 8px;
    padding-top: 6px;
    color: #6070a0;
    font-size: 10px;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QPushButton {
    background: #1a1d2e;
    color: #c0c8e0;
    border: 1px solid #252840;
    border-radius: 5px;
    padding: 6px 16px;
    font-size: 12px;
}
QPushButton:hover { background: #1e2235; border-color: #3060cc; }
QPushButton:pressed { background: #3060cc; }
QPushButton:disabled { color: #404060; border-color: #1a1d2e; }
QPushButton#primary {
    background: #1e3a8a;
    border-color: #3060cc;
    color: #e0eaff;
    font-weight: bold;
}
QPushButton#primary:hover { background: #2550b0; }
QPushButton#danger {
    background: #3a1010;
    border-color: #cc3030;
    color: #ffb0b0;
}
QPushButton#danger:hover { background: #501515; }
QSlider::groove:horizontal {
    height: 4px; background: #1e2235; border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 16px; height: 16px; background: #4080ff;
    border-radius: 8px; margin: -6px 0;
}
QSlider::sub-page:horizontal { background: #3060cc; border-radius: 2px; }
QProgressBar {
    background: #1a1d2e;
    border: 1px solid #252840;
    border-radius: 4px;
    text-align: center;
    color: #8090c0;
    font-size: 11px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1e3a8a, stop:1 #4080ff);
    border-radius: 3px;
}
QListWidget {
    background: #0d0f17;
    border: 1px solid #1e2235;
    border-radius: 4px;
    color: #8090b0;
    font-size: 11px;
    font-family: Consolas;
}
QListWidget::item:selected { background: #1e2a50; color: #c0d0ff; }
QListWidget::item:hover { background: #141626; }
QLabel#section_title {
    color: #404060;
    font-size: 9px;
    letter-spacing: 2px;
    font-family: Consolas;
}
QStatusBar { background: #090b12; color: #404060; font-size: 11px; }
QSplitter::handle { background: #1e2235; width: 2px; height: 2px; }
"""


class MainWindow(QMainWindow):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.video_path: str = ""
        self.output_dir: str = ""
        self.cut_points: list = []
        self.video_fps: float = 30.0
        self.video_total_frames: int = 1
        self.video_duration: float = 0.0

        # Workers (threads)
        self._analysis_worker = None
        self._export_worker = None
        self._frame_worker = None

        self.setWindowTitle("🚁  Drone Cutter")
        self.setMinimumSize(1200, 750)
        self.setStyleSheet(STYLE)

        self._build_ui()
        self._connect_signals()
        self._apply_config_to_ui()

    # ──────────────────────────────────────────────
    # CONSTRUÇÃO DA UI
    # ──────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 4)
        root.setSpacing(6)

        # ── Toolbar superior ──────────────────────
        root.addLayout(self._build_toolbar())

        # ── Splitter principal ────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        # Coluna esquerda: player + gráfico
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.player = VideoPlayerWidget()
        left_layout.addWidget(self.player, stretch=3)

        self.vector_plot = VectorPlotWidget(
            history_len=self.config.get("ui", {}).get("vector_plot_history", 120)
        )
        self.vector_plot.setMinimumHeight(200)
        left_layout.addWidget(self.vector_plot, stretch=2)

        splitter.addWidget(left_col)

        # Coluna direita: controles + lista de cortes
        right_col = QWidget()
        right_col.setFixedWidth(290)
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(self._build_sensitivity_panel())
        right_layout.addWidget(self._build_actions_panel())
        right_layout.addWidget(self._build_cuts_list(), stretch=1)

        splitter.addWidget(right_col)
        splitter.setSizes([900, 290])
        root.addWidget(splitter, stretch=1)

        # ── Progresso ─────────────────────────────
        root.addLayout(self._build_progress_bar())

        # ── Painel de miniaturas ──────────────────
        self.thumb_panel = ThumbnailPanel()
        root.addWidget(self.thumb_panel)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Pronto. Abra um vídeo para começar.")

    def _build_toolbar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)

        self.btn_open = QPushButton("📂  Abrir Vídeo")
        self.btn_open.setObjectName("primary")
        self.btn_open.setFixedHeight(34)

        self.btn_output = QPushButton("📁  Pasta de Saída")
        self.btn_output.setFixedHeight(34)

        self.lbl_video = QLabel("Nenhum vídeo carregado")
        self.lbl_video.setStyleSheet("color: #404060; font-size: 11px;")
        self.lbl_video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        row.addWidget(self.btn_open)
        row.addWidget(self.btn_output)
        row.addWidget(self.lbl_video)
        return row

    def _build_sensitivity_panel(self) -> QGroupBox:
        box = QGroupBox("SENSIBILIDADE DE CORTE")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        # Slider principal
        self.lbl_sensitivity = QLabel("0.50")
        self.lbl_sensitivity.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.lbl_sensitivity.setStyleSheet("color: #4080ff; font-family: Consolas; font-weight: bold;")

        hdr = QHBoxLayout()
        lbl = QLabel("Sensibilidade")
        lbl.setStyleSheet("color: #8090b0;")
        hdr.addWidget(lbl)
        hdr.addWidget(self.lbl_sensitivity)
        layout.addLayout(hdr)

        self.slider_sensitivity = QSlider(Qt.Orientation.Horizontal)
        self.slider_sensitivity.setRange(1, 100)
        self.slider_sensitivity.setValue(50)
        self.slider_sensitivity.setTickInterval(10)
        layout.addWidget(self.slider_sensitivity)

        # Descrição do nível
        self.lbl_sens_desc = QLabel("Balanceado")
        self.lbl_sens_desc.setStyleSheet("color: #506080; font-size: 10px; font-style: italic;")
        layout.addWidget(self.lbl_sens_desc)

        # Duração mínima
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Dur. mínima (s):"))
        self.spin_min_dur = QDoubleSpinBox()
        self.spin_min_dur.setRange(0.1, 60.0)
        self.spin_min_dur.setValue(1.0)
        self.spin_min_dur.setSingleStep(0.5)
        self.spin_min_dur.setStyleSheet("""
            QDoubleSpinBox {
                background: #1a1d2e; border: 1px solid #252840;
                color: #c0c8e0; padding: 3px; border-radius: 3px;
            }
        """)
        dur_row.addWidget(self.spin_min_dur)
        layout.addLayout(dur_row)

        return box

    def _build_actions_panel(self) -> QGroupBox:
        box = QGroupBox("AÇÕES")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self.btn_analyze = QPushButton("🔍  Analisar Vídeo")
        self.btn_analyze.setObjectName("primary")
        self.btn_analyze.setEnabled(False)

        self.btn_export = QPushButton("✂️  Exportar Segmentos")
        self.btn_export.setEnabled(False)

        self.btn_stop = QPushButton("⏹  Parar")
        self.btn_stop.setObjectName("danger")
        self.btn_stop.setEnabled(False)

        self.btn_clear = QPushButton("🗑  Limpar")
        self.btn_clear.setEnabled(False)

        layout.addWidget(self.btn_analyze)
        layout.addWidget(self.btn_export)
        layout.addWidget(self.btn_stop)
        layout.addWidget(self.btn_clear)
        return box

    def _build_cuts_list(self) -> QGroupBox:
        box = QGroupBox("CORTES DETECTADOS")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 8, 4, 4)

        self.cuts_list = QListWidget()
        self.cuts_list.setAlternatingRowColors(True)
        self.cuts_list.setStyleSheet("""
            QListWidget { alternate-background-color: #0f1118; }
        """)
        layout.addWidget(self.cuts_list)
        return box

    def _build_progress_bar(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(2)

        row = QHBoxLayout()
        self.lbl_progress_title = QLabel("PROGRESSO")
        self.lbl_progress_title.setObjectName("section_title")
        self.lbl_progress_pct = QLabel("0%")
        self.lbl_progress_pct.setStyleSheet("color: #4080ff; font-family: Consolas; font-size: 11px;")
        row.addWidget(self.lbl_progress_title)
        row.addStretch()
        row.addWidget(self.lbl_progress_pct)
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setFormat("")
        layout.addWidget(self.progress_bar)

        return layout

    # ──────────────────────────────────────────────
    # CONEXÃO DE SINAIS
    # ──────────────────────────────────────────────

    def _connect_signals(self):
        self.btn_open.clicked.connect(self._open_video)
        self.btn_output.clicked.connect(self._choose_output)
        self.btn_analyze.clicked.connect(self._start_analysis)
        self.btn_export.clicked.connect(self._start_export)
        self.btn_stop.clicked.connect(self._stop_all)
        self.btn_clear.clicked.connect(self._clear_all)

        self.slider_sensitivity.valueChanged.connect(self._on_sensitivity_changed)
        self.spin_min_dur.valueChanged.connect(self._on_min_dur_changed)

        self.player.play_pause_toggled.connect(self._on_play_pause)
        self.player.seek_requested.connect(self._on_seek)
        self.thumb_panel.segment_clicked.connect(self._on_segment_clicked)

    def _apply_config_to_ui(self):
        sens = int(self.config["analysis"]["sensitivity"] * 100)
        self.slider_sensitivity.setValue(sens)
        self.spin_min_dur.setValue(self.config["export"]["min_segment_duration"])

    # ──────────────────────────────────────────────
    # SLOTS DE INTERFACE
    # ──────────────────────────────────────────────

    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Vídeo", "",
            "Vídeos (*.mp4 *.mov *.avi *.mkv *.m4v *.mts);;Todos (*)"
        )
        if not path:
            return
        self.video_path = path
        name = Path(path).name
        self.lbl_video.setText(name)
        self.status.showMessage(f"Vídeo carregado: {name}")

        # Info do vídeo
        import cv2
        cap = cv2.VideoCapture(path)
        self.video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.video_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_duration = self.video_total_frames / self.video_fps
        cap.release()

        self.player.load_video(self.video_total_frames, self.video_fps)

        # Inicia player de vídeo
        self._start_frame_worker()

        self.btn_analyze.setEnabled(True)
        self.btn_clear.setEnabled(True)

        if not self.output_dir:
            self.output_dir = str(Path(path).parent / "output")

    def _choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "Pasta de Saída", self.output_dir or "")
        if path:
            self.output_dir = path
            self.status.showMessage(f"Saída: {path}")

    def _on_sensitivity_changed(self, value: int):
        sens = value / 100.0
        self.config["analysis"]["sensitivity"] = sens
        self.lbl_sensitivity.setText(f"{sens:.2f}")

        # Atualiza limiar no gráfico
        threshold = self.config["optical_flow"]["magnitude_threshold"] / sens
        self.vector_plot.set_cut_threshold(threshold)

        # Descrição
        if sens < 0.3:
            desc = "Poucos cortes (conservador)"
        elif sens < 0.5:
            desc = "Cortes moderados"
        elif sens < 0.7:
            desc = "Balanceado"
        elif sens < 0.85:
            desc = "Sensível"
        else:
            desc = "Muito sensível (muitos cortes)"
        self.lbl_sens_desc.setText(desc)

    def _on_min_dur_changed(self, value: float):
        self.config["export"]["min_segment_duration"] = value

    def _on_play_pause(self, playing: bool):
        if self._frame_worker:
            self._frame_worker.pause(not playing)

    def _on_seek(self, frame: int):
        if self._frame_worker:
            self._frame_worker.seek(frame)

    def _on_segment_clicked(self, path: str):
        """Abre segmento clicado no player."""
        if os.path.exists(path):
            self._stop_frame_worker()
            self.video_path = path
            import cv2
            cap = cv2.VideoCapture(path)
            self.video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            self.video_total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            self.player.load_video(self.video_total_frames, self.video_fps)
            self._start_frame_worker()

    # ──────────────────────────────────────────────
    # ANÁLISE
    # ──────────────────────────────────────────────

    def _start_analysis(self):
        if not self.video_path:
            return
        self._set_busy(True, "Analisando vídeo...")
        self.cuts_list.clear()
        self.cut_points.clear()
        self.player.clear_cuts()
        self.thumb_panel.clear()

        self._analysis_worker = AnalysisWorker(self.video_path, self.config)
        self._analysis_worker.progress.connect(self._on_analysis_progress)
        self._analysis_worker.cut_found.connect(self._on_cut_found)
        self._analysis_worker.finished.connect(self._on_analysis_finished)
        self._analysis_worker.error.connect(self._on_error)
        self._analysis_worker.start()

    @pyqtSlot(int, int, object)
    def _on_analysis_progress(self, frame: int, total: int, motion):
        pct = int(100 * frame / max(1, total))
        self.progress_bar.setValue(pct)
        self.lbl_progress_pct.setText(f"{pct}%")

        # Atualiza gráfico de vetor em tempo real
        self.vector_plot.update_motion(motion.angle_degrees, motion.magnitude)

    @pyqtSlot(dict)
    def _on_cut_found(self, cut_info: dict):
        self.cut_points.append(cut_info)

        # Adiciona à lista
        ts = cut_info["timestamp"]
        cut_type = cut_info["type"].replace("_", " ")
        conf = cut_info["confidence"]
        item_text = f"  {ts:>7.2f}s  |  {cut_type[:28]:<28}  {conf:.0%}"
        item = QListWidgetItem(item_text)
        item.setForeground(QColor("#ff8080"))
        self.cuts_list.addItem(item)
        self.cuts_list.scrollToBottom()

        # Marcador no player
        self.player.add_cut_marker(ts, self.video_duration)
        self.status.showMessage(f"{len(self.cut_points)} cortes detectados | último: {ts:.2f}s — {cut_type}")

    @pyqtSlot(list)
    def _on_analysis_finished(self, cut_points: list):
        self.cut_points = cut_points
        n = len(cut_points)
        self.status.showMessage(f"✅ Análise concluída: {n} cortes, {n+1} segmentos")
        self._set_busy(False)
        self.btn_export.setEnabled(True)
        self.progress_bar.setValue(100)
        self.lbl_progress_pct.setText("100%")

    # ──────────────────────────────────────────────
    # EXPORTAÇÃO
    # ──────────────────────────────────────────────

    def _start_export(self):
        if not self.cut_points and len(self.cut_points) == 0:
            # Exporta vídeo inteiro
            pass

        os.makedirs(self.output_dir, exist_ok=True)
        self._set_busy(True, f"Exportando para {self.output_dir}...")
        self.progress_bar.setValue(0)
        self.thumb_panel.clear()

        self._export_worker = ExportWorker(
            self.video_path, self.cut_points, self.output_dir, self.config
        )
        self._export_worker.progress.connect(self._on_export_progress)
        self._export_worker.segment_done.connect(self._on_segment_done)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_error)
        self._export_worker.start()

    @pyqtSlot(int, int)
    def _on_export_progress(self, current: int, total: int):
        pct = int(100 * current / max(1, total))
        self.progress_bar.setValue(pct)
        self.lbl_progress_pct.setText(f"{pct}%")
        self.status.showMessage(f"Exportando segmento {current}/{total}...")

    @pyqtSlot(dict)
    def _on_segment_done(self, seg_info: dict):
        self.thumb_panel.add_segment(seg_info)

    @pyqtSlot(list)
    def _on_export_finished(self, segments: list):
        n = len(segments)
        self._set_busy(False)
        self.progress_bar.setValue(100)
        self.lbl_progress_pct.setText("100%")
        self.status.showMessage(f"✅ Exportação concluída: {n} segmentos salvos em {self.output_dir}")
        QMessageBox.information(
            self, "Exportação Concluída",
            f"{n} segmentos salvos em:\n{self.output_dir}"
        )

    # ──────────────────────────────────────────────
    # PLAYER DE VÍDEO (THREAD)
    # ──────────────────────────────────────────────

    def _start_frame_worker(self):
        self._stop_frame_worker()
        self._frame_worker = VideoFrameWorker(self.video_path, fps_limit=30)
        self._frame_worker.frame_ready.connect(self._on_frame_ready)
        self._frame_worker.start()
        self._frame_worker.pause(True)  # começa pausado

    def _stop_frame_worker(self):
        if self._frame_worker:
            self._frame_worker.stop()
            self._frame_worker.wait(1000)
            self._frame_worker = None

    @pyqtSlot(object, int, int)
    def _on_frame_ready(self, rgb, frame_num, total):
        self.player.update_frame(rgb, frame_num, total)

    # ──────────────────────────────────────────────
    # CONTROLES GERAIS
    # ──────────────────────────────────────────────

    def _stop_all(self):
        if self._analysis_worker and self._analysis_worker.isRunning():
            self._analysis_worker.stop()
        if self._export_worker and self._export_worker.isRunning():
            self._export_worker.stop()
        self._set_busy(False)
        self.status.showMessage("Operação interrompida.")

    def _clear_all(self):
        self.cut_points.clear()
        self.cuts_list.clear()
        self.player.clear_cuts()
        self.thumb_panel.clear()
        self.progress_bar.setValue(0)
        self.lbl_progress_pct.setText("0%")
        self.status.showMessage("Limpo.")
        self.btn_export.setEnabled(False)

    def _set_busy(self, busy: bool, msg: str = ""):
        self.btn_analyze.setEnabled(not busy and bool(self.video_path))
        self.btn_export.setEnabled(not busy and bool(self.cut_points))
        self.btn_stop.setEnabled(busy)
        self.btn_open.setEnabled(not busy)
        self.slider_sensitivity.setEnabled(not busy)
        self.spin_min_dur.setEnabled(not busy)
        if msg:
            self.status.showMessage(msg)

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._set_busy(False)
        self.status.showMessage(f"❌ Erro: {msg[:80]}")
        QMessageBox.critical(self, "Erro", msg)

    def closeEvent(self, event):
        self._stop_all()
        self._stop_frame_worker()
        event.accept()
