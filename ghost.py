# ghost.py — Ghost race recording & playback
import json, os, time

GHOST_FILE = "ghost_save.json"

class GhostRecorder:
    """Records a player's run for later ghost playback."""

    def __init__(self):
        self.events: list[dict] = []
        self._start: float | None = None

    def start(self):
        self._start = time.time()
        self.events = []

    def record(self, word: str, correct: bool):
        if self._start is None:
            return
        self.events.append({
            "t": round(time.time() - self._start, 3),
            "w": word,
            "ok": correct,
        })

    def save(self, wpm: float, mode: str):
        data = {"wpm": wpm, "mode": mode, "events": self.events}
        with open(GHOST_FILE, "w") as f:
            json.dump(data, f)

    @staticmethod
    def exists() -> bool:
        return os.path.exists(GHOST_FILE)

    @staticmethod
    def load() -> dict | None:
        if not os.path.exists(GHOST_FILE):
            return None
        try:
            with open(GHOST_FILE) as f:
                return json.load(f)
        except Exception:
            return None


class GhostPlayer:
    """Replays a saved ghost run in real-time."""

    def __init__(self, data: dict):
        self.events     = data.get("events", [])
        self.saved_wpm  = data.get("wpm", 0)
        self.mode       = data.get("mode", "")
        self._ptr       = 0
        self._start: float | None = None
        self.words_done = 0
        self.current_wpm = 0.0

    def start(self):
        self._start = time.time()
        self._ptr = 0
        self.words_done = 0

    def update(self):
        if self._start is None:
            return
        elapsed = time.time() - self._start
        while self._ptr < len(self.events):
            ev = self.events[self._ptr]
            if ev["t"] > elapsed:
                break
            if ev["ok"]:
                self.words_done += 1
            self._ptr += 1
        if elapsed > 0:
            self.current_wpm = (self.words_done / elapsed) * 60

    @property
    def progress(self) -> float:
        """0–1 fraction of ghost events processed."""
        if not self.events:
            return 0.0
        return min(self._ptr / len(self.events), 1.0)
