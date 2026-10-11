"""Bottom player bar widget showing playback status, progress bar, and controls."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Label, Static

from liquidcloud.api import Track
from liquidcloud.queue_manager import LoopMode


class EqualizerWidget(Static):
    """Animated ASCII equalizer bars."""

    FRAMES = [
        " ▃▅▇▅▃",
        "▃▅▇█▇▅",
        "▅▇█▇▅▃",
        "▇█▇▅▃ ",
        "█▇▅▃ ▂",
        "▇▅▃ ▂▃",
        "▅▃ ▂▃▅",
        "▃ ▂▃▅▇",
    ]

    is_playing = reactive(False)
    is_paused = reactive(False)

    def __init__(self, **kwargs):
        super().__init__("      ", **kwargs)
        self.frame_idx = 0

    def tick(self):
        if self.is_playing:
            self.frame_idx = (self.frame_idx + 1) % len(self.FRAMES)
            self.update(f"[bold #00f5d4]{self.FRAMES[self.frame_idx]}[/]")
        elif self.is_paused:
            self.update("[dim #00b4d8] ▂  ▂ [/]")
        else:
            self.update("[dim]      [/]")


class PlayerBar(Widget):
    """Bottom playback controller and status display."""

    current_track: reactive[Track | None] = reactive(None)
    position: reactive[float] = reactive(0.0)
    duration: reactive[float] = reactive(0.0)
    state: reactive[str] = reactive("stopped")
    volume: reactive[int] = reactive(80)
    is_muted: reactive[bool] = reactive(False)
    loop_mode: reactive[LoopMode] = reactive(LoopMode.OFF)
    is_shuffled: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        with Vertical(id="player-container"):
            # Top row: Equalizer + Track Title & Artist + Badges
            with Horizontal(id="player-info-row"):
                yield EqualizerWidget(id="player-equalizer")
                yield Label("[dim]No track playing[/]", id="player-track-info")
                yield Static("", id="player-spacer")
                yield Label("", id="player-badges")

            # Middle row: Progress bar with time elapsed / duration
            with Horizontal(id="player-progress-row"):
                yield Label("0:00", id="player-time-curr")
                yield Static("", id="player-progress-bar")
                yield Label("0:00", id="player-time-total")

            # Bottom row: Keybinding hints and control buttons
            with Horizontal(id="player-hints-row"):
                yield Button("⏮ Prev", id="btn-player-prev", classes="player-ctrl-btn")
                yield Button("⏯ Play", id="btn-player-play", classes="player-ctrl-btn")
                yield Button("⏭ Next", id="btn-player-next", classes="player-ctrl-btn")
                yield Label(
                    " [dim]• [b #00f5d4]Space[/] Play • [b #00f5d4]n/p[/] Next/Prev • [b #00f5d4]←/→[/] Seek • [b #00f5d4]+/-[/] Vol • [b #00f5d4]l[/] Loop • [b #00f5d4]?[/] Help[/]",
                    id="player-hints",
                )

    def on_mount(self):
        for btn in self.query(Button):
            btn.can_focus = False
        self._last_rendered_sec = -1
        self._eq_timer = self.set_interval(0.25, self._tick_equalizer)

    def _tick_equalizer(self):
        if self.state != "playing":
            return
        eq = self.query_one(EqualizerWidget)
        eq.is_playing = True
        eq.is_paused = False
        eq.tick()

    def watch_current_track(self, track: Track | None):
        self._update_track_info()

    def watch_position(self, pos: float):
        self._update_progress()

    def watch_duration(self, dur: float):
        self._update_progress()

    def watch_state(self, st: str):
        self._update_track_info()
        self._update_badges()
        try:
            btn = self.query_one("#btn-player-play", Button)
            if st == "playing":
                btn.label = "⏸ Pause"
            else:
                btn.label = "▶ Play"
        except Exception:
            pass

    def watch_volume(self, vol: int):
        self._update_badges()

    def watch_is_muted(self, muted: bool):
        self._update_badges()

    def watch_loop_mode(self, mode: LoopMode):
        self._update_badges()

    def watch_is_shuffled(self, shuff: bool):
        self._update_badges()

    def _format_time(self, seconds: float) -> str:
        s = max(0, int(seconds))
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _update_track_info(self):
        lbl = self.query_one("#player-track-info", Label)
        if not self.current_track:
            lbl.update("[dim italic]No track playing[/]")
            return

        title = self.current_track.title
        artist = self.current_track.artist

        if len(title) > 45:
            title = title[:42] + "..."
        if len(artist) > 25:
            artist = artist[:22] + "..."

        status_prefix = ""
        if self.state == "buffering":
            status_prefix = "[bold #70d6ff]⌛ Loading... [/]"
        elif self.state == "playing":
            status_prefix = "[bold #00f5d4]▶ [/]"
        elif self.state == "paused":
            status_prefix = "[bold #00b4d8]⏸ [/]"

        lbl.update(
            f"{status_prefix}[bold #f8fafc]{title}[/] [dim #64748b]by[/] [bold #38bdf8]{artist}[/]"
        )

    def _update_progress(self):
        curr_sec = int(self.position)
        if getattr(self, "_last_rendered_sec", -1) == curr_sec and self.duration == getattr(self, "_last_rendered_dur", -1):
            return
        self._last_rendered_sec = curr_sec
        self._last_rendered_dur = self.duration

        curr_lbl = self.query_one("#player-time-curr", Label)
        total_lbl = self.query_one("#player-time-total", Label)
        bar = self.query_one("#player-progress-bar", Static)

        curr_lbl.update(self._format_time(self.position))
        dur = self.duration
        if dur <= 0 and self.current_track:
            dur = self.current_track.duration_sec
        total_lbl.update(self._format_time(dur))

        # Build progress bar string
        total_slots = 36
        ratio = 0.0
        if dur > 0:
            ratio = max(0.0, min(1.0, self.position / dur))

        filled_slots = int(ratio * total_slots)
        empty_slots = total_slots - filled_slots

        # Liquid progress bar characters: ━ and 💧
        filled_str = "━" * max(0, filled_slots - 1) + ("💧" if filled_slots > 0 else "")
        empty_str = "─" * empty_slots
        pct = int(ratio * 100)

        bar.update(f"[bold #00f5d4]{filled_str}[/][dim #1e293b]{empty_str}[/] [bold #70d6ff]{pct}%[/]")

    def _update_badges(self):
        badges_lbl = self.query_one("#player-badges", Label)

        # Volume
        if self.is_muted:
            vol_str = "[bold #f43f5e]🔇 MUTED[/]"
        else:
            vol_str = f"[#00f5d4]🔊 {self.volume}%[/]"

        # Loop
        loop_str = f"[#70d6ff]{self.loop_mode.label()}[/]"

        # Shuffle
        shuff_str = "[#00f5d4]🔀 SHUFF[/]" if self.is_shuffled else ""

        # State
        state_color = {
            "playing": "#00f5d4",
            "paused": "#00b4d8",
            "buffering": "#70d6ff",
            "stopped": "#64748b",
        }.get(self.state, "#64748b")
        state_str = f"[{state_color}][{self.state.upper()}][/]"

        parts = [p for p in [state_str, vol_str, loop_str, shuff_str] if p]
        badges_lbl.update("  ".join(parts))
