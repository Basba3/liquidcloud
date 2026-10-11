"""Modal screens for URL input, help, and playlist management."""

from typing import Any, Dict, List, Optional
from textual.app import ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static


class UrlModal(ModalScreen[Optional[str]]):
    """Modal for inputting a SoundCloud URL."""

    def compose(self) -> ComposeResult:
        with Vertical(id="url-modal-dialog"):
            yield Label("[bold #00f5d4]Open SoundCloud URL[/]", id="modal-title")
            yield Label(
                "Paste a track, playlist, or artist URL:",
                classes="modal-subtitle",
            )
            yield Input(
                placeholder="https://soundcloud.com/artist/track-name",
                id="url-input",
            )
            with Horizontal(classes="modal-buttons"):
                yield Button("Load", variant="primary", id="btn-submit")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self):
        self.query_one("#url-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted):
        val = event.value.strip()
        self.dismiss(val if val else None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-submit":
            val = self.query_one("#url-input", Input).value.strip()
            self.dismiss(val if val else None)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class HelpModal(ModalScreen[None]):
    """Modal displaying keybindings and instructions."""

    HELP_TEXT = """
[bold #00f5d4]═══ LiquidCloud Keybindings ═══[/]

[bold yellow]Navigation[/]
  [bold white]1[/]          SoundCloud Likes (❤️)
  [bold white]2[/]          SoundCloud Playlists (📂)
  [bold white][ / ][/]      Switch SoundCloud Playlist (Prev / Next)
  [bold white]3[/]          Search tracks (🔍)
  [bold white]4[/]          Explore trending by genre (🧭)
  [bold white]5[/]          Playback Queue (📑)
  [bold white]6[/]          Local Custom Playlists (📁)
  [bold white]7[/]          Playback History (🕒)
  [bold white]↑ / ↓[/]      Navigate through track list
  [bold white]Enter[/]      Play selected track immediately
  [bold white]/[/]          Focus Search bar
  [bold white]u[/]          Open direct SoundCloud URL (track/playlist/artist)
  [bold white]L[/]          SoundCloud Account & Login modal (🔑)
  [bold white]?[/]          Show this help dialog
  [bold white]q[/]          Quit application

[bold yellow]Playback Controls[/]
  [bold white]Space[/]      Play / Pause
  [bold white]← / →[/]      Seek -5s / +5s
  [bold white]Shift+←/→[/]  Seek -30s / +30s
  [bold white]n[/]          Next track
  [bold white]p[/]          Previous track
  [bold white]+ / =[/]      Volume up (+5%)
  [bold white]- / _[/]      Volume down (-5%)
  [bold white]m[/]          Mute / Unmute
  [bold white]l[/]          Cycle loop mode: Off ➔ Track ➔ Queue
  [bold white]z[/]          Toggle shuffle queue

[bold yellow]Track & Playlist Actions[/]
  [bold white]a[/]          Add selected track to Queue
  [bold white]f[/]          Toggle Favorite (♥) on selected or playing track
  [bold white]c[/]          Clear queue (in Queue tab)
  [bold white]d / Del[/]    Remove track from queue or playlist
  [bold white]P (Shift+p)[/] Add selected track to a Local Playlist
"""

    def compose(self) -> ComposeResult:
        with Vertical(id="help-modal-dialog"):
            yield Static(self.HELP_TEXT, id="help-text")
            with Horizontal(classes="modal-buttons"):
                yield Button("Close (Esc)", variant="primary", id="btn-close")

    def on_button_pressed(self, event: Button.Pressed):
        self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class PlaylistPickerModal(ModalScreen[Optional[str]]):
    """Modal to choose a playlist to add a track to."""

    def __init__(self, playlists: List[str]):
        super().__init__()
        self.playlists = playlists

    def compose(self) -> ComposeResult:
        with Vertical(id="playlist-picker-dialog"):
            yield Label("[bold #00f5d4]Add Track to Playlist[/]", id="modal-title")
            if self.playlists:
                yield Label("Select an existing playlist:", classes="modal-subtitle")
                yield OptionList(*self.playlists, id="playlist-options")
            else:
                yield Label("[italic dim]No playlists created yet.[/]", classes="modal-subtitle")

            yield Label("Or create a new playlist:", classes="modal-subtitle")
            yield Input(placeholder="New playlist name...", id="new-playlist-input")

            with Horizontal(classes="modal-buttons"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-add":
            new_name = self.query_one("#new-playlist-input", Input).value.strip()
            if new_name:
                self.dismiss(new_name)
                return
            if self.playlists:
                opt_list = self.query_one("#playlist-options", OptionList)
                if opt_list.highlighted is not None:
                    chosen = self.playlists[opt_list.highlighted]
                    self.dismiss(chosen)
                    return
            self.dismiss(None)
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class NewPlaylistModal(ModalScreen[Optional[str]]):
    """Modal to create a new playlist."""

    def compose(self) -> ComposeResult:
        with Vertical(id="new-playlist-dialog"):
            yield Label("[bold #00f5d4]Create New Playlist[/]", id="modal-title")
            yield Input(placeholder="Enter playlist name...", id="playlist-name-input")
            with Horizontal(classes="modal-buttons"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def on_mount(self):
        self.query_one("#playlist-name-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted):
        val = event.value.strip()
        self.dismiss(val if val else None)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-create":
            val = self.query_one("#playlist-name-input", Input).value.strip()
            self.dismiss(val if val else None)
        else:
            self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)


class LoginModal(ModalScreen[Optional[Dict[str, Any]]]):
    """Modal for SoundCloud authentication and account management."""

    def __init__(self, api: Any, current_user: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.api = api
        self.current_user = current_user

    def compose(self) -> ComposeResult:
        with Vertical(id="login-modal-dialog"):
            yield Label("[bold #00f5d4]🫧 SoundCloud Authentication 🔑[/]", id="modal-title")

            if self.current_user:
                username = self.current_user.get("username", "Unknown")
                likes = self.current_user.get("likes_count", 0)
                pls = self.current_user.get("playlist_count", 0)
                yield Static(
                    f"[bold #22c55e]● Logged in as[/] [bold #38bdf8]@{username}[/]\n"
                    f"[dim #94a3b8]SoundCloud Library: [bold white]{likes}[/] likes • [bold white]{pls}[/] playlists[/]",
                    id="modal-account-status",
                    classes="modal-user-card",
                )
            else:
                yield Static(
                    "[bold #f43f5e]○ Not Logged In[/] [dim #94a3b8](Guest Mode - personal likes & playlists unavailable)[/]",
                    id="modal-account-status",
                    classes="modal-user-card",
                )

            yield Static(
                "[bold #f59e0b]How to connect your SoundCloud account:[/]\n"
                "[dim #94a3b8]1. Click [bold #00f5d4]'Auto-Detect'[/] to import active cookies from Firefox / Zen / LibreWolf.\n"
                "2. Or sign in on [bold #38bdf8]soundcloud.com[/], press [bold white]F12[/] (DevTools) ➔ [bold white]Storage/Cookies[/],\n"
                "   copy the [bold #00f5d4]oauth_token[/] cookie value (starts with 2-...) and paste below.[/]",
                classes="modal-help-box",
            )

            yield Label("SoundCloud OAuth Token:", classes="modal-subtitle")
            yield Input(
                placeholder="2-xxxxxx-xxxxxxxxx-xxxxxx",
                id="token-input",
                password=True,
            )
            yield Label("", id="login-status-label", classes="modal-status")

            with Horizontal(classes="modal-buttons"):
                yield Button("✨ Auto-Detect", variant="warning", id="btn-autodetect")
                yield Button("Log In", variant="primary", id="btn-login")
                if self.current_user:
                    yield Button("Log Out", variant="error", id="btn-logout")
                yield Button("Cancel (Esc)", variant="default", id="btn-cancel")

    def on_mount(self):
        token_input = self.query_one("#token-input", Input)
        token_input.focus()

    def on_input_submitted(self, event: Input.Submitted):
        self._do_login()

    def _set_status(self, text: str):
        try:
            self.query_one("#login-status-label", Label).update(text)
        except Exception:
            pass

    def _do_login(self):
        token = self.query_one("#token-input", Input).value.strip()
        if not token:
            self._set_status("[bold red]Please enter an OAuth token or use Auto-Detect.[/]")
            return

        self._set_status("[dim cyan]Connecting to SoundCloud and verifying token...[/]")
        profile = self.api.set_token(token)
        if profile:
            self.dismiss({"action": "login", "user": profile})
        else:
            self._set_status("[bold red]Authentication failed: Token is invalid or expired.[/]")

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn-autodetect":
            self._set_status("[dim cyan]Scanning local browser cookies for soundcloud token...[/]")
            found = self.api.find_browser_token()
            if found:
                self.query_one("#token-input", Input).value = found
                self._set_status("[dim cyan]Browser token detected! Verifying account...[/]")
                profile = self.api.set_token(found)
                if profile:
                    self.dismiss({"action": "login", "user": profile})
                    return
                else:
                    self._set_status("[bold red]Browser token found, but SoundCloud rejected it (expired).[/]")
            else:
                self._set_status("[bold yellow]No active session found in browser cookies. Please paste token manually.[/]")
        elif bid == "btn-login":
            self._do_login()
        elif bid == "btn-logout":
            self.api.logout()
            self.dismiss({"action": "logout"})
        elif bid == "btn-cancel":
            self.dismiss(None)

    def key_escape(self):
        self.dismiss(None)

