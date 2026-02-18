"""
Detector de cortes com suporte a 8 direções e ângulos contínuos.
Emite sinais de progresso para integração com a GUI.
"""

import cv2
import numpy as np
from collections import deque
from typing import List, Dict, Any, Optional, Callable

from .optical_flow import (
    compute_optical_flow, analyze_flow, angle_difference,
    MovementDirection, FrameMotion
)
from .scene_change import is_scene_cut


class CutDetector:
    def __init__(self, config: dict):
        self.config = config
        self.sensitivity = config["analysis"]["sensitivity"]
        self.frame_skip = config["analysis"]["frame_skip"]

        flow_cfg = config["optical_flow"]
        # Limiares ajustados pela sensibilidade
        self.magnitude_threshold = flow_cfg["magnitude_threshold"] / self.sensitivity
        self.angle_change_threshold = flow_cfg["angle_change_threshold"] / self.sensitivity
        self.stop_threshold = flow_cfg["stop_threshold"]
        self.window_size = flow_cfg["window_size"]

        scene_cfg = config["scene_change"]
        self.histogram_threshold = scene_cfg["histogram_threshold"] / self.sensitivity
        self.ssim_threshold = min(0.99, scene_cfg["ssim_threshold"] * self.sensitivity)

        self.min_segment_duration = config["export"]["min_segment_duration"]

    def detect(
        self,
        video_path: str,
        progress_callback: Optional[Callable[[int, int, FrameMotion], None]] = None,
        stop_flag: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Analisa o vídeo e retorna lista de cortes detectados.

        Args:
            progress_callback: função(frame_atual, total_frames, motion) chamada a cada frame
            stop_flag: função que retorna True para interromper análise
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Não foi possível abrir: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        cut_points = []
        last_cut_frame = 0
        min_frames_between_cuts = int(self.min_segment_duration * fps)

        angle_window = deque(maxlen=self.window_size)
        magnitude_window = deque(maxlen=self.window_size)
        direction_window = deque(maxlen=self.window_size)

        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            return []

        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        frame_number = 1

        while True:
            if stop_flag and stop_flag():
                break

            # Frame skip
            for _ in range(self.frame_skip):
                cap.read()
                frame_number += 1

            ret, curr_frame = cap.read()
            if not ret:
                break

            frame_number += 1
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

            # Fluxo óptico
            flow = compute_optical_flow(prev_gray, curr_gray)
            motion = analyze_flow(flow, self.magnitude_threshold)

            angle_window.append(motion.angle_degrees)
            magnitude_window.append(motion.magnitude)
            direction_window.append(motion.direction)

            # Callback de progresso com o FrameMotion atual
            if progress_callback:
                progress_callback(frame_number, total_frames, motion)

            frames_since_last_cut = frame_number - last_cut_frame
            if frames_since_last_cut < min_frames_between_cuts:
                prev_frame = curr_frame
                prev_gray = curr_gray
                continue

            cut_reason = None
            confidence = 0.0

            # --- Detectar mudança de movimento ---
            if len(magnitude_window) >= self.window_size:
                change = self._detect_motion_change(angle_window, magnitude_window, direction_window)
                if change["changed"]:
                    cut_reason = change["type"]
                    confidence = change["confidence"]

            # --- Corte brusco de cena ---
            scene_cut, scene_conf = is_scene_cut(
                prev_frame, curr_frame,
                self.histogram_threshold, self.ssim_threshold
            )
            if scene_cut and scene_conf > confidence:
                cut_reason = "corte_de_cena"
                confidence = scene_conf

            if cut_reason:
                timestamp = frame_number / fps
                cut_points.append({
                    "frame": frame_number,
                    "timestamp": timestamp,
                    "type": cut_reason,
                    "confidence": confidence,
                    "angle": motion.angle_degrees,
                    "magnitude": motion.magnitude,
                    "direction": motion.direction.value
                })
                last_cut_frame = frame_number
                angle_window.clear()
                magnitude_window.clear()
                direction_window.clear()

            prev_frame = curr_frame
            prev_gray = curr_gray

        cap.release()
        return cut_points

    def _detect_motion_change(
        self,
        angle_window: deque,
        magnitude_window: deque,
        direction_window: deque
    ) -> Dict[str, Any]:
        angles = list(angle_window)
        mags = list(magnitude_window)
        dirs = list(direction_window)

        half = len(angles) // 2
        mags_first = mags[:half]
        mags_second = mags[half:]
        angles_first = angles[:half]
        angles_second = angles[half:]

        mean_mag_first = np.mean(mags_first)
        mean_mag_second = np.mean(mags_second)

        # Ângulo médio circular por metade
        def circular_mean(ang_list):
            r = np.mean(np.exp(1j * np.radians(ang_list)))
            return float(np.degrees(np.angle(r)) % 360)

        def dominant_direction(d_list):
            d_list = [d for d in d_list if d != MovementDirection.NONE]
            return max(set(d_list), key=d_list.count) if d_list else MovementDirection.NONE

        angle_first = circular_mean(angles_first)
        angle_second = circular_mean(angles_second)
        dir_first = dominant_direction(dirs[:half])
        dir_second = dominant_direction(dirs[half:])

        # Parou
        if (mean_mag_first > self.magnitude_threshold * 1.5 and
                mean_mag_second < self.magnitude_threshold * self.stop_threshold):
            conf = min(1.0, mean_mag_first / (mean_mag_second + 0.1) / 8)
            return {"changed": True, "type": f"parada_{dir_first.value}", "confidence": conf}

        # Começou
        if (mean_mag_first < self.magnitude_threshold * self.stop_threshold and
                mean_mag_second > self.magnitude_threshold * 1.5):
            conf = min(1.0, mean_mag_second / (mean_mag_first + 0.1) / 8)
            return {"changed": True, "type": f"inicio_{dir_second.value}", "confidence": conf}

        # Mudança de ângulo (detecta diagonais e todas as transições)
        if (mean_mag_first > self.magnitude_threshold and
                mean_mag_second > self.magnitude_threshold):
            ang_diff = angle_difference(angle_first, angle_second)
            if ang_diff >= self.angle_change_threshold:
                conf = min(1.0, ang_diff / 180.0)
                type_str = f"mudança_{dir_first.value}_para_{dir_second.value}"
                return {"changed": True, "type": type_str, "confidence": conf}

        return {"changed": False, "type": None, "confidence": 0.0}
