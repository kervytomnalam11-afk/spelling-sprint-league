# leaderboard.py — JSON-backed score storage
import json, os
from config import get_league

LEADERBOARD_FILE = "leaderboard.json"

def load() -> list:
    if os.path.exists(LEADERBOARD_FILE):
        try:
            with open(LEADERBOARD_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_score(name: str, wpm: float, accuracy: float, mode: str) -> dict:
    league_name, _, league_color = get_league(wpm)
    entry = {
        "name":     name[:16],
        "wpm":      round(wpm, 1),
        "accuracy": round(accuracy, 1),
        "mode":     mode,
        "league":   league_name,
    }
    data = load()
    data.append(entry)
    data.sort(key=lambda x: x["wpm"], reverse=True)
    data = data[:100]
    with open(LEADERBOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return entry

def top(limit: int = 15, mode: str = None) -> list:
    data = load()
    if mode:
        data = [e for e in data if e["mode"] == mode]
    return data[:limit]

def personal_best(name: str) -> dict | None:
    data = load()
    mine = [e for e in data if e["name"].lower() == name.lower()]
    return mine[0] if mine else None
