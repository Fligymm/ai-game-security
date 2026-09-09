"""Validated schemas for offline trajectory behavior research."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Literal


TrajectorySource = Literal["human", "bot", "synthetic_adversarial"]
EventPhase = Literal[
    "reaction_phase",
    "coarse_move",
    "deceleration",
    "micro_correction",
    "pause",
]


@dataclass(frozen=True, slots=True)
class EventSegment:
    """Half-open time-series index interval: ``start_idx <= i < end_idx``."""

    phase: EventPhase
    start_idx: int
    end_idx: int

    def __post_init__(self) -> None:
        if self.start_idx < 0 or self.end_idx <= self.start_idx:
            raise ValueError("event segment must have 0 <= start_idx < end_idx")


@dataclass(frozen=True, slots=True)
class TrajectoryMetadata:
    session_id: str
    source: TrajectorySource
    target_distance_px: float
    target_size_px: float
    reaction_time_ms: float
    seed: int | None = None


@dataclass(frozen=True, slots=True)
class TrajectoryTimeSeries:
    timestamps: list[float]
    x: list[float]
    y: list[float]
    dx: list[int]
    dy: list[int]


@dataclass(slots=True)
class TrajectorySession:
    """One labeled trajectory session with metadata and event segments."""

    session_id: str
    source: TrajectorySource
    target_distance_px: float
    target_size_px: float
    reaction_time_ms: float
    timestamps: list[float] = field(default_factory=list)
    x: list[float] = field(default_factory=list)
    y: list[float] = field(default_factory=list)
    dx: list[int] = field(default_factory=list)
    dy: list[int] = field(default_factory=list)
    event_segments: list[EventSegment] = field(default_factory=list)
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.session_id:
            raise ValueError("session_id must not be empty")
        if self.source not in {"human", "bot", "synthetic_adversarial"}:
            raise ValueError(f"unsupported trajectory source: {self.source}")
        if self.target_distance_px < 0 or self.target_size_px < 0 or self.reaction_time_ms < 0:
            raise ValueError("trajectory metadata values must be non-negative")
        lengths = {len(self.timestamps), len(self.x), len(self.y), len(self.dx), len(self.dy)}
        if len(lengths) != 1:
            raise ValueError("timestamps, x, y, dx, and dy must have equal lengths")
        if any(current <= previous for previous, current in zip(self.timestamps, self.timestamps[1:])):
            raise ValueError("timestamps must be strictly increasing")
        if any(not isinstance(value, int) or isinstance(value, bool) for value in self.dx + self.dy):
            raise TypeError("dx and dy must contain integers")
        for segment in self.event_segments:
            if segment.end_idx > len(self.timestamps):
                raise ValueError("event segment exceeds trajectory length")

    def to_dict(self) -> dict[str, object]:
        return {
            "metadata": asdict(TrajectoryMetadata(
                self.session_id,
                self.source,
                self.target_distance_px,
                self.target_size_px,
                self.reaction_time_ms,
                self.seed,
            )),
            "time_series": asdict(TrajectoryTimeSeries(
                list(self.timestamps), list(self.x), list(self.y), list(self.dx), list(self.dy)
            )),
            "events": [asdict(event) for event in self.event_segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "TrajectorySession":
        """Load canonical nested JSON or the earlier flat representation."""
        if "metadata" not in data:
            return cls(
                session_id=str(data["session_id"]),
                source=data["source"],
                target_distance_px=float(data["target_distance_px"]),
                target_size_px=float(data["target_size_px"]),
                reaction_time_ms=float(data["reaction_time_ms"]),
                timestamps=[float(value) for value in data.get("timestamps", [])],
                x=[float(value) for value in data.get("x", [])],
                y=[float(value) for value in data.get("y", [])],
                dx=[int(value) for value in data.get("dx", [])],
                dy=[int(value) for value in data.get("dy", [])],
                event_segments=[EventSegment(**event) for event in data.get("event_segments", [])],
                seed=data.get("seed"),
            )
        metadata = data["metadata"]
        series = data["time_series"]
        return cls(
            session_id=str(metadata["session_id"]),
            source=metadata["source"],
            target_distance_px=float(metadata["target_distance_px"]),
            target_size_px=float(metadata["target_size_px"]),
            reaction_time_ms=float(metadata["reaction_time_ms"]),
            timestamps=[float(value) for value in series["timestamps"]],
            x=[float(value) for value in series["x"]],
            y=[float(value) for value in series["y"]],
            dx=[int(value) for value in series["dx"]],
            dy=[int(value) for value in series["dy"]],
            event_segments=[EventSegment(**event) for event in data.get("events", [])],
            seed=metadata.get("seed"),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> "TrajectorySession":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def frame_count(self) -> int:
        return len(self.timestamps)
