"""Explicit tkinter human trajectory sampler for local behavior research."""

from __future__ import annotations

import argparse
import math
import random
import time
import tkinter as tk
from pathlib import Path

from cv_agent.analytics import TrajectoryLogger


class HumanCaptureApp:
    def __init__(self, root: tk.Tk, *, sessions: int, output_dir: Path, seed: int | None) -> None:
        self.root = root
        self.sessions = int(sessions)
        self.output_dir = output_dir
        self.random = random.Random(seed)
        self.completed = 0
        self.target_radius = 14
        self.canvas = tk.Canvas(root, width=800, height=600, bg="#20242b", highlightthickness=0)
        self.canvas.pack()
        self.status = tk.Label(root, text="Move to the target and click it", anchor="w")
        self.status.pack(fill="x")
        self.target: tuple[float, float] | None = None
        self.appeared_at = 0.0
        self.last_time = 0.0
        self.last_x = 0.0
        self.last_y = 0.0
        self.first_move_index: int | None = None
        self.logger: TrajectoryLogger | None = None
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Button-1>", self.on_click)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        self.spawn_target()

    def spawn_target(self) -> None:
        if self.completed >= self.sessions:
            self.status.configure(text="Capture complete. You may close this window.")
            return
        self.canvas.delete("target")
        x = self.random.randint(40, 760)
        y = self.random.randint(40, 560)
        self.target = (float(x), float(y))
        now = time.perf_counter()
        self.appeared_at = now
        self.last_time = now
        pointer_x = float(self.canvas.winfo_pointerx())
        pointer_y = float(self.canvas.winfo_pointery())
        self.last_x, self.last_y = pointer_x, pointer_y
        distance = math.hypot(pointer_x - x, pointer_y - y)
        self.logger = TrajectoryLogger(
            session_id=f"human_{self.completed + 1:04d}_{int(now * 1000)}",
            source="human",
            target_distance_px=distance,
            target_size_px=float(self.target_radius * 2),
            reaction_time_ms=0.0,
            start_time=now,
        )
        self.logger.append_point(0.0, pointer_x, pointer_y, 0, 0)
        self.first_move_index = None
        self.canvas.create_oval(
            x - self.target_radius,
            y - self.target_radius,
            x + self.target_radius,
            y + self.target_radius,
            fill="#e5b84b",
            outline="#fff2b2",
            width=2,
            tags="target",
        )
        self.status.configure(text=f"Target {self.completed + 1}/{self.sessions}")

    def on_motion(self, event: tk.Event) -> None:
        if self.logger is None:
            return
        timestamp = time.perf_counter() - self.appeared_at
        x, y = float(event.x_root), float(event.y_root)
        dx, dy = int(round(x - self.last_x)), int(round(y - self.last_y))
        if dx or dy:
            if self.first_move_index is None:
                self.first_move_index = self.logger.frame_count
            self.logger.append_point(timestamp, x, y, dx, dy)
            self.last_x, self.last_y = x, y
            self.last_time = time.perf_counter()

    def on_click(self, event: tk.Event) -> None:
        if self.logger is None or self.target is None:
            return
        target_x, target_y = self.target
        if math.hypot(event.x - target_x, event.y - target_y) > self.target_radius:
            return
        timestamp = time.perf_counter() - self.appeared_at
        x, y = float(event.x_root), float(event.y_root)
        dx, dy = int(round(x - self.last_x)), int(round(y - self.last_y))
        if dx or dy:
            self.logger.append_point(timestamp, x, y, dx, dy)
        self.logger.reaction_time_ms = timestamp * 1000.0
        movement_index = self.first_move_index if self.first_move_index is not None else self.logger.frame_count
        self.logger.add_event("reaction_phase", 0, max(1, movement_index))
        self.logger.add_event("coarse_move", movement_index, self.logger.frame_count)
        output = self.output_dir / f"{self.logger.session_id}.json"
        self.logger.export_to_json(output)
        self.completed += 1
        self.logger = None
        self.root.after(150, self.spawn_target)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture explicit tkinter human trajectories")
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/human/trajectories"))
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.sessions < 1:
        raise ValueError("--sessions must be >= 1")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    root = tk.Tk()
    root.title("Human Trajectory Capture")
    HumanCaptureApp(root, sessions=args.sessions, output_dir=args.output_dir, seed=args.seed)
    root.mainloop()


if __name__ == "__main__":
    main()
