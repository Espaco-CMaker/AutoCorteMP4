"""
Divide o vídeo usando ffmpeg e gera miniaturas dos segmentos.
"""

import os
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

import cv2
import numpy as np


class VideoSplitter:
    def __init__(self, config: dict):
        self.codec = config["export"].get("codec", "copy")
        self.output_format = config["export"].get("output_format", "mp4")
        self.ffmpeg_threads = int(config["export"].get("ffmpeg_threads", 0) or 0)
        self.thumb_w = config.get("ui", {}).get("thumbnail_width", 160)
        self.thumb_h = config.get("ui", {}).get("thumbnail_height", 90)

    def split(
        self,
        input_path: str,
        cut_points: List[Dict[str, Any]],
        output_dir: str,
        progress_callback: Optional[Callable[[int, int, str, np.ndarray], None]] = None,
        stop_flag: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Divide o vídeo e gera miniaturas.

        Args:
            progress_callback: função(segmento_atual, total, caminho, thumbnail_array)

        Returns:
            Lista de dicts com info de cada segmento
        """
        timestamps = [0.0] + [cp["timestamp"] for cp in cut_points]
        total_duration = self._get_duration(input_path)
        timestamps.append(total_duration)

        input_stem = Path(input_path).stem
        segments = []
        total = len(timestamps) - 1

        for i, (start, end) in enumerate(zip(timestamps[:-1], timestamps[1:]), 1):
            if stop_flag and stop_flag():
                break

            duration = end - start
            if duration < 0.1:
                continue

            filename = f"{input_stem}_segmento_{i:03d}.{self.output_format}"
            output_path = os.path.join(output_dir, filename)

            success = self._extract_segment(input_path, start, duration, output_path)

            thumbnail = None
            if success and os.path.exists(output_path):
                thumbnail = self._generate_thumbnail(output_path)

            seg_info = {
                "index": i,
                "path": output_path,
                "start": start,
                "end": end,
                "duration": duration,
                "success": success,
                "thumbnail": thumbnail,
                "cut_type": cut_points[i-1]["type"] if i <= len(cut_points) else "fim"
            }
            segments.append(seg_info)

            if progress_callback:
                progress_callback(i, total, output_path, thumbnail)

        return segments

    def _extract_segment(self, input_path: str, start: float, duration: float, output_path: str) -> bool:
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-i", input_path,
            "-t", f"{duration:.3f}",
        ]
        if self.ffmpeg_threads > 0:
            cmd.extend(["-threads", str(self.ffmpeg_threads)])
        cmd.extend([
            "-c", self.codec,
            "-avoid_negative_ts", "1",
            output_path
        ])
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _get_duration(self, video_path: str) -> float:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", video_path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return float(result.stdout.strip())
        except Exception:
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.release()
            return frames / fps

    def _generate_thumbnail(self, video_path: str) -> Optional[np.ndarray]:
        """Captura frame do meio do segmento como miniatura."""
        try:
            cap = cv2.VideoCapture(video_path)
            total = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 2)
            ret, frame = cap.read()
            cap.release()
            if ret:
                thumb = cv2.resize(frame, (self.thumb_w, self.thumb_h))
                return cv2.cvtColor(thumb, cv2.COLOR_BGR2RGB)
        except Exception:
            pass
        return None
