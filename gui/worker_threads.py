"""
Threads de trabalho para análise e exportação em paralelo.
Usa QThread + sinais para comunicação segura com a GUI.
"""

import traceback
from typing import List, Dict, Any

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from analyzer.optical_flow import FrameMotion
from analyzer.cut_detector import CutDetector
from exporter.video_splitter import VideoSplitter


class AnalysisWorker(QThread):
    """Thread que analisa o vídeo e detecta pontos de corte."""

    # Sinais emitidos durante a análise
    progress = pyqtSignal(int, int, object)   # frame_atual, total_frames, FrameMotion
    analysis_frame = pyqtSignal(object, int, int)  # frame RGB atual da analise, frame_atual, total_frames
    cut_found = pyqtSignal(dict)              # informações do corte encontrado
    finished = pyqtSignal(list)              # lista completa de cut_points
    error = pyqtSignal(str)

    def __init__(self, video_path: str, config: dict):
        super().__init__()
        self.video_path = video_path
        self.config = config
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            detector = CutDetector(self.config)
            cut_points = []

            def on_progress(frame, total, motion):
                self.progress.emit(frame, total, motion)

            def on_stop():
                return self._stop

            # Monkey-patch para emitir sinal de corte encontrado em tempo real
            original_detect = detector.detect

            def detect_with_signal(video_path, progress_callback=None, stop_flag=None):
                import cv2
                from collections import deque
                from analyzer.optical_flow import compute_optical_flow, analyze_flow
                from analyzer.scene_change import is_scene_cut

                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    raise ValueError(f"Não foi possível abrir: {video_path}")

                fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

                local_cuts = []
                last_cut_frame = 0
                min_frames = int(detector.min_segment_duration * fps)

                angle_window = deque(maxlen=detector.window_size)
                mag_window = deque(maxlen=detector.window_size)
                dir_window = deque(maxlen=detector.window_size)

                ret, prev_frame = cap.read()
                if not ret:
                    cap.release()
                    return []

                prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
                frame_number = 1

                while True:
                    if self._stop:
                        break

                    for _ in range(detector.frame_skip):
                        cap.read()
                        frame_number += 1

                    ret, curr_frame = cap.read()
                    if not ret:
                        break

                    frame_number += 1
                    curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

                    flow = compute_optical_flow(prev_gray, curr_gray)
                    motion = analyze_flow(flow, detector.magnitude_threshold)

                    angle_window.append(motion.angle_degrees)
                    mag_window.append(motion.magnitude)
                    dir_window.append(motion.direction)

                    # Emite progresso para GUI
                    self.progress.emit(frame_number, total_frames, motion)
                    preview_rgb = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2RGB)
                    self.analysis_frame.emit(preview_rgb, frame_number, total_frames)

                    frames_since = frame_number - last_cut_frame
                    if frames_since >= min_frames and len(mag_window) >= detector.window_size:
                        cut_reason = None
                        confidence = 0.0

                        change = detector._detect_motion_change(angle_window, mag_window, dir_window)
                        if change["changed"]:
                            cut_reason = change["type"]
                            confidence = change["confidence"]

                        scene_cut, scene_conf = is_scene_cut(
                            prev_frame, curr_frame,
                            detector.histogram_threshold, detector.ssim_threshold
                        )
                        if scene_cut and scene_conf > confidence:
                            cut_reason = "corte_de_cena"
                            confidence = scene_conf

                        if cut_reason:
                            timestamp = frame_number / fps
                            cut_info = {
                                "frame": frame_number,
                                "timestamp": timestamp,
                                "type": cut_reason,
                                "confidence": confidence,
                                "angle": motion.angle_degrees,
                                "magnitude": motion.magnitude,
                                "direction": motion.direction.value
                            }
                            local_cuts.append(cut_info)
                            last_cut_frame = frame_number
                            angle_window.clear()
                            mag_window.clear()
                            dir_window.clear()

                            # Sinal em tempo real para a GUI
                            self.cut_found.emit(cut_info)

                    prev_frame = curr_frame
                    prev_gray = curr_gray

                cap.release()
                return local_cuts

            cut_points = detect_with_signal(self.video_path)
            self.finished.emit(cut_points)

        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


class ExportWorker(QThread):
    """Thread que exporta os segmentos de vídeo em paralelo."""

    segment_done = pyqtSignal(dict)   # info do segmento concluído (com thumbnail)
    progress = pyqtSignal(int, int)   # segmento_atual, total
    finished = pyqtSignal(list)       # lista de todos os segmentos
    error = pyqtSignal(str)

    def __init__(self, video_path: str, cut_points: list, output_dir: str, config: dict):
        super().__init__()
        self.video_path = video_path
        self.cut_points = cut_points
        self.output_dir = output_dir
        self.config = config
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            splitter = VideoSplitter(self.config)

            def on_segment(i, total, path, thumb):
                self.progress.emit(i, total)

            segments = splitter.split(
                self.video_path,
                self.cut_points,
                self.output_dir,
                progress_callback=on_segment,
                stop_flag=lambda: self._stop
            )

            for seg in segments:
                self.segment_done.emit(seg)

            self.finished.emit(segments)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


class VideoFrameWorker(QThread):
    """Thread que lê frames do vídeo para o player embutido."""

    frame_ready = pyqtSignal(np.ndarray, int, int)  # frame RGB, frame_num, total
    finished = pyqtSignal()

    def __init__(self, video_path: str, fps_limit: int = 30):
        super().__init__()
        self.video_path = video_path
        self.fps_limit = fps_limit
        self._stop = False
        self._paused = False
        self._seek_frame = None

    def stop(self):
        self._stop = True

    def pause(self, paused: bool):
        self._paused = paused

    def seek(self, frame_number: int):
        self._seek_frame = frame_number

    def run(self):
        import time
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            self.finished.emit()
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_delay = 1.0 / min(self.fps_limit, fps)

        while not self._stop:
            if self._seek_frame is not None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, self._seek_frame)
                self._seek_frame = None

            if self._paused:
                time.sleep(0.05)
                continue

            t_start = time.time()
            ret, frame = cap.read()
            if not ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_num = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self.frame_ready.emit(rgb, frame_num, total_frames)

            elapsed = time.time() - t_start
            sleep_time = max(0, frame_delay - elapsed)
            time.sleep(sleep_time)

        cap.release()
        self.finished.emit()


import cv2



