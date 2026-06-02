"""Persistent session logs for the desktop GUI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class GuiSessionLogger:
    """Append-only text log for one GUI process session."""

    path: Path

    @classmethod
    def create(cls, log_dir: str | Path = "data/gui_logs") -> "GuiSessionLogger":
        directory = Path(log_dir)
        directory.mkdir(parents=True, exist_ok=True)
        path = unique_session_log_path(directory)
        logger = cls(path=path)
        logger.write("GUI session started")
        return logger

    def write(self, message: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat(timespec="seconds")
        with self.path.open("a", encoding="utf-8") as handle:
            for line in str(message).splitlines() or [""]:
                handle.write(f"{timestamp} | {line}\n")

    def read_text(self) -> str:
        if not self.path.exists():
            return ""
        return self.path.read_text(encoding="utf-8")


def unique_session_log_path(log_dir: Path) -> Path:
    base = datetime.now().strftime("%Y%m%d_%H%M%S_gui_session")
    candidate = log_dir / f"{base}.log"
    if not candidate.exists():
        return candidate
    for suffix in range(2, 1000):
        candidate = log_dir / f"{base}_{suffix:02d}.log"
        if not candidate.exists():
            return candidate
    raise FileExistsError("Could not create a unique GUI session log path")
