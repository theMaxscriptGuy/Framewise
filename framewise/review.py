from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class MarkupShape:
    shape: str
    points: List[List[float]]
    color: str = "#ff0000"
    width: int = 2


@dataclass
class FrameReview:
    comment: str = ""
    markups: List[MarkupShape] = field(default_factory=list)


@dataclass
class ReviewData:
    video_path: str
    fps: float
    frame_count: int
    frames: Dict[int, FrameReview] = field(default_factory=dict)

    def to_dict(self) -> dict:
        frames_payload = {}
        for index, data in self.frames.items():
            frames_payload[str(index)] = {
                "comment": data.comment,
                "markups": [markup.__dict__ for markup in data.markups],
            }
        return {
            "video_path": self.video_path,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "frames": frames_payload,
        }

    @staticmethod
    def from_dict(payload: dict) -> "ReviewData":
        frames_payload = payload.get("frames", {})
        frames: Dict[int, FrameReview] = {}
        for key, value in frames_payload.items():
            markups = []
            for markup in value.get("markups", []):
                markups.append(
                    MarkupShape(
                        shape=markup.get("shape", "pen"),
                        points=markup.get("points", []),
                        color=markup.get("color", "#ff0000"),
                        width=int(markup.get("width", 2)),
                    )
                )
            frames[int(key)] = FrameReview(
                comment=value.get("comment", ""),
                markups=markups,
            )
        return ReviewData(
            video_path=payload.get("video_path", ""),
            fps=float(payload.get("fps", 0.0)),
            frame_count=int(payload.get("frame_count", 0)),
            frames=frames,
        )


class ReviewSaver:
    @staticmethod
    def save(path: str, review: ReviewData) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(review.to_dict(), handle, indent=2)

    @staticmethod
    def load(path: str) -> ReviewData:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return ReviewData.from_dict(payload)


class ReviewStore:
    def __init__(self) -> None:
        self.review: Optional[ReviewData] = None

    def set_review(self, review: ReviewData) -> None:
        self.review = review

    def get_frame(self, index: int) -> FrameReview:
        if not self.review:
            raise RuntimeError("Review not initialized")
        if index not in self.review.frames:
            self.review.frames[index] = FrameReview()
        return self.review.frames[index]

    def update_comment(self, index: int, text: str) -> None:
        frame = self.get_frame(index)
        frame.comment = text

    def update_markups(self, index: int, markups: List[MarkupShape]) -> None:
        frame = self.get_frame(index)
        frame.markups = markups
