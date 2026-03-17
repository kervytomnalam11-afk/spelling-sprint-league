# mobile_input.py — On-screen virtual keyboard + touch submit/backspace
"""
Drop-in mobile keyboard for Spelling Sprint League.

Usage
-----
    from mobile_input import MobileKeyboard

    kb = MobileKeyboard(screen_w, screen_h)

    # inside event loop
    events = kb.translate_events(pygame.event.get())
    for event in events:
        game_screen.handle(event)

    # inside draw loop (call LAST so it's on top)
    kb.draw(surface)
    kb.update(dt)

The keyboard fires synthetic pygame.KEYDOWN events with:
    event.key     = pygame.K_BACKSPACE | pygame.K_SPACE | pygame.K_a … z
    event.unicode = the character (empty for BACKSPACE/SPACE)
    event.mod     = 0
so your existing GameEngine.keydown() needs zero changes.
"""

import pygame
from config import (
    BG_PANEL, BG_CARD, BG_INPUT, CYAN, CYAN_DIM, PURPLE,
    ORANGE, RED, GREEN, OFF_WHITE, GRAY, LIGHT_GRAY, WHITE, BG
)
import ui

# ── layout ──────────────────────────────────────────────────────────────────

_ROWS = [
    list("qwertyuiop"),
    list("asdfghjkl"),
    list("zxcvbnm"),
]

_ACTION_KEYS = {
    "⌫":   (pygame.K_BACKSPACE, ""),
    "SPACE": (pygame.K_SPACE,     " "),
}


def _make_fake_event(key: int, unicode: str) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, {
        "key":     key,
        "unicode": unicode,
        "mod":     0,
        "scancode": 0,
    })


# ── MobileKeyboard ───────────────────────────────────────────────────────────

class MobileKeyboard:
    """
    Full QWERTY on-screen keyboard drawn at the bottom of the screen.
    Translates touch/click events into KEYDOWN events understood by GameEngine.
    """

    VISIBLE_H_FRAC = 0.42   # keyboard takes this fraction of screen height
    KEY_RADIUS     = 6

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.visible  = True
        self._keys:   list[dict] = []   # {rect, key, unicode, label, color}
        self._pressed_key: dict | None = None
        self._press_t: float = 0.0
        self._build_layout()

    # ── layout builder ───────────────────────────────────────────────────────

    def _build_layout(self):
        self._keys = []
        W, H     = self.screen_w, self.screen_h
        kb_h     = int(H * self.VISIBLE_H_FRAC)
        kb_top   = H - kb_h
        pad      = int(W * 0.01)

        row_count  = len(_ROWS) + 1   # +1 for action row
        row_h      = (kb_h - pad * (row_count + 1)) // row_count

        for row_idx, row in enumerate(_ROWS):
            n      = len(row)
            key_w  = (W - pad * (n + 1)) // n
            y      = kb_top + pad + row_idx * (row_h + pad)
            offset = (W - (n * key_w + (n - 1) * pad)) // 2
            for col_idx, ch in enumerate(row):
                x = offset + col_idx * (key_w + pad)
                self._keys.append({
                    "rect":    pygame.Rect(x, y, key_w, row_h),
                    "key":     getattr(pygame, f"K_{ch}"),
                    "unicode": ch,
                    "label":   ch.upper(),
                    "color":   BG_CARD,
                    "border":  CYAN_DIM,
                })

        # ── action row: ⌫  |  SPACE  |  ⌫ (mirror) ────────────────────────
        action_y = kb_top + pad + len(_ROWS) * (row_h + pad)
        bs_w     = int(W * 0.14)
        sp_w     = W - 2 * bs_w - 4 * pad

        # left backspace
        self._keys.append({
            "rect":    pygame.Rect(pad, action_y, bs_w, row_h),
            "key":     pygame.K_BACKSPACE,
            "unicode": "",
            "label":   "⌫",
            "color":   (40, 20, 50),
            "border":  PURPLE,
        })
        # space bar
        self._keys.append({
            "rect":    pygame.Rect(pad + bs_w + pad, action_y, sp_w, row_h),
            "key":     pygame.K_SPACE,
            "unicode": " ",
            "label":   "SUBMIT",
            "color":   (0, 40, 50),
            "border":  CYAN,
        })
        # right backspace (thumb-friendly)
        self._keys.append({
            "rect":    pygame.Rect(W - pad - bs_w, action_y, bs_w, row_h),
            "key":     pygame.K_BACKSPACE,
            "unicode": "",
            "label":   "⌫",
            "color":   (40, 20, 50),
            "border":  PURPLE,
        })

    # ── public API ───────────────────────────────────────────────────────────

    def resize(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self._build_layout()

    def translate_events(self, events: list) -> list:
        """
        Consume touch/click events that hit the keyboard area.
        Returns a (possibly augmented) event list where keyboard taps have been
        replaced by synthetic KEYDOWN events.
        """
        if not self.visible:
            return events

        out = []
        for event in events:
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                pos = self._get_pos(event)
                hit = self._hit_key(pos)
                if hit:
                    self._pressed_key = hit
                    self._press_t     = 0.12
                    out.append(_make_fake_event(hit["key"], hit["unicode"]))
                    continue   # don't pass the raw touch through
            out.append(event)
        return out

    def update(self, dt: float):
        if self._press_t > 0:
            self._press_t = max(0.0, self._press_t - dt)
        else:
            self._pressed_key = None

    def draw(self, surf: pygame.Surface):
        if not self.visible:
            return

        W, H   = self.screen_w, self.screen_h
        kb_top = H - int(H * self.VISIBLE_H_FRAC)

        # background panel
        kb_rect = pygame.Rect(0, kb_top, W, H - kb_top)
        s = pygame.Surface((kb_rect.width, kb_rect.height), pygame.SRCALPHA)
        s.fill((*BG, 230))
        surf.blit(s, kb_rect.topleft)
        pygame.draw.line(surf, CYAN_DIM, (0, kb_top), (W, kb_top), 1)

        f_small  = ui.font(max(10, int(self.screen_h * 0.028)))
        f_submit = ui.font(max(10, int(self.screen_h * 0.022)), bold=True)

        for k in self._keys:
            r       = k["rect"]
            pressed = self._pressed_key is k
            col     = k["color"]
            border  = k["border"]

            # pressed = slightly lighter + glow
            if pressed:
                col    = ui.lerp_color(col, WHITE, 0.3)
                border = WHITE

            # fill
            s2 = pygame.Surface((r.width, r.height), pygame.SRCALPHA)
            s2.fill((*col, 210))
            surf.blit(s2, r.topleft)
            pygame.draw.rect(surf, border, r, width=1, border_radius=self.KEY_RADIUS)

            # label
            lbl = k["label"]
            f   = f_submit if lbl in ("SUBMIT", "⌫") else f_small
            tc  = CYAN if lbl == "SUBMIT" else PURPLE if lbl == "⌫" else OFF_WHITE
            ui.draw_text(surf, lbl, f, tc,
                         r.centerx, r.centery, anchor="center", shadow=False)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _get_pos(event) -> tuple[int, int]:
        if event.type == pygame.FINGERDOWN:
            # FINGERDOWN coords are 0–1 fractions; we need display coords
            info = pygame.display.Info()
            return (int(event.x * info.current_w),
                    int(event.y * info.current_h))
        return event.pos

    def _hit_key(self, pos: tuple[int, int]) -> dict | None:
        for k in self._keys:
            if k["rect"].collidepoint(pos):
                return k
        return None


# ── SlidePanel ───────────────────────────────────────────────────────────────

class SlidePanel:
    """
    Tiny animated toggle button that shows/hides the keyboard.
    Draw it above the keyboard.
    """

    def __init__(self, keyboard: MobileKeyboard):
        self.kb  = keyboard
        self._t  = 0.0

    def handle(self, event) -> bool:
        """Returns True if consumed."""
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            pos = MobileKeyboard._get_pos(event)
            if self._rect().collidepoint(pos):
                self.kb.visible = not self.kb.visible
                return True
        return False

    def _rect(self) -> pygame.Rect:
        W, H   = self.kb.screen_w, self.kb.screen_h
        kb_top = H - int(H * MobileKeyboard.VISIBLE_H_FRAC)
        y      = kb_top - 28 if self.kb.visible else H - 28
        return pygame.Rect(W // 2 - 44, y, 88, 24)

    def update(self, dt):
        self._t = (self._t + dt) % 2.0

    def draw(self, surf):
        r   = self._rect()
        col = CYAN if self.kb.visible else GRAY
        s   = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        s.fill((*BG_PANEL, 200))
        surf.blit(s, r.topleft)
        pygame.draw.rect(surf, col, r, width=1, border_radius=4)
        lbl = "▼ hide" if self.kb.visible else "▲ keyboard"
        ui.draw_text(surf, lbl, ui.font(12), col,
                     r.centerx, r.centery, anchor="center", shadow=False)
