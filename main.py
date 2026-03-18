#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║         SPELLING SPRINT LEAGUE  —  main.py           ║
║   Rebuilt with Pygame + Unity-inspired dark UI        ║
╚══════════════════════════════════════════════════════╝
Screens / States
  MENU → MODE_SELECT → NAME → GAME → RESULTS → LEADERBOARD
                            ↘ GHOST_RACE
                            ↘ LOCAL_MULTI
                            ↘ WIFI_HOST / WIFI_JOIN
"""

import pygame, sys, time, math, random
import numpy as np
import struct
from enum import Enum, auto

import config as C
from config import *
from words import get_words
from sentences import get_sentences, sentences_to_words
import leaderboard as LB
from ghost import GhostRecorder, GhostPlayer
from network import NetHost, NetClient
import ui
from animation import AnimatedRaceTrack
from platform import IS_ANDROID
from mobile_input import MobileKeyboard, SlidePanel


# ── State IDs ─────────────────────────────────────────────────────────────────

class S(Enum):
    MENU        = auto()
    MODE_SELECT = auto()
    NAME_INPUT  = auto()
    GAME        = auto()
    GHOST_RACE  = auto()
    MULTI_LOBBY = auto()   # HOST or JOIN choice for all multiplayer
    LOCAL_MULTI = auto()   # host on local WiFi
    WIFI_JOIN   = auto()   # join via IP
    RESULTS     = auto()
    LEADERBOARD = auto()


# ─────────────────────────────────────────────────────────────────────────────
# ── Shared session object (passed between screens) ────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class Session:
    def __init__(self):
        self.reset()

    def reset(self):
        self.mode        = "Sprint"
        self.difficulty  = "Mixed"
        self.player_name = "Player"
        self.words:  list[str] = []
        self.wpm         = 0.0
        self.accuracy    = 0.0
        self.words_done  = 0
        self.result_mode = ""   # mode label for results


# ─────────────────────────────────────────────────────────────────────────────
# ── MENU ─────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class MenuScreen:
    def __init__(self, app):
        self.app   = app
        self.field = ui.ParticleField(70)
        CX = WIDTH  // 2
        self.title_y = HEIGHT // 4

        bw, bh, gap = 260, 50, 14
        bx = CX - bw // 2
        by = HEIGHT // 2 - 10

        self.btn_play  = ui.Button(bx, by,           bw, bh, "▶  PLAY",            C.CYAN)
        self.btn_ghost = ui.Button(bx, by+bh+gap,    bw, bh, "👻  GHOST RACE",     C.PURPLE)
        self.btn_multi = ui.Button(bx, by+(bh+gap)*2,bw, bh, "🌐  MULTIPLAYER",    C.ORANGE)
        self.btn_lb    = ui.Button(bx, by+(bh+gap)*3,bw, bh, "🏆  LEADERBOARD",    C.YELLOW)
        self.btn_quit  = ui.Button(bx, by+(bh+gap)*4,bw, bh, "✕  QUIT",            C.RED)
        self.buttons   = [self.btn_play, self.btn_ghost, self.btn_multi,
                          self.btn_lb, self.btn_quit]
        self._t = 0.0

    def handle(self, event):
        if self.btn_play .handle(event): self.app.go(S.MODE_SELECT)
        if self.btn_ghost.handle(event): self.app.go(S.GHOST_RACE)
        if self.btn_multi.handle(event): self.app.go(S.MULTI_LOBBY)
        if self.btn_lb   .handle(event): self.app.go(S.LEADERBOARD)
        if self.btn_quit .handle(event): sys.exit()

    def update(self, dt):
        self._t += dt
        self.field.update()

    def draw(self, surf):
        surf.fill(C.BG)
        self.field.draw(surf)
        # scanline tint
        tint = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        for y in range(0, HEIGHT, 4):
            tint.fill((0,0,0,18), (0, y, WIDTH, 1))
        surf.blit(tint, (0, 0))

        # title
        pulse = 0.5 + 0.5 * math.sin(self._t * 2)
        col   = ui.lerp_color(C.CYAN, C.PURPLE, pulse)
        ui.draw_glow_text(surf, "SPELLING SPRINT", ui.font(56, bold=True),
                          col, WIDTH//2, self.title_y - 20, anchor="center")
        ui.draw_glow_text(surf, "L E A G U E",     ui.font(28),
                          C.OFF_WHITE, WIDTH//2, self.title_y + 40, anchor="center")
        ui.draw_text(surf, "Type faster. Race harder. Climb the league.",
                     ui.font(16), C.GRAY,
                     WIDTH//2, self.title_y + 76, anchor="center", shadow=False)
        for b in self.buttons:
            b.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── MODE SELECT ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class ModeSelectScreen:
    # Card dimensions — sized to fit 3 per row with margins
    CW, CH   = 190, 110   # mode card  w, h
    DW, DH   = 270, 88    # diff card  w, h
    GAP      = 14

    def __init__(self, app):
        self.app  = app
        self.mode = None
        self.diff = None
        self._cards_mode = self._make_grid(
            list(C.GAME_MODES.items()),
            cols=3, cw=self.CW, ch=self.CH, top=180)
        self._cards_diff = self._make_grid(
            list(C.DIFFICULTIES.items()),
            cols=4, cw=self.DW, ch=self.DH, top=440)
        self.btn_back = ui.Button(40, HEIGHT-64, 120, 44, "◀ Back", C.GRAY)
        self.btn_next = ui.Button(WIDTH-160, HEIGHT-64, 130, 44, "NEXT ▶", C.CYAN)
        self.btn_next.enabled = False

    @classmethod
    def _make_grid(cls, items, cols, cw, ch, top):
        gap   = cls.GAP
        cards = []
        for i, (name, data) in enumerate(items):
            row = i // cols
            col = i  % cols
            n_this_row = min(cols, len(items) - row * cols)
            row_w = n_this_row * cw + (n_this_row - 1) * gap
            sx    = WIDTH // 2 - row_w // 2
            x     = sx + col * (cw + gap)
            y     = top + row * (ch + gap)
            cards.append({"name": name, "data": data,
                           "rect": pygame.Rect(x, y, cw, ch),
                           "hover": False, "selected": False})
        return cards

    def _pick(self, cards, pos):
        hit = None
        for c in cards:
            if c["rect"].collidepoint(pos):
                c["selected"] = True
                hit = c["name"]
            # keep previously selected ones selected
        return hit

    def _deselect_others(self, cards, chosen_name):
        for c in cards:
            c["selected"] = (c["name"] == chosen_name)

    def handle(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit_m = self._pick(self._cards_mode, event.pos)
            hit_d = self._pick(self._cards_diff, event.pos)
            if hit_m:
                self.mode = hit_m
                self._deselect_others(self._cards_mode, hit_m)
            if hit_d:
                self.diff = hit_d
                self._deselect_others(self._cards_diff, hit_d)
            self.btn_next.enabled = bool(self.mode and self.diff)
        if event.type == pygame.MOUSEMOTION:
            for c in self._cards_mode + self._cards_diff:
                c["hover"] = c["rect"].collidepoint(event.pos)
        if self.btn_back.handle(event): self.app.go(S.MENU)
        if self.btn_next.handle(event):
            self.app.session.mode       = self.mode
            self.app.session.difficulty = self.diff
            self.app.go(S.NAME_INPUT)

    def update(self, dt): pass

    def _draw_cards(self, surf, cards, label):
        top_y = cards[0]["rect"].y
        ui.draw_text(surf, label, ui.font(16, bold=True),
                     C.LIGHT_GRAY, WIDTH//2, top_y - 22, anchor="center")
        for c in cards:
            r   = c["rect"]
            col = c["data"]["color"]
            sel = c["selected"]
            hov = c["hover"] and not sel
            border = col if sel else (C.LIGHT_GRAY if hov else C.GRAY)
            ui.draw_panel(surf, r, border=border,
                          color=BG_CARD if sel else BG_PANEL)
            if sel:
                gs = ui.glow_surf(r.w, r.h, col, 14)
                surf.blit(gs, (r.x-14, r.y-14), special_flags=pygame.BLEND_RGBA_ADD)
            tc = col if sel else (C.OFF_WHITE if hov else C.LIGHT_GRAY)
            ui.draw_text(surf, c["name"], ui.font(17, bold=True),
                         tc, r.centerx, r.y + 28, anchor="center")
            data = c["data"]
            if "time" in data:
                t    = data["time"]
                tstr = f"{t}s" if t else "∞"
                ui.draw_text(surf, tstr, ui.font(13),
                             col if sel else C.GRAY,
                             r.centerx, r.y + 52, anchor="center", shadow=False)
            desc = data.get("desc", "")
            ui.draw_text(surf, desc, ui.font(12),
                         C.GRAY, r.centerx, r.y + 70,
                         anchor="center", shadow=False)

    def draw(self, surf):
        surf.fill(C.BG)
        ui.draw_glow_text(surf, "SELECT MODE & DIFFICULTY",
                          ui.font(28, bold=True), C.CYAN,
                          WIDTH//2, 80, anchor="center")
        ui.draw_text(surf, "Choose a game mode, then a difficulty — then hit NEXT",
                     ui.font(15), C.GRAY, WIDTH//2, 112,
                     anchor="center", shadow=False)
        self._draw_cards(surf, self._cards_mode, "GAME MODE")
        self._draw_cards(surf, self._cards_diff, "DIFFICULTY")
        # selection summary
        if self.mode or self.diff:
            summary = f"{self.mode or '—'}  ·  {self.diff or '—'}"
            ui.draw_text(surf, summary, ui.font(16), C.CYAN,
                         WIDTH//2, HEIGHT-76, anchor="center", shadow=False)
        self.btn_back.draw(surf)
        self.btn_next.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── NAME INPUT ───────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class NameInputScreen:
    def __init__(self, app):
        self.app    = app
        self.tinput = ui.TextInput(WIDTH//2-200, HEIGHT//2-30, 400, 56,
                                   placeholder="Enter your name…", max_len=16)
        self.tinput.active = True
        self.btn_go   = ui.Button(WIDTH//2-80,  HEIGHT//2+50, 160, 48, "LET'S GO!", C.CYAN)
        self.btn_back = ui.Button(40, HEIGHT-70, 120, 44, "◀ Back", C.GRAY)
        self._dt = 0.0

    def handle(self, event):
        self.tinput.handle(event)
        if self.btn_back.handle(event): self.app.go(S.MODE_SELECT)
        if self.btn_go.handle(event) or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN):
            name = self.tinput.text.strip() or "Player"
            self.app.session.player_name = name
            self.app.go(S.GAME)

    def update(self, dt):
        self._dt = dt

    def draw(self, surf):
        surf.fill(C.BG)
        CX = WIDTH // 2
        ui.draw_glow_text(surf, "WHAT'S YOUR NAME?",
                          ui.font(36, bold=True), C.CYAN, CX, HEIGHT//2 - 120, anchor="center")
        mode = self.app.session.mode
        diff = self.app.session.difficulty
        t    = C.GAME_MODES[mode]["time"]
        tstr = f"{t}s" if t else "∞"
        ui.draw_text(surf, f"{mode} ({tstr})  ·  {diff}", ui.font(18),
                     C.GRAY, CX, HEIGHT//2 - 70, anchor="center", shadow=False)
        self.tinput.draw(surf, self._dt)
        self.btn_go.draw(surf)
        self.btn_back.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── CORE GAME ENGINE (shared by solo, ghost, local multi) ────────────────────
# ─────────────────────────────────────────────────────────────────────────────

WORDS_VISIBLE = 8   # how many future words to show

class GameEngine:
    """
    Handles: word list, typed input, WPM, accuracy, streak, timing.
    Optionally tracks sentence boundaries for Sentence Race mode.
    Does NOT draw anything.
    """

    def __init__(self, words: list[str], time_limit: float,
                 recorder: GhostRecorder | None = None,
                 sentence_boundaries: list[int] | None = None,
                 raw_sentences: list[str] | None = None):
        self.words      = words
        self.time_limit = time_limit   # 0 = endless
        self.recorder   = recorder
        # sentence mode extras
        self.sentence_boundaries = sentence_boundaries or []
        self.raw_sentences       = raw_sentences or []
        self.is_sentence_mode    = bool(sentence_boundaries)

        self.word_idx   = 0
        self.typed      = ""
        self.started    = False
        self.finished   = False
        self._start_t   = 0.0
        self.elapsed    = 0.0

        self.correct_words     = 0
        self.total_chars       = 0
        self.correct_chars     = 0
        self.wrong_keys        = 0
        self.streak            = 0
        self.best_streak       = 0
        self.sentences_done    = 0   # sentence race counter

    # ── read-only properties ──────────────────────────────────────────────────

    @property
    def current_word(self) -> str:
        return self.words[self.word_idx] if self.word_idx < len(self.words) else ""

    @property
    def current_sentence_idx(self) -> int:
        """Which sentence we are currently inside (sentence mode only)."""
        for i, end in enumerate(self.sentence_boundaries):
            if self.word_idx <= end:
                return i
        return len(self.sentence_boundaries) - 1

    @property
    def current_sentence_text(self) -> str:
        """The full text of the active sentence."""
        idx = self.current_sentence_idx
        if idx < len(self.raw_sentences):
            return self.raw_sentences[idx]
        return ""

    @property
    def sentence_word_offset(self) -> int:
        """Index of the first word of the current sentence in self.words."""
        idx = self.current_sentence_idx
        if idx == 0:
            return 0
        return self.sentence_boundaries[idx - 1] + 1

    @property
    def wpm(self) -> float:
        if self.elapsed < 0.1:
            return 0.0
        return (self.correct_words / self.elapsed) * 60

    @property
    def accuracy(self) -> float:
        total = self.total_chars + self.wrong_keys
        if total == 0:
            return 100.0
        return 100.0 * self.total_chars / total

    @property
    def time_left(self) -> float:
        if not self.time_limit:
            return float("inf")
        return max(0.0, self.time_limit - self.elapsed)

    @property
    def time_frac(self) -> float:
        if not self.time_limit:
            return 1.0
        return self.time_left / self.time_limit

    @property
    def progress(self) -> float:
        return self.word_idx / max(1, len(self.words))

    # ── update ────────────────────────────────────────────────────────────────

    def update(self, dt):
        if self.started and not self.finished:
            self.elapsed = time.time() - self._start_t
            if self.time_limit and self.elapsed >= self.time_limit:
                self.finished = True

    def keydown(self, event) -> str | None:
        """
        TEXTINPUT handles ALL printable characters (desktop + Android).
        KEYDOWN only handles special keys: Escape, Backspace, Space.
        This prevents the double-letter bug where both events fire for the same keypress.
        """
        if self.finished:
            return None

        # ── TEXTINPUT: every printable character including space ──────────────
        if event.type == pygame.TEXTINPUT:
            text = event.text
            if not text:
                return None
            if not self.started:
                self.started  = True
                self._start_t = time.time()
                if self.recorder:
                    self.recorder.start()
            results = []
            for ch in text:
                r = self._process_char(ch)
                if r:
                    results.append(r)
            return results[-1] if results else None

        # ── KEYDOWN: special keys only — never printable chars ────────────────
        if event.type != pygame.KEYDOWN:
            return None

        if event.key == pygame.K_ESCAPE:
            return "escape"

        # Backspace — no TEXTINPUT equivalent on desktop
        if event.key == pygame.K_BACKSPACE:
            self.typed = self.typed[:-1]
            return None

        # Everything else (a-z, space, etc.) is handled by TEXTINPUT above.
        # Do NOT fall through to _process_char here — that causes double letters.
        return None

    def _process_char(self, ch: str) -> str | None:
        """Process a single typed character. Returns result or None."""
        cw = self.current_word
        if ch == " ":
            correct = self.typed == cw
            if self.recorder:
                self.recorder.record(cw, correct)
            if correct:
                self.correct_words += 1
                self.total_chars   += len(cw)
                self.streak        += 1
                self.best_streak    = max(self.best_streak, self.streak)
                self._advance()
                return "correct"
            else:
                self.wrong_keys += max(1, len(self.typed))
                self.streak      = 0
                self.typed = ""
                return "wrong"
        elif ch == "\b" or ch == "\x7f":   # backspace via TEXTINPUT
            self.typed = self.typed[:-1]
            return None
        else:
            self.typed += ch
            if len(self.typed) <= len(cw):
                if ch != cw[len(self.typed) - 1]:
                    self.wrong_keys += 1
            return None

    def _advance(self):
        prev_sent = self.current_sentence_idx
        self.typed     = ""
        self.word_idx += 1
        if self.word_idx >= len(self.words):
            self.finished = True
        elif self.is_sentence_mode:
            new_sent = self.current_sentence_idx
            if new_sent != prev_sent:
                self.sentences_done += 1

    # ── colour each letter of current word ───────────────────────────────────

    def letter_colors(self):
        cw = self.current_word
        cols = []
        for i, ch in enumerate(cw):
            if i < len(self.typed):
                cols.append(CORRECT_COL if self.typed[i] == ch else WRONG_COL)
            else:
                cols.append(PENDING_COL)
        return cols


# ─────────────────────────────────────────────────────────────────────────────
# ── GAME SCREEN (solo — all word modes + Sentence Race) ──────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class GameScreen:
    def __init__(self, app):
        self.app       = app
        self._flash_col = None
        self._flash_t   = 0.0
        self._eng: GameEngine | None = None
        self._track     = AnimatedRaceTrack(40, 430, WIDTH - 80)

    def enter(self):
        sess   = self.app.session
        mode   = sess.mode
        tlimit = C.GAME_MODES[mode]["time"]
        is_sent = C.GAME_MODES[mode].get("sentences", False)

        if is_sent:
            sents = get_sentences(40)
            words, boundaries = sentences_to_words(sents)
            rec = GhostRecorder()
            self._eng = GameEngine(words, tlimit, recorder=rec,
                                   sentence_boundaries=boundaries,
                                   raw_sentences=sents)
        else:
            words = get_words(sess.difficulty, count=200)
            rec   = GhostRecorder()
            self._eng = GameEngine(words, tlimit, recorder=rec)

        self._rec   = rec
        self._mode  = mode
        self._is_sent = is_sent
        self._flash_col = None
        self._flash_t   = 0.0

        # animated track: one lane for solo player
        self._track = AnimatedRaceTrack(40, 430, WIDTH - 80)
        mc = C.GAME_MODES[mode]["color"]
        self._track.add_lane(sess.player_name, mc)

    def handle(self, event):
        eng = self._eng
        # KEYDOWN (desktop) or TEXTINPUT (Android system keyboard)
        if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            result = eng.keydown(event)
            if result == "correct":
                self._flash_col = C.GREEN; self._flash_t = 0.22
            elif result == "wrong":
                self._flash_col = C.RED;   self._flash_t = 0.16
            elif result == "escape":
                self._finish()
        # On Android: tapping anywhere opens the system keyboard
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            if IS_ANDROID:
                pygame.key.start_text_input()
        if eng.finished:
            self._finish()

    def _finish(self):
        eng  = self._eng
        sess = self.app.session
        sess.wpm        = eng.wpm
        sess.accuracy   = eng.accuracy
        sess.words_done = eng.correct_words
        sess.result_mode = self._mode
        if eng.correct_words > 0:
            self._rec.save(eng.wpm, self._mode)
        self.app.go(S.RESULTS)

    def update(self, dt):
        if not self._eng:
            return
        self._eng.update(dt)
        if self._flash_t > 0:
            self._flash_t -= dt
        eng = self._eng
        self._track.set_lane(0, eng.progress, eng.wpm)
        self._track.update(dt)
        if eng.finished:
            self._finish()

    def draw(self, surf):
        if not self._eng:
            surf.fill(C.BG)
            ui.draw_glow_text(surf, "Loading…", ui.font(28), C.GRAY,
                              WIDTH//2, HEIGHT//2, anchor="center")
            return
        surf.fill(C.BG)
        eng = self._eng
        CX  = WIDTH // 2

        # flash overlay
        if self._flash_t > 0 and self._flash_col:
            frac = self._flash_t / 0.22
            ov   = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((*self._flash_col, int(40 * frac)))
            surf.blit(ov, (0, 0))

        # ── HUD ──────────────────────────────────────────────────────────────
        hud_r = pygame.Rect(40, 14, WIDTH - 80, 74)
        ui.draw_panel(surf, hud_r)

        ui.draw_glow_text(surf, f"{eng.wpm:.0f}", ui.font(38, bold=True),
                          C.CYAN, 120, 51, anchor="center")
        ui.draw_text(surf, "WPM", ui.font(13), C.GRAY, 120, 76, anchor="center")

        acc_col = C.GREEN if eng.accuracy >= 90 else C.ORANGE if eng.accuracy >= 75 else C.RED
        ui.draw_glow_text(surf, f"{eng.accuracy:.1f}%", ui.font(28, bold=True),
                          acc_col, 260, 48, anchor="center")
        ui.draw_text(surf, "ACCURACY", ui.font(11), C.GRAY, 260, 76, anchor="center")

        if eng.streak >= 3:
            sc = C.YELLOW if eng.streak >= 5 else C.ORANGE
            ui.draw_text(surf, f"🔥 x{eng.streak}", ui.font(20, bold=True),
                         sc, 390, 46, anchor="center")
            ui.draw_text(surf, "STREAK", ui.font(11), C.GRAY, 390, 74, anchor="center")

        score_lbl = "SENTENCES" if self._is_sent else "WORDS"
        score_val = eng.sentences_done if self._is_sent else eng.correct_words
        ui.draw_text(surf, f"{score_val}", ui.font(28, bold=True),
                     C.PURPLE, WIDTH - 200, 48, anchor="center")
        ui.draw_text(surf, score_lbl, ui.font(11), C.GRAY, WIDTH-200, 76, anchor="center")

        mc = C.GAME_MODES.get(self._mode, {}).get("color", C.CYAN)
        ui.draw_text(surf, self._mode.upper(), ui.font(13, bold=True),
                     mc, CX, 48, anchor="center")

        if eng.time_limit:
            ui.draw_timer_ring(surf, WIDTH - 76, 51, 34, eng.time_frac, thick=6)
            tl = eng.time_left
            tc = C.RED if tl < 10 else C.YELLOW if tl < 20 else C.CYAN
            ui.draw_text(surf, f"{int(tl)+1}", ui.font(16, bold=True),
                         tc, WIDTH-76, 51, anchor="center")
        else:
            ui.draw_text(surf, f"{int(eng.elapsed)}s", ui.font(16, bold=True),
                         C.CYAN, WIDTH - 76, 51, anchor="center")

        # ── word / sentence display ───────────────────────────────────────────
        wd_top = 100
        wd_h   = 300 if self._is_sent else 200
        wd_r   = pygame.Rect(60, wd_top, WIDTH - 120, wd_h)
        ui.draw_panel(surf, wd_r, border=C.PURPLE_DIM)

        if self._is_sent:
            _draw_sentence_area(surf, eng, wd_r)
        else:
            _draw_word_area_solo(surf, eng, CX, wd_r)

        # ── typed input ───────────────────────────────────────────────────────
        ti_y = wd_r.bottom + 10
        ti_r = pygame.Rect(CX - 320, ti_y, 640, 56)
        ui.draw_panel(surf, ti_r, color=C.BG_INPUT, border=C.CYAN_DIM)
        cw = eng.current_word
        typed_col = C.GREEN if eng.typed == cw[:len(eng.typed)] else C.RED
        ui.draw_text(surf, eng.typed or "start typing…",
                     ui.font(22), typed_col if eng.typed else C.GRAY,
                     ti_r.x + 14, ti_r.centery, anchor="midleft")

        # ── animated race track ───────────────────────────────────────────────
        self._track.draw(surf)

        # ── footer ────────────────────────────────────────────────────────────
        ui.draw_text(surf, "SPACE = submit  ·  BACKSPACE = delete  ·  ESC = quit",
                     ui.font(13), C.GRAY, CX, HEIGHT - 18, anchor="center", shadow=False)

        if not eng.started:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 130))
            surf.blit(ov, (0, 0))
            ui.draw_glow_text(surf, "START TYPING TO BEGIN",
                              ui.font(32, bold=True), C.CYAN,
                              CX, HEIGHT // 2, anchor="center")


# ─────────────────────────────────────────────────────────────────────────────
# ── Shared drawing helpers ────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def _draw_word_area_solo(surf, eng, CX, panel_rect):
    """Big current word + upcoming words — for word modes."""
    # upcoming (greyed out)
    upcoming = eng.words[eng.word_idx + 1: eng.word_idx + 7]
    x_up = CX + 30
    for w in upcoming:
        ui.draw_text(surf, w, ui.font(24), C.GRAY,
                     x_up, panel_rect.y + 60, anchor="midleft")
        x_up += ui.font(24).size(w)[0] + 12

    # current word letter-by-letter
    cw   = eng.current_word
    cols = eng.letter_colors()
    f_cw = ui.font(52, bold=True)
    total_w = sum(f_cw.size(ch)[0] for ch in cw)
    lx = CX - total_w // 2
    word_y = panel_rect.y + 100
    for ch, col in zip(cw, cols):
        img = f_cw.render(ch, True, col)
        surf.blit(img, (lx, word_y))
        lx += img.get_width()
    if len(eng.typed) < len(cw):
        tw = sum(f_cw.size(c)[0] for c in cw[:len(eng.typed)])
        cxp = CX - total_w // 2 + tw
        chw = f_cw.size(cw[len(eng.typed)])[0]
        pygame.draw.rect(surf, C.CURSOR_COL,
                         (cxp, word_y + f_cw.get_height() - 3, chw, 3))


def _draw_sentence_area(surf, eng, panel_rect):
    """Sentence Race: show the full sentence with words coloured by state."""
    sent_text = eng.current_sentence_text
    if not sent_text:
        return
    sent_words  = sent_text.split()
    offset      = eng.sentence_word_offset
    rel_idx     = eng.word_idx - offset   # which word within this sentence

    f_word  = ui.font(26, bold=True)
    f_done  = ui.font(26)
    pad     = 24
    x       = panel_rect.x + pad
    y_line  = panel_rect.y + 44
    line_h  = 40
    max_x   = panel_rect.right - pad

    for i, w in enumerate(sent_words):
        if i < rel_idx:
            col = C.GREEN      # done
            fnt = f_done
        elif i == rel_idx:
            col = C.CYAN       # active — colour letters individually below
            fnt = f_word
        else:
            col = C.GRAY       # upcoming
            fnt = f_done

        if i == rel_idx:
            # per-letter colouring on the active word
            letter_cols = eng.letter_colors()
            for j, ch in enumerate(w):
                lc  = letter_cols[j] if j < len(letter_cols) else C.GRAY
                img = fnt.render(ch, True, lc)
                if x + img.get_width() > max_x:
                    x = panel_rect.x + pad; y_line += line_h
                surf.blit(img, (x, y_line))
                x += img.get_width()
        else:
            img = fnt.render(w, True, col)
            if x + img.get_width() > max_x:
                x = panel_rect.x + pad; y_line += line_h
            surf.blit(img, (x, y_line))
            x += img.get_width()

        # space between words
        x += f_done.size(" ")[0]

    # sentence progress dots
    n_sents = len(eng.raw_sentences)
    done    = eng.sentences_done
    dot_y   = panel_rect.bottom - 22
    dot_cx  = panel_rect.centerx - min(n_sents, 20) * 10
    for i in range(min(n_sents, 20)):
        col  = C.GREEN if i < done else (C.CYAN if i == done else C.GRAY)
        r_   = 5 if i == done else 3
        pygame.draw.circle(surf, col, (dot_cx + i * 20, dot_y), r_)




class GhostRaceScreen:
    def __init__(self, app):
        self.app       = app
        self._eng:    GameEngine  | None = None
        self._ghost:  GhostPlayer | None = None
        self._no_ghost = False
        self._track    = AnimatedRaceTrack(40, 390, WIDTH - 80)
        self._flash_col = None
        self._flash_t   = 0.0

    def enter(self):
        ghost_data = GhostRecorder.load()
        if not ghost_data:
            self._no_ghost = True
            return
        self._no_ghost = False
        sess   = self.app.session
        mode   = ghost_data.get("mode", "Sprint")
        sess.mode = mode
        tlimit = C.GAME_MODES.get(mode, {}).get("time", 60)
        words  = get_words(sess.difficulty, count=200)
        self._eng   = GameEngine(words, tlimit)
        self._ghost = GhostPlayer(ghost_data)
        self._flash_col = None
        self._flash_t   = 0.0

        self._track = AnimatedRaceTrack(40, 390, WIDTH - 80)
        self._track.add_lane(sess.player_name, C.CYAN)
        self._track.add_lane(f"Ghost ({ghost_data.get('wpm', 0):.0f} wpm)", C.PURPLE, is_ghost=True)

    def handle(self, event):
        if self._no_ghost:
            if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                self.app.go(S.MENU)
            return
        if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            result = self._eng.keydown(event)
            if result == "correct":
                self._flash_col = C.GREEN; self._flash_t = 0.20
            elif result == "wrong":
                self._flash_col = C.RED;   self._flash_t = 0.14
            elif result == "escape":
                self.app.go(S.MENU)
        if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
            if IS_ANDROID:
                pygame.key.start_text_input()
        if self._eng and self._eng.started and self._ghost._start is None:
            self._ghost.start()

    def update(self, dt):
        if self._no_ghost or not self._eng:
            return
        self._eng.update(dt)
        self._ghost.update()
        if self._flash_t > 0:
            self._flash_t -= dt
        if self._eng.started and self._ghost._start is None:
            self._ghost.start()
        self._track.set_lane(0, self._eng.progress, self._eng.wpm)
        self._track.set_lane(1, self._ghost.progress, self._ghost.current_wpm)
        self._track.update(dt)
        if self._eng.finished:
            sess = self.app.session
            sess.wpm = self._eng.wpm; sess.accuracy = self._eng.accuracy
            sess.words_done = self._eng.correct_words
            sess.result_mode = self.app.session.mode
            self.app.go(S.RESULTS)

    def draw(self, surf):
        surf.fill(C.BG)
        if self._no_ghost:
            ui.draw_glow_text(surf, "No ghost saved yet!", ui.font(32, bold=True),
                              C.ORANGE, WIDTH//2, HEIGHT//2-40, anchor="center")
            ui.draw_text(surf, "Play a solo game first to record your ghost.",
                         ui.font(20), C.GRAY, WIDTH//2, HEIGHT//2+10, anchor="center", shadow=False)
            ui.draw_text(surf, "Press any key to return.", ui.font(16),
                         C.GRAY, WIDTH//2, HEIGHT//2+50, anchor="center", shadow=False)
            return
        if not self._eng:
            ui.draw_glow_text(surf, "Loading…", ui.font(28), C.GRAY,
                              WIDTH//2, HEIGHT//2, anchor="center")
            return

        eng   = self._eng
        ghost = self._ghost
        CX    = WIDTH // 2

        if self._flash_t > 0 and self._flash_col:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((*self._flash_col, int(35 * self._flash_t / 0.20)))
            surf.blit(ov, (0, 0))

        # header HUD
        hud_r = pygame.Rect(40, 14, WIDTH - 80, 60)
        ui.draw_panel(surf, hud_r)
        ui.draw_glow_text(surf, f"{eng.wpm:.0f}", ui.font(32, bold=True),
                          C.CYAN, 110, 44, anchor="center")
        ui.draw_text(surf, "YOUR WPM", ui.font(11), C.GRAY, 110, 65, anchor="center")
        ui.draw_glow_text(surf, f"{ghost.current_wpm:.0f}", ui.font(32, bold=True),
                          C.PURPLE, 260, 44, anchor="center")
        ui.draw_text(surf, "GHOST WPM", ui.font(11), C.GRAY, 260, 65, anchor="center")

        delta = eng.wpm - ghost.current_wpm
        dc    = C.GREEN if delta > 0 else C.RED if delta < 0 else C.GRAY
        ui.draw_text(surf, f"{delta:+.0f}", ui.font(24, bold=True), dc,
                     390, 44, anchor="center")
        ui.draw_text(surf, "DELTA", ui.font(11), C.GRAY, 390, 65, anchor="center")

        ui.draw_glow_text(surf, "GHOST RACE", ui.font(22, bold=True),
                          C.PURPLE, CX, 44, anchor="center")

        if eng.time_limit:
            ui.draw_timer_ring(surf, WIDTH - 60, 44, 28, eng.time_frac, thick=5)
            tl = eng.time_left
            tc = C.RED if tl < 10 else C.YELLOW if tl < 20 else C.CYAN
            ui.draw_text(surf, f"{int(tl)+1}", ui.font(14, bold=True),
                         tc, WIDTH-60, 44, anchor="center")

        # word area
        wd_r = pygame.Rect(60, 88, WIDTH - 120, 175)
        ui.draw_panel(surf, wd_r, border=C.PURPLE_DIM)
        _draw_word_area_solo(surf, eng, CX, wd_r)

        # typed input
        ti_r = pygame.Rect(CX-300, 278, 600, 52)
        ui.draw_panel(surf, ti_r, color=C.BG_INPUT, border=C.CYAN_DIM)
        cw = eng.current_word
        tcol = C.GREEN if eng.typed == cw[:len(eng.typed)] else C.RED
        ui.draw_text(surf, eng.typed or "start typing…",
                     ui.font(20), tcol if eng.typed else C.GRAY,
                     ti_r.x+12, ti_r.centery, anchor="midleft")

        # animated race track (two lanes)
        self._track.draw(surf)

        if not eng.started:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 130))
            surf.blit(ov, (0, 0))
            ui.draw_glow_text(surf, "TYPE TO START — RACE THE GHOST!",
                              ui.font(30, bold=True), C.PURPLE, CX, HEIGHT//2, anchor="center")



# ─────────────────────────────────────────────────────────────────────────────
# ── MULTI LOBBY — HOST or JOIN choice ────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class MultiLobbyScreen:
    """
    First screen for any multiplayer session.
    Everyone sees this — pick HOST to start a game, JOIN to enter a host's IP.

    HOST → LocalMultiScreen  (acts as server, others connect to your IP)
    JOIN → WifiJoinScreen    (enter the host's IP and connect)
    """

    def __init__(self, app):
        self.app = app
        CX = WIDTH // 2

        cw, ch = 340, 220
        gap = 40
        total = cw * 2 + gap
        lx = CX - total // 2
        rx = lx + cw + gap
        cy = HEIGHT // 2 - 60

        self.btn_host = ui.Button(lx, cy,        cw, ch, "HOST",  C.CYAN)
        self.btn_join = ui.Button(rx, cy,        cw, ch, "JOIN",  C.ORANGE)
        self.btn_back = ui.Button(40, HEIGHT-68, 120, 44, "◀ Back", C.GRAY)

    def handle(self, event):
        if self.btn_host.handle(event): self.app.go(S.LOCAL_MULTI)
        if self.btn_join.handle(event): self.app.go(S.WIFI_JOIN)
        if self.btn_back.handle(event): self.app.go(S.MENU)

    def update(self, dt): pass

    def draw(self, surf):
        surf.fill(C.BG)
        CX = WIDTH // 2

        ui.draw_glow_text(surf, "MULTIPLAYER", ui.font(36, bold=True),
                          C.ORANGE, CX, 80, anchor="center")
        ui.draw_text(surf, "Works on the same WiFi network — no internet needed",
                     ui.font(16), C.GRAY, CX, 118, anchor="center", shadow=False)

        # HOST card (left)
        hr = self.btn_host.rect
        ui.draw_panel(surf, hr, border=C.CYAN_DIM, color=C.BG_CARD)
        ui.draw_glow_text(surf, "HOST", ui.font(38, bold=True),
                          C.CYAN, hr.centerx, hr.y + 64, anchor="center")
        ui.draw_text(surf, "Start a game on", ui.font(15), C.GRAY,
                     hr.centerx, hr.y + 112, anchor="center", shadow=False)
        ui.draw_text(surf, "this device", ui.font(15), C.GRAY,
                     hr.centerx, hr.y + 132, anchor="center", shadow=False)
        ui.draw_text(surf, "Your IP is shown", ui.font(13), C.CYAN_DIM,
                     hr.centerx, hr.y + 162, anchor="center", shadow=False)
        ui.draw_text(surf, "for friends to connect", ui.font(13), C.CYAN_DIM,
                     hr.centerx, hr.y + 180, anchor="center", shadow=False)

        # JOIN card (right)
        jr = self.btn_join.rect
        ui.draw_panel(surf, jr, border=C.ORANGE, color=C.BG_CARD)
        ui.draw_glow_text(surf, "JOIN", ui.font(38, bold=True),
                          C.ORANGE, jr.centerx, jr.y + 64, anchor="center")
        ui.draw_text(surf, "Connect to a friend's", ui.font(15), C.GRAY,
                     jr.centerx, jr.y + 112, anchor="center", shadow=False)
        ui.draw_text(surf, "game by entering", ui.font(15), C.GRAY,
                     jr.centerx, jr.y + 132, anchor="center", shadow=False)
        ui.draw_text(surf, "their IP address", ui.font(13), C.ORANGE,
                     jr.centerx, jr.y + 162, anchor="center", shadow=False)
        ui.draw_text(surf, "(shown on their screen)", ui.font(13), C.ORANGE,
                     jr.centerx, jr.y + 180, anchor="center", shadow=False)

        # Tip at bottom
        ui.draw_text(surf,
                     "All players must be on the same WiFi — one person hosts, the rest join",
                     ui.font(14), C.GRAY, CX, HEIGHT - 50,
                     anchor="center", shadow=False)

        # Draw the actual buttons (invisible — cards above are the visual)
        # Just draw back button
        self.btn_back.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── LOCAL MULTIPLAYER ────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class LocalMultiScreen:
    """
    Local WiFi multiplayer — host on this device, friends join on the same network.
    Replaces the old same-keyboard numpad mode.
    """

    def __init__(self, app):
        self.app    = app
        self._host: NetHost | None = None
        self._eng:  GameEngine | None = None
        self._phase = "lobby"   # lobby | game | done
        self._track = AnimatedRaceTrack(40, 430, WIDTH - 80)
        CX = WIDTH // 2
        self.btn_start = ui.Button(CX - 110, HEIGHT - 90, 220, 50, "▶  START RACE", C.CYAN)
        self.btn_back  = ui.Button(40, HEIGHT - 68, 120, 44, "◀ Back", C.GRAY)

    def enter(self):
        if self._host:
            self._host.stop()
        self._host  = NetHost()
        self._host.start_server()
        self._phase = "lobby"
        self._eng   = None
        self._track = AnimatedRaceTrack(40, 430, WIDTH - 80)

    def _launch(self):
        sess   = self.app.session
        words  = get_words(sess.difficulty, count=200)
        tlimit = C.GAME_MODES[sess.mode]["time"]
        self._eng   = GameEngine(words, tlimit)
        self._host.send_start(words, sess.mode)
        self._phase = "game"
        # one lane per player (host first, then clients)
        self._track = AnimatedRaceTrack(40, 430, WIDTH - 80)
        self._track.add_lane(sess.player_name, C.CYAN)
        colors = [C.ORANGE, C.GREEN, C.PINK]
        for i, name in enumerate(self._host.names):
            self._track.add_lane(name, colors[i % len(colors)])

    def handle(self, event):
        if self.btn_back.handle(event):
            if self._host: self._host.stop()
            self.app.go(S.MULTI_LOBBY)
            return
        if self._phase == "lobby" and self.btn_start.handle(event):
            self._launch()
            return
        if self._phase == "game" and self._eng:
            result = self._eng.keydown(event) if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT) else None
            if result == "escape":
                if self._host: self._host.stop()
                self.app.go(S.MENU)

    def update(self, dt):
        if self._phase != "game" or not self._eng:
            return
        self._eng.update(dt)
        self._host.send_progress(self._eng.correct_words, self._eng.accuracy)
        self._track.set_lane(0, self._eng.progress, self._eng.wpm)
        for i, prog in enumerate(self._host.progress):
            wd  = prog.get("words_done", 0)
            wpm = wd / max(self._eng.elapsed, 0.1) * 60
            self._track.set_lane(i + 1, wd / max(len(self._eng.words), 1), wpm)
        self._track.update(dt)
        if self._eng.finished:
            sess = self.app.session
            sess.wpm = self._eng.wpm; sess.accuracy = self._eng.accuracy
            sess.words_done = self._eng.correct_words
            sess.result_mode = sess.mode
            if self._host: self._host.stop()
            self.app.go(S.RESULTS)

    def draw(self, surf):
        surf.fill(C.BG)
        CX = WIDTH // 2
        mc = C.GAME_MODES.get(self.app.session.mode, {}).get("color", C.CYAN)
        ui.draw_glow_text(surf, "LOCAL WiFi RACE", ui.font(30, bold=True),
                          mc, CX, 40, anchor="center")

        if self._phase == "lobby" and self._host:
            # IP panel
            ip_panel = pygame.Rect(CX - 300, 90, 600, 130)
            ui.draw_panel(surf, ip_panel, border=C.CYAN_DIM)
            ui.draw_text(surf, "Players on the same WiFi: open the game and tap JOIN",
                         ui.font(15), C.GRAY, CX, 112, anchor="center", shadow=False)
            ui.draw_glow_text(surf, f"{self._host.ip}",
                              ui.font(36, bold=True), C.CYAN, CX, 160, anchor="center")
            ui.draw_text(surf, f"port  {NET_PORT}",
                         ui.font(14), C.GRAY, CX, 192, anchor="center", shadow=False)

            # player slots
            slots_y = 250
            ui.draw_text(surf, "Connected players:", ui.font(16, bold=True),
                         C.LIGHT_GRAY, CX, slots_y, anchor="center")
            # host slot (always present)
            slot_r = pygame.Rect(CX - 180, slots_y + 24, 360, 40)
            ui.draw_panel(surf, slot_r, border=C.CYAN_DIM)
            ui.draw_text(surf, f"★  {self.app.session.player_name}  (host)",
                         ui.font(16), C.CYAN, slot_r.centerx, slot_r.centery,
                         anchor="center")
            colors = [C.ORANGE, C.GREEN, C.PINK]
            for i, name in enumerate(self._host.names):
                sy = slots_y + 24 + (i + 1) * 48
                sr = pygame.Rect(CX - 180, sy, 360, 40)
                ui.draw_panel(surf, sr, border=colors[i % len(colors)])
                ui.draw_text(surf, f"●  {name}",
                             ui.font(16), colors[i % len(colors)],
                             sr.centerx, sr.centery, anchor="center")

            connected_txt = f"{self._host.client_count} player{'s' if self._host.client_count != 1 else ''} joined"
            ui.draw_text(surf, connected_txt, ui.font(14), C.ORANGE,
                         CX, slots_y + 24 + (max(1, self._host.client_count + 1)) * 48 + 16,
                         anchor="center", shadow=False)
            self.btn_start.draw(surf)

        else:
            # In-game view
            eng = self._eng
            if not eng:
                self.btn_back.draw(surf)
                return
            hud_r = pygame.Rect(40, 80, WIDTH - 80, 60)
            ui.draw_panel(surf, hud_r)
            ui.draw_glow_text(surf, f"{eng.wpm:.0f}", ui.font(32, bold=True),
                              C.CYAN, 120, 110, anchor="center")
            ui.draw_text(surf, "WPM", ui.font(12), C.GRAY, 120, 132, anchor="center")
            acc_col = C.GREEN if eng.accuracy >= 90 else C.ORANGE if eng.accuracy >= 75 else C.RED
            ui.draw_glow_text(surf, f"{eng.accuracy:.1f}%", ui.font(26, bold=True),
                              acc_col, 270, 108, anchor="center")
            ui.draw_text(surf, "ACCURACY", ui.font(11), C.GRAY, 270, 132, anchor="center")
            if eng.streak >= 3:
                sc = C.YELLOW if eng.streak >= 5 else C.ORANGE
                ui.draw_text(surf, f"🔥 x{eng.streak}", ui.font(18, bold=True),
                             sc, 410, 108, anchor="center")
            if eng.time_limit:
                ui.draw_timer_ring(surf, WIDTH - 60, 110, 28, eng.time_frac, thick=5)
                tl = eng.time_left
                tc = C.RED if tl < 10 else C.YELLOW if tl < 20 else C.CYAN
                ui.draw_text(surf, f"{int(tl)+1}", ui.font(14, bold=True),
                             tc, WIDTH - 60, 110, anchor="center")
            # word area
            wd_r = pygame.Rect(60, 156, WIDTH - 120, 160)
            ui.draw_panel(surf, wd_r, border=C.PURPLE_DIM)
            _draw_word_area_solo(surf, eng, CX, wd_r)
            # input
            ti_r = pygame.Rect(CX - 280, 328, 560, 48)
            ui.draw_panel(surf, ti_r, color=C.BG_INPUT, border=C.CYAN_DIM)
            cw = eng.current_word
            tcol = C.GREEN if eng.typed == cw[:len(eng.typed)] else C.RED
            ui.draw_text(surf, eng.typed or "start typing…",
                         ui.font(20), tcol if eng.typed else C.GRAY,
                         ti_r.x + 12, ti_r.centery, anchor="midleft")
            # animated track
            self._track.draw(surf)

        self.btn_back.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── WIFI JOIN (Client/Join) ───────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class WifiJoinScreen:
    def __init__(self, app):
        self.app    = app
        self._client: NetClient | None = None
        self._eng:    GameEngine | None = None
        self._phase  = "input"
        self._error  = ""
        self._track  = AnimatedRaceTrack(40, 430, WIDTH - 80)
        CX = WIDTH // 2
        self.ip_input = ui.TextInput(CX-200, 260, 400, 52,
                                     placeholder="Host IP (e.g. 192.168.1.10)", max_len=20)
        self.btn_join = ui.Button(CX-90, 335, 180, 48, "JOIN", C.GREEN)
        self.btn_back = ui.Button(40, HEIGHT-70, 120, 44, "◀ Back", C.GRAY)
        self._dt = 0.0

    def enter(self):
        self._phase  = "input"
        self._client = None
        self._eng    = None
        self._error  = ""
        self._track  = AnimatedRaceTrack(40, 430, WIDTH - 80)
        self.ip_input.text = ""

    def _do_join(self):
        ip   = self.ip_input.text.strip()
        name = self.app.session.player_name
        self._client = NetClient()
        ok = self._client.connect(ip, name)
        if ok:
            self._phase = "wait"
        else:
            self._phase = "error"
            self._error = f"Could not connect to {ip}:{NET_PORT}"

    def handle(self, event):
        self.ip_input.handle(event)
        if self.btn_back.handle(event):
            if self._client: self._client.disconnect()
            self.app.go(S.MULTI_LOBBY)
        if self._phase == "input" and self.btn_join.handle(event):
            self._do_join()
        if self._phase == "game" and self._eng:
            if event.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
                result = self._eng.keydown(event)
                if result == "escape":
                    if self._client: self._client.disconnect()
                    self.app.go(S.MENU)
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN) and IS_ANDROID:
                pygame.key.start_text_input()

    def update(self, dt):
        self._dt = dt
        if self._client:
            while not self._client.in_queue.empty():
                msg = self._client.in_queue.get()
                if msg.get("type") == "start" and self._phase == "wait":
                    words  = self._client.words
                    mode   = self._client.mode
                    tlimit = C.GAME_MODES.get(mode, {}).get("time", 60)
                    self._eng = GameEngine(words, tlimit)
                    self.app.session.mode = mode
                    self._phase = "game"
                    # build lanes: self first, then host/opponents
                    self._track = AnimatedRaceTrack(40, 430, WIDTH - 80)
                    self._track.add_lane(self.app.session.player_name, C.CYAN)
                    self._track.add_lane("Host", C.GREEN)
                    for opp in self._client.opponents:
                        self._track.add_lane(opp, C.ORANGE)

        if self._phase == "game" and self._eng:
            self._eng.update(dt)
            self._client.send_progress(self._eng.correct_words, self._eng.accuracy)
            # update lanes
            self._track.set_lane(0, self._eng.progress, self._eng.wpm)
            for i, opp_data in enumerate(self._client.opponents.values()):
                wd  = opp_data.get("words_done", 0)
                wpm = wd / max(self._eng.elapsed, 0.1) * 60
                self._track.set_lane(i + 1, wd / max(len(self._eng.words), 1), wpm)
            self._track.update(dt)
            if self._eng.finished:
                sess = self.app.session
                self._client.send_finish(sess.player_name, self._eng.wpm, self._eng.accuracy)
                sess.wpm = self._eng.wpm; sess.accuracy = self._eng.accuracy
                sess.words_done = self._eng.correct_words
                self.app.go(S.RESULTS)

    def draw(self, surf):
        surf.fill(C.BG)
        CX = WIDTH // 2
        ui.draw_glow_text(surf, "WIFI MULTI — JOIN", ui.font(32, bold=True),
                          C.GREEN, CX, 44, anchor="center")

        if self._phase == "input":
            ui.draw_text(surf, "Enter the host's IP address:", ui.font(20),
                         C.LIGHT_GRAY, CX, 210, anchor="center")
            self.ip_input.draw(surf, self._dt)
            self.btn_join.draw(surf)

        elif self._phase == "wait":
            ui.draw_glow_text(surf, "Waiting for host to start…",
                              ui.font(28, bold=True), C.ORANGE, CX, HEIGHT//2, anchor="center")

        elif self._phase == "error":
            ui.draw_glow_text(surf, "Connection Failed", ui.font(28, bold=True),
                              C.RED, CX, HEIGHT//2-30, anchor="center")
            ui.draw_text(surf, self._error, ui.font(18), C.GRAY,
                         CX, HEIGHT//2+15, anchor="center", shadow=False)

        elif self._phase == "game" and self._eng:
            eng = self._eng
            hud_r = pygame.Rect(40, 80, WIDTH - 80, 60)
            ui.draw_panel(surf, hud_r)
            ui.draw_glow_text(surf, f"{eng.wpm:.0f}", ui.font(32, bold=True),
                              C.CYAN, 130, 110, anchor="center")
            ui.draw_text(surf, "WPM", ui.font(12), C.GRAY, 130, 132, anchor="center")
            acc_col = C.GREEN if eng.accuracy >= 90 else C.ORANGE if eng.accuracy >= 75 else C.RED
            ui.draw_glow_text(surf, f"{eng.accuracy:.1f}%", ui.font(26, bold=True),
                              acc_col, 280, 108, anchor="center")
            ui.draw_text(surf, "ACCURACY", ui.font(11), C.GRAY, 280, 132, anchor="center")
            if eng.time_limit:
                ui.draw_timer_ring(surf, WIDTH - 60, 110, 28, eng.time_frac, thick=5)
                tl = eng.time_left
                tc = C.RED if tl < 10 else C.YELLOW if tl < 20 else C.CYAN
                ui.draw_text(surf, f"{int(tl)+1}", ui.font(14, bold=True),
                             tc, WIDTH-60, 110, anchor="center")
            wd_r = pygame.Rect(60, 156, WIDTH - 120, 160)
            ui.draw_panel(surf, wd_r, border=C.PURPLE_DIM)
            _draw_word_area_solo(surf, eng, CX, wd_r)
            ti_r = pygame.Rect(CX - 280, 328, 560, 48)
            ui.draw_panel(surf, ti_r, color=C.BG_INPUT, border=C.CYAN_DIM)
            cw = eng.current_word
            tcol = C.GREEN if eng.typed == cw[:len(eng.typed)] else C.RED
            ui.draw_text(surf, eng.typed or "type…",
                         ui.font(20), tcol if eng.typed else C.GRAY,
                         ti_r.x + 12, ti_r.centery, anchor="midleft")
            self._track.draw(surf)

        self.btn_back.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── RESULTS ──────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class ResultsScreen:
    def __init__(self, app):
        self.app   = app
        CX = WIDTH // 2
        self.btn_again = ui.Button(CX-290, HEIGHT-90, 180, 52, "▶ PLAY AGAIN", C.CYAN)
        self.btn_save  = ui.Button(CX-90,  HEIGHT-90, 180, 52, "💾 SAVE SCORE", C.GREEN)
        self.btn_lb    = ui.Button(CX+110, HEIGHT-90, 180, 52, "🏆 LEADERBOARD", C.YELLOW)
        self.btn_menu  = ui.Button(CX+310, HEIGHT-90, 130, 52, "MENU", C.GRAY)
        self._saved    = False
        self._entry    = None
        self._t        = 0.0

    def enter(self):
        self._saved = False
        self._entry = None
        self._t     = 0.0

    def handle(self, event):
        if self.btn_again.handle(event): self.app.go(S.GAME)
        if self.btn_lb   .handle(event): self.app.go(S.LEADERBOARD)
        if self.btn_menu .handle(event): self.app.go(S.MENU)
        if not self._saved and self.btn_save.handle(event):
            sess = self.app.session
            self._entry = LB.save_score(sess.player_name, sess.wpm,
                                         sess.accuracy, sess.result_mode)
            self._saved = True

    def update(self, dt):
        self._t += dt

    def draw(self, surf):
        surf.fill(C.BG)
        sess = self.app.session
        CX   = WIDTH // 2
        pulse = 0.5 + 0.5 * math.sin(self._t * 3)

        ui.draw_glow_text(surf, "RACE COMPLETE!",
                          ui.font(48, bold=True),
                          ui.lerp_color(C.CYAN, C.PURPLE, pulse),
                          CX, 70, anchor="center")

        # main stats card
        card = pygame.Rect(CX-340, 130, 680, 280)
        ui.draw_panel(surf, card, border=C.CYAN_DIM)

        stats = [
            ("WPM",      f"{sess.wpm:.1f}",       C.CYAN),
            ("ACCURACY", f"{sess.accuracy:.1f}%",  C.GREEN if sess.accuracy>=90 else C.ORANGE),
            ("WORDS",    str(sess.words_done),      C.PURPLE),
            ("MODE",     sess.result_mode,           C.YELLOW),
        ]
        for i, (label, val, col) in enumerate(stats):
            bx = card.x + 40 + i * 165
            ui.draw_glow_text(surf, val, ui.font(40, bold=True), col,
                              bx, card.y + 90, anchor="center")
            ui.draw_text(surf, label, ui.font(13), C.GRAY,
                         bx, card.y + 140, anchor="center")

        # league badge
        lname, _, lcol = C.get_league(sess.wpm)
        badge_r = pygame.Rect(CX-80, card.y+160, 160, 56)
        ui.draw_panel(surf, badge_r, color=BG_CARD, border=lcol)
        gs = ui.glow_surf(160, 56, lcol, 14)
        surf.blit(gs, (badge_r.x-14, badge_r.y-14), special_flags=pygame.BLEND_RGBA_ADD)
        ui.draw_glow_text(surf, f"⬥ {lname.upper()} ⬥",
                          ui.font(22, bold=True), lcol,
                          badge_r.centerx, badge_r.centery, anchor="center")

        # saved confirmation
        if self._saved and self._entry:
            ui.draw_text(surf, f"✔ Score saved — #{1}", ui.font(16),
                         C.GREEN, CX, card.bottom + 22, anchor="center")

        self.btn_again.draw(surf)
        self.btn_save .draw(surf)
        self.btn_lb   .draw(surf)
        self.btn_menu .draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── LEADERBOARD ──────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class LeaderboardScreen:
    def __init__(self, app):
        self.app      = app
        self._filter  = None  # None = all modes
        self._mode_btns = []
        bw, bh = 110, 36
        CX = WIDTH // 2
        total_bw = (len(C.GAME_MODES)+1) * (bw+8)
        sx = CX - total_bw // 2
        self._mode_btns.append(ui.Button(sx, 80, bw, bh, "ALL", C.GRAY))
        for i, mode in enumerate(C.GAME_MODES):
            col = C.GAME_MODES[mode]["color"]
            self._mode_btns.append(ui.Button(sx+(i+1)*(bw+8), 80, bw, bh, mode, col))
        self.btn_back = ui.Button(40, HEIGHT-70, 120, 44, "◀ Back", C.GRAY)

    def handle(self, event):
        if self.btn_back.handle(event): self.app.go(S.MENU)
        for i, btn in enumerate(self._mode_btns):
            if btn.handle(event):
                self._filter = None if i == 0 else list(C.GAME_MODES.keys())[i-1]

    def update(self, dt): pass

    def draw(self, surf):
        surf.fill(C.BG)
        CX = WIDTH // 2
        ui.draw_glow_text(surf, "🏆  LEADERBOARD", ui.font(36, bold=True),
                          C.YELLOW, CX, 36, anchor="center")
        for btn in self._mode_btns:
            btn.draw(surf)

        scores = LB.top(limit=15, mode=self._filter)
        if not scores:
            ui.draw_text(surf, "No scores yet — play a game!", ui.font(22),
                         C.GRAY, CX, HEIGHT//2, anchor="center")
        else:
            headers = ["#", "NAME", "WPM", "ACC", "MODE", "LEAGUE"]
            col_x   = [80, 180, 420, 540, 660, 810]
            hy      = 138
            for hdr, cx in zip(headers, col_x):
                ui.draw_text(surf, hdr, ui.font(14, bold=True), C.GRAY,
                             cx, hy, anchor="midleft")
            pygame.draw.line(surf, C.GRAY, (60, hy+18), (WIDTH-60, hy+18), 1)

            for rank, e in enumerate(scores, 1):
                ry   = hy + 30 + (rank-1)*30
                _, _, lcol = C.get_league(e["wpm"])
                rc   = C.YELLOW if rank == 1 else C.LIGHT_GRAY if rank <= 3 else C.GRAY
                vals = [str(rank), e["name"], f"{e['wpm']:.1f}", f"{e['accuracy']:.1f}%",
                        e["mode"], e["league"]]
                cols = [rc, C.OFF_WHITE, C.CYAN, C.GREEN, C.ORANGE, lcol]
                for val, cx, vc in zip(vals, col_x, cols):
                    ui.draw_text(surf, val, ui.font(16), vc, cx, ry, anchor="midleft")
                if rank <= 3:
                    pygame.draw.line(surf, (*lcol, 50), (60, ry+14), (WIDTH-60, ry+14), 1)

        self.btn_back.draw(surf)


# ─────────────────────────────────────────────────────────────────────────────
# ── MUSIC GENERATOR ──────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

def _generate_music():
    """Generate a looping chiptune-style background track using numpy."""
    try:
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        RATE   = 44100
        BPM    = 128
        BEAT   = int(RATE * 60 / BPM)
        # 8-bar loop
        LOOP   = BEAT * 32
        t      = np.linspace(0, LOOP / RATE, LOOP, endpoint=False, dtype=np.float32)

        def note(freq, dur_beats, start_beat, wave="square", detune=0.0):
            """Return a mono float32 array for one note."""
            s = int(start_beat * BEAT)
            n = int(dur_beats   * BEAT)
            if s >= LOOP:
                return
            n = min(n, LOOP - s)
            lt = t[s:s+n]
            f  = freq + detune
            if wave == "square":
                sig = np.sign(np.sin(2 * np.pi * f * lt))
            elif wave == "saw":
                sig = 2.0 * (lt * f - np.floor(lt * f + 0.5))
            else:  # sine
                sig = np.sin(2 * np.pi * f * lt)
            # ADSR envelope
            a = min(int(0.01 * RATE), n)
            d = min(int(0.05 * RATE), n - a)
            r = min(int(0.08 * RATE), n)
            env = np.ones(n, dtype=np.float32)
            env[:a] = np.linspace(0, 1, a)
            env[a:a+d] *= np.linspace(1, 0.7, d)
            env[n-r:] *= np.linspace(1, 0, r)
            return s, sig * env

        # ── melody notes (C minor pentatonic: C D# F G A#) ──────────────────
        C4, Ds4, F4, G4, As4 = 261.63, 311.13, 349.23, 392.00, 466.16
        C5, G3               = 523.25, 196.00

        melody_seq = [
            (C4,  1, 0),  (G4,  1, 1),  (F4,  1, 2),  (As4, 1, 3),
            (C5,  1, 4),  (As4, 1, 5),  (G4,  1, 6),  (F4,  1, 7),
            (Ds4, 1, 8),  (F4,  1, 9),  (G4,  1,10),  (C4,  1,11),
            (Ds4, 1,12),  (G4,  1,13),  (As4, 1,14),  (C5,  2,15),
            (G4,  1,17),  (F4,  1,18),  (Ds4, 1,19),  (C4,  1,20),
            (Ds4, 1,21),  (F4,  1,22),  (G4,  1,23),  (As4, 1,24),
            (C5,  1,25),  (G4,  1,26),  (F4,  1,27),  (Ds4, 1,28),
            (C4,  2,29),  (G3,  1,31),
        ]
        # ── bass line ────────────────────────────────────────────────────────
        bass_seq = [
            (C4/2, 2, b) for b in range(0, 32, 4)
        ] + [
            (G3,   2, b) for b in range(2, 32, 4)
        ]
        # ── hi-hat (noise bursts) ─────────────────────────────────────────────
        hat_beats = list(range(0, 32))   # every beat

        buf = np.zeros(LOOP, dtype=np.float32)

        # layer melody
        for freq, dur, start in melody_seq:
            res = note(freq, dur, start, "square", detune=0.5)
            if res:
                s, sig = res
                buf[s:s+len(sig)] += sig * 0.30

        # layer bass (saw wave)
        for freq, dur, start in bass_seq:
            res = note(freq, dur, start, "saw")
            if res:
                s, sig = res
                buf[s:s+len(sig)] += sig * 0.18

        # hi-hat noise
        for b in hat_beats:
            s = int(b * BEAT)
            n = int(0.05 * RATE)
            if s + n > LOOP:
                continue
            hat = np.random.uniform(-1, 1, n).astype(np.float32)
            env = np.linspace(1, 0, n) ** 2
            buf[s:s+n] += hat * env * 0.12

        # soft kick on beats 0, 4, 8 ...
        for b in range(0, 32, 4):
            s = int(b * BEAT)
            n = int(0.15 * RATE)
            if s + n > LOOP:
                continue
            lt2 = np.linspace(0, 1, n)
            freq_sweep = np.exp(np.linspace(np.log(200), np.log(50), n))
            kick = np.sin(2 * np.pi * np.cumsum(freq_sweep) / RATE)
            env  = np.linspace(1, 0, n) ** 1.5
            buf[s:s+n] += kick.astype(np.float32) * env * 0.35

        # normalize
        peak = np.max(np.abs(buf))
        if peak > 0:
            buf /= peak
        buf *= 0.55

        # to stereo int16
        stereo = np.stack([buf, buf], axis=1)
        pcm    = (stereo * 32767).astype(np.int16)
        sound  = pygame.sndarray.make_sound(pcm)
        sound.set_volume(0.45)
        sound.play(loops=-1)
    except Exception as e:
        print(f"[music] Could not generate music: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# ── APP (main controller) ────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────

class App:
    _TYPING_STATES = {S.GAME, S.GHOST_RACE, S.LOCAL_MULTI,
                      S.WIFI_JOIN, S.NAME_INPUT}

    def __init__(self):
        pygame.init()
        pygame.display.set_caption(TITLE)

        if IS_ANDROID:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

        self.clock   = pygame.time.Clock()
        self.session = Session()

        pygame.key.set_text_input_rect(pygame.Rect(0, 0, 1, 1))

        self._screens: dict[S, object] = {
            S.MENU:        MenuScreen(self),
            S.MODE_SELECT: ModeSelectScreen(self),
            S.NAME_INPUT:  NameInputScreen(self),
            S.GAME:        GameScreen(self),
            S.GHOST_RACE:  GhostRaceScreen(self),
            S.MULTI_LOBBY: MultiLobbyScreen(self),
            S.LOCAL_MULTI: LocalMultiScreen(self),
            S.WIFI_JOIN:   WifiJoinScreen(self),
            S.RESULTS:     ResultsScreen(self),
            S.LEADERBOARD: LeaderboardScreen(self),
        }
        self._state: S = S.MENU

        # ── start background music ────────────────────────────────────────────
        _generate_music()

        # ── credit font (loaded once) ─────────────────────────────────────────
        self._credit_font = ui.font(13)

    def go(self, state: S):
        self._state = state
        scr = self._screens[state]
        if hasattr(scr, "enter"):
            scr.enter()
        # On Android: open system keyboard when entering a typing screen,
        # close it on menus/results so it doesn't block the UI
        if IS_ANDROID:
            if state in self._TYPING_STATES:
                pygame.key.start_text_input()
            else:
                pygame.key.stop_text_input()

    def run(self):
        # Start text input right away so TEXTINPUT events flow from the start
        pygame.key.start_text_input()

        while True:
            dt  = self.clock.tick(FPS) / 1000.0
            scr = self._screens[self._state]

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                # Pass both KEYDOWN and TEXTINPUT to the active screen
                scr.handle(event)

            scr.update(dt)
            scr.draw(self.screen)

            # ── persistent bottom-left credit ─────────────────────────────────
            credit_txt = "Made by Kervy Nalam"
            shadow = self._credit_font.render(credit_txt, True, (0, 0, 0))
            self.screen.blit(shadow, (12, HEIGHT - 22))
            label  = self._credit_font.render(credit_txt, True, (90, 90, 120))
            self.screen.blit(label,  (11, HEIGHT - 23))

            pygame.display.flip()


# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App().run()
