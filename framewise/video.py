from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class VideoInfo:
    path: str
    frame_count: int
    fps: float
    width: int
    height: int


class VideoLoader:
    def __init__(self) -> None:
        self._cap: Optional[cv2.VideoCapture] = None
        self.info: Optional[VideoInfo] = None
        self._last_index: Optional[int] = None
        self._last_frame: Optional[np.ndarray] = None

    def is_loaded(self) -> bool:
        return self._cap is not None and self.info is not None

    def load(self, path: str) -> VideoInfo:
        self.release()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise ValueError(f"Unable to open video: {path}")

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self._cap = cap
        self.info = VideoInfo(path=path, frame_count=frame_count, fps=fps, width=width, height=height)
        self._last_index = None
        self._last_frame = None
        return self.info

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
        self._cap = None
        self.info = None
        self._last_index = None
        self._last_frame = None

    def read_frame(self, index: int) -> Tuple[np.ndarray, int]:
        if not self._cap or not self.info:
            raise RuntimeError("Video not loaded")
        if index < 0 or index >= self.info.frame_count:
            raise IndexError("Frame index out of range")

        if self._last_index == index and self._last_frame is not None:
            return self._last_frame.copy(), index

        self._cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = self._cap.read()
        if not ok or frame is None:
            raise RuntimeError(f"Unable to read frame {index}")

        self._last_index = index
        self._last_frame = frame
        return frame.copy(), index
