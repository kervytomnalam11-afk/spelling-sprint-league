# 🎮 Spelling Sprint League
**Rebuilt with Pygame — Unity-inspired dark neon UI**

---

## Setup

```bash
pip install pygame
python main.py
```

---

## Features

| Feature | Details |
|---|---|
| **Game Modes** | Burst (30s), Sprint (60s), Marathon (90s), Endless |
| **Difficulty** | Easy / Medium / Hard / Mixed (word randomizer) |
| **Live Stats** | WPM, Accuracy %, Streak counter, Progress bar |
| **League System** | Bronze → Silver → Gold → Platinum → Diamond |
| **Ghost Race** | Record your best run; race against it locally |
| **Local Multi** | 2 players on one keyboard (P1=normal, P2=numpad) |
| **WiFi Multi** | LAN multiplayer via TCP sockets (Host + Join) |
| **Leaderboard** | JSON-saved, filter by mode, top 100 scores |

---

## Controls

### Solo / Ghost Race
| Key | Action |
|---|---|
| Type letters | Fill current word |
| `SPACE` | Submit word |
| `BACKSPACE` | Delete last char |
| `ESC` | End game / back |

### Local Multiplayer
| Player | Keys |
|---|---|
| P1 | Normal keyboard |
| P2 | Numpad (KP_Enter = submit, KP_Period = backspace) |

### WiFi Multiplayer
1. **Host**: Main Menu → WiFi Multi → share your IP shown on screen → Start Game
2. **Guest**: Main Menu → WiFi Join → type host IP → Join

---

## File Structure

```
spelling_sprint_league/
├── main.py          ← Entry point + all game screens
├── config.py        ← Colors, constants, league thresholds
├── words.py         ← Word bank (Easy/Medium/Hard/Mixed)
├── leaderboard.py   ← JSON-backed score storage
├── ghost.py         ← Ghost recorder + playback engine
├── network.py       ← WiFi multi (TCP server/client)
├── ui.py            ← Buttons, panels, particles, timer ring
├── requirements.txt
└── README.md
```

---

## League Thresholds

| League | WPM Required |
|---|---|
| 🥉 Bronze | 0+ |
| 🥈 Silver | 30+ |
| 🥇 Gold | 50+ |
| 💎 Platinum | 70+ |
| 💠 Diamond | 90+ |
