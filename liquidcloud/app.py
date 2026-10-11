"""Main SoundCloud TUI Application."""

import logging
import time
from typing import Any, Dict, List, Optional
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, HorizontalScroll, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Input, Label, Static

from liquidcloud.api import SoundCloudAPI, Track
from liquidcloud.player import MpvPlayer
from liquidcloud.queue_manager import LoopMode, QueueManager
from liquidcloud.storage import Storage
from liquidcloud.ui.modals import HelpModal, LoginModal, NewPlaylistModal, PlaylistPickerModal, UrlModal
from liquidcloud.ui.player_bar import PlayerBar
from liquidcloud.ui.sidebar import Sidebar
from liquidcloud.ui.track_table import TrackTable

logging.basicConfig(level=logging.INFO, filename="/tmp/liquidcloud.log", filemode="a")
logger = logging.getLogger("liquidcloud")


class LiquidCloudApp(App):
    """LiquidCloud - Modern Terminal SoundCloud Client."""

    CSS_PATH = "styles.tcss"
    TITLE = "LiquidCloud"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("L", "login", "Account", show=False),
        Binding("space", "toggle_play", "Play/Pause", show=False),
        Binding("left", "seek_backward", "Seek -5s", show=False),
        Binding("right", "seek_forward", "Seek +5s", show=False),
        Binding("shift+left", "seek_backward_big", "Seek -30s", show=False),
        Binding("shift+right", "seek_forward_big", "Seek +30s", show=False),
        Binding("n", "next_track", "Next", show=False),
        Binding("p", "prev_track", "Prev", show=False),
        Binding("plus", "volume_up", "Vol +", show=False),
        Binding("=", "volume_up", "Vol +", show=False),
        Binding("minus", "volume_down", "Vol -", show=False),
        Binding("_", "volume_down", "Vol -", show=False),
        Binding("m", "toggle_mute", "Mute", show=False),
        Binding("l", "cycle_loop", "Loop", show=False),
        Binding("z", "toggle_shuffle", "Shuffle", show=False),
        Binding("slash", "focus_search", "Search", show=False),
        Binding("u", "open_url_dialog", "Open URL", show=False),
        Binding("question_mark", "show_help", "Help", show=False),
        Binding("1", "tab_sc_likes", "SC Likes Tab", show=False),
        Binding("2", "tab_sc_playlists", "SC Playlists Tab", show=False),
        Binding("3", "tab_search", "Search Tab", show=False),
        Binding("4", "tab_explore", "Explore Tab", show=False),
        Binding("5", "tab_queue", "Queue Tab", show=False),
        Binding("6", "tab_playlists", "Local Lists Tab", show=False),
        Binding("7", "tab_history", "History Tab", show=False),
        Binding("left_square_bracket", "prev_sc_playlist", "Prev SC Playlist", show=False),
        Binding("right_square_bracket", "next_sc_playlist", "Next SC Playlist", show=False),
        Binding("a", "add_to_queue", "Add to Queue", show=False),
        Binding("f", "toggle_favorite", "Favorite", show=False),
        Binding("shift+p", "add_to_playlist", "Add to Playlist", show=False),
        Binding("d", "delete_item", "Delete", show=False),
        Binding("delete", "delete_item", "Delete", show=False),
        Binding("c", "clear_queue", "Clear Queue", show=False),
    ]

    GENRES = [
        "Lo-Fi",
        "Phonk",
        "Synthwave",
        "Deep House",
        "Electronic",
        "Hip-Hop",
        "Techno",
        "Drum & Bass",
        "Rock",
        "Ambient",
        "Gaming",
    ]

    current_tab = reactive("sc_likes")
    active_playlist_name = reactive("")
    active_sc_playlist_idx: int = 0
    sc_playlists: List[Dict[str, Any]] = []

    def __init__(self):
        super().__init__()
        self.api = SoundCloudAPI()
        self.player = MpvPlayer()
        self.queue_mgr = QueueManager()
        self.storage = Storage()
        self._likes_cache: List[Track] = []
        self._consecutive_errors: int = 0

        # Connect player callbacks
        self.player.on_time_update = self._on_player_time
        self.player.on_state_change = self._on_player_state
        self.player.on_volume_change = self._on_player_volume
        self.player.on_track_end = self._on_player_track_end

        # Load saved settings
        settings = self.storage.get_settings()
        self.player.set_volume(settings.get("volume", 80))

    def compose(self) -> ComposeResult:
        with Vertical(id="app-container"):
            with Horizontal(id="main-layout"):
                yield Sidebar(id="sidebar")
                with Vertical(id="content-container"):
                    # Search bar
                    with Horizontal(id="search-bar-row"):
                        yield Input(placeholder="Search tracks, artists, mixes... (Press / to focus)", id="search-input")
                        yield Button("Search", id="search-btn")

                    # SC Playlists bar (visible in sc_playlists tab)
                    with HorizontalScroll(id="sc-playlists-bar-row"):
                        pass

                    # Explore genre tags row (visible in explore tab)
                    with Horizontal(id="explore-genres-row"):
                        for genre in self.GENRES:
                            slug = genre.lower().replace(" & ", "-and-").replace(" ", "-")
                            yield Button(genre, classes="genre-tag-btn", id=f"genre-{slug}")

                    # Local Playlists bar (visible in playlists tab)
                    with Horizontal(id="playlists-bar-row", classes="hidden"):
                        yield Button("➕ New Playlist", id="btn-new-playlist", classes="genre-tag-btn")
                        yield Static("", id="playlist-list-container")

                    # Track list table
                    yield TrackTable(id="track-table")

            # Bottom Player Bar
            yield PlayerBar(id="player-bar")

    def on_mount(self):
        self._update_counts()
        self._init_user_account()
        # Default start tab: sc_likes
        self.action_tab_sc_likes()

    @work(thread=True)
    def _init_user_account(self):
        me = self.api.get_me()
        if me:
            user_text = f"[bold #00f5d4]👤 {me['username']}[/]\n[dim #70d6ff]{me.get('likes_count', 0)} likes • {me.get('playlist_count', 0)} lists[/]"
            self.call_from_thread(self._set_sidebar_user, user_text, me.get("likes_count", 0), True, me.get("username", ""))
        else:
            self.call_from_thread(self._set_sidebar_user, "[dim #64748b]Guest Mode (Not logged in)[/]", 0, False, "")

    def _set_sidebar_user(self, text: str, likes_count: int, is_logged: bool = False, uname: str = ""):
        try:
            sidebar = self.query_one(Sidebar)
            sidebar.user_info = text
            sidebar.fav_count = likes_count
            sidebar.is_logged_in = is_logged
            sidebar.username = uname
        except Exception:
            pass

    def action_login(self) -> None:
        def on_auth_result(res: Optional[Dict[str, Any]]):
            if not res:
                return
            act = res.get("action")
            if act == "logout":
                self.api.logout()
                self._set_sidebar_user("[dim #64748b]Guest Mode (Not logged in)[/]", 0, False, "")
                self._likes_cache = []
                self.sc_playlists = []
                self.notify("Signed out of SoundCloud (Guest Mode).", severity="information")
                if self.current_tab == "sc_likes":
                    table = self.query_one(TrackTable)
                    table.set_tracks([], None)
            elif act == "login":
                user = res.get("user") or {}
                uname = user.get("username", "User")
                likes = user.get("likes_count", 0)
                pls = user.get("playlist_count", 0)
                user_text = f"[bold #00f5d4]👤 {uname}[/]\n[dim #70d6ff]{likes} likes • {pls} lists[/]"
                self._set_sidebar_user(user_text, likes, True, uname)
                self.notify(f"Connected to SoundCloud as @{uname}!", severity="information")
                self._likes_cache = []
                self.sc_playlists = []
                if self.current_tab == "sc_likes":
                    self._load_sc_likes()
                elif self.current_tab == "sc_playlists":
                    self._load_sc_playlists()

        current_user = self.api.get_me()
        self.push_screen(LoginModal(self.api, current_user=current_user), on_auth_result)

    def _update_counts(self):
        sidebar = self.query_one(Sidebar)
        sidebar.queue_count = len(self.queue_mgr.queue)

    # --- Player callbacks ---
    def _on_player_time(self, pos: float, dur: float):
        if self.is_running:
            try:
                self.call_from_thread(self._update_player_time, pos, dur)
            except RuntimeError:
                pass

    def _update_player_time(self, pos: float, dur: float):
        try:
            bar = self.query_one(PlayerBar)
            bar.position = pos
            bar.duration = dur
        except Exception:
            pass

    def _on_player_state(self, state: str):
        if self.is_running:
            try:
                self.call_from_thread(self._update_player_state, state)
            except RuntimeError:
                pass

    def _update_player_state(self, state: str):
        try:
            bar = self.query_one(PlayerBar)
            bar.state = state
        except Exception:
            pass

    def _on_player_volume(self, vol: int, muted: bool):
        if self.is_running:
            try:
                self.call_from_thread(self._update_player_volume, vol, muted)
            except RuntimeError:
                pass

    def _update_player_volume(self, vol: int, muted: bool):
        try:
            bar = self.query_one(PlayerBar)
            bar.volume = vol
            bar.is_muted = muted
            self.storage.save_settings({"volume": vol, "loop_mode": self.queue_mgr.loop_mode.value})
        except Exception:
            pass

    def _on_player_track_end(self):
        if self.is_running:
            try:
                self.call_from_thread(self._handle_track_finished)
            except Exception as e:
                logger.error(f"Error handling track end: {e}")

    def _handle_track_finished(self):
        next_track = self.queue_mgr.next_track(is_manual=False)
        if next_track:
            self._start_playback(next_track)
            self.notify(f"Playing next: {next_track.title}", timeout=2)
        else:
            bar = self.query_one(PlayerBar)
            bar.state = "stopped"
            bar.current_track = None

    # --- Playback Logic ---
    def _start_playback(self, track: Track):
        bar = self.query_one(PlayerBar)
        bar.current_track = track
        bar.state = "buffering"
        self.player.stop()  # Stop old track immediately so no lingering audio!

        # Update table playing highlight
        table = self.query_one(TrackTable)
        table.update_playing_track(track.id, is_favorite_checker=self.storage.is_favorite)

        # Add to history
        self.storage.add_history(track)

        # Resolve stream asynchronously
        self._resolve_and_play(track)

    @work(thread=True, exclusive=True)
    def _resolve_and_play(self, track: Track):
        try:
            stream_url = self.api.get_stream_url(track)
            self.player.play(stream_url, track.title)
            self._consecutive_errors = 0
        except Exception as e:
            logger.error(f"Playback error for {track.title}: {e}")
            self.notify(f"Could not play '{track.title}': {e}", severity="error")
            self._consecutive_errors = getattr(self, "_consecutive_errors", 0) + 1
            if self._consecutive_errors < 3:
                time.sleep(1.0)
                try:
                    self.call_from_thread(self._handle_track_finished)
                except Exception:
                    pass

    # --- UI Events ---
    def on_button_pressed(self, event: Button.Pressed):
        btn_id = event.button.id or ""

        # SC Playlist buttons
        if hasattr(event.button, "sc_playlist_idx"):
            self._select_sc_playlist(event.button.sc_playlist_idx)
            return

        # Sidebar buttons
        if btn_id.startswith("tab-btn-"):
            tab = btn_id.replace("tab-btn-", "")
            if tab == "help":
                self.action_show_help()
            elif tab == "auth":
                self.action_login()
            else:
                self._switch_tab(tab)

        # Search button
        elif btn_id == "search-btn":
            val = self.query_one("#search-input", Input).value.strip()
            if val:
                self._run_search(val)

        # Explore genre buttons
        elif btn_id.startswith("genre-"):
            genre_name = event.button.label.plain
            self._load_genre(genre_name)

        # New playlist button
        elif btn_id == "btn-new-playlist":
            self.action_new_playlist()

        # Playlist select button
        elif btn_id.startswith("pl-select-"):
            pl_name = btn_id.replace("pl-select-", "")
            self._select_playlist(pl_name)

        # Player Bar playback controls
        elif btn_id == "btn-player-prev":
            self.action_prev_track()

        elif btn_id == "btn-player-play":
            self.action_toggle_play()

        elif btn_id == "btn-player-next":
            self.action_next_track()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "search-input":
            val = event.value.strip()
            if val:
                self._run_search(val)

    def on_data_table_row_selected(self, event: TrackTable.RowSelected):
        table = self.query_one(TrackTable)
        selected_track = table.get_selected_track()
        if not selected_track:
            return

        all_tracks = table.get_all_tracks()
        start_idx = 0
        for i, t in enumerate(all_tracks):
            if str(t.id) == str(selected_track.id):
                start_idx = i
                break
        else:
            if table.cursor_row is not None:
                start_idx = table.cursor_row

        # Replace queue with current table tracks starting at clicked track
        self.queue_mgr.set_queue(all_tracks, start_index=start_idx)
        self._update_counts()
        self._start_playback(selected_track)

    # --- Navigation / Tabs ---
    def _switch_tab(self, tab: str):
        self.current_tab = tab
        sidebar = self.query_one(Sidebar)
        sidebar.active_tab = tab

        # Genre & playlist row visibility
        genres_row = self.query_one("#explore-genres-row")
        pl_row = self.query_one("#playlists-bar-row")
        sc_pl_row = self.query_one("#sc-playlists-bar-row")

        genres_row.display = (tab == "explore")
        pl_row.display = (tab == "playlists")
        sc_pl_row.display = (tab == "sc_playlists")

        table = self.query_one(TrackTable)
        current_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None

        if tab == "sc_likes":
            if self._likes_cache:
                table.set_tracks(self._likes_cache, current_id, self.storage.is_favorite)
            self._load_sc_likes()
        elif tab == "sc_playlists":
            if self.sc_playlists:
                self._refresh_sc_playlists_ui()
            self._load_sc_playlists()
        elif tab == "queue":
            table.set_tracks(self.queue_mgr.queue, current_id, self.storage.is_favorite)
        elif tab == "favorites":
            favs = self.storage.get_favorites()
            table.set_tracks(favs, current_id, self.storage.is_favorite)
        elif tab == "history":
            hist = self.storage.get_history()
            table.set_tracks(hist, current_id, self.storage.is_favorite)
        elif tab == "playlists":
            self._refresh_playlists_ui()
        elif tab == "explore":
            if not table.get_all_tracks():
                self._load_genre("Lo-Fi")

    def _refresh_playlists_ui(self):
        playlists = self.storage.get_playlists()
        container = self.query_one("#playlist-list-container", Static)
        names = list(playlists.keys())
        if not names:
            container.update(" [dim italic]No playlists created yet. Click 'New Playlist' to create one.[/]")
            table = self.query_one(TrackTable)
            table.set_tracks([], None)
            return

        parts = []
        for name in names:
            count = len(playlists[name])
            is_active = (name == self.active_playlist_name)
            style = "[bold #00f5d4]" if is_active else "[#94a3b8]"
            parts.append(f"{style}📁 {name} [dim]({count})[/][/]")

        container.update("  " + "  |  ".join(parts))

        # Show active playlist tracks
        if not self.active_playlist_name and names:
            self.active_playlist_name = names[0]

        table = self.query_one(TrackTable)
        tracks = playlists.get(self.active_playlist_name, [])
        current_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
        table.set_tracks(tracks, current_id, self.storage.is_favorite)

    def _select_playlist(self, name: str):
        self.active_playlist_name = name
        self._refresh_playlists_ui()

    # --- Async Data Fetchers ---
    @work(thread=True)
    def _load_sc_likes(self):
        if not self.api.get_token():
            self.notify("Press 'L' to sign in and view your SoundCloud Likes.", severity="warning", timeout=5)
            return
        if not self._likes_cache:
            self.notify("Loading your SoundCloud likes...", timeout=3)
        likes = self.api.get_user_likes()
        if likes:
            self._likes_cache = likes
            self.call_from_thread(self._display_tracks, likes, "SoundCloud Likes")

    @work(thread=True)
    def _load_sc_playlists(self):
        if not self.api.get_token():
            self.notify("Press 'L' to sign in and view your online Playlists.", severity="warning", timeout=5)
        elif not self.sc_playlists:
            self.notify("Loading your SoundCloud playlists...", timeout=3)
        online_pls = self.api.get_user_playlists()
        local_pls = []
        for name, tracks in self.storage.get_playlists().items():
            local_pls.append({
                "id": f"local_{name}",
                "title": f"{name}",
                "type": "local",
                "icon": "⚡",
                "track_count": len(tracks),
                "permalink_url": "",
                "tracks": [t.to_dict() if hasattr(t, "to_dict") else t for t in tracks],
            })
        self.sc_playlists = local_pls + online_pls
        self.call_from_thread(self._refresh_sc_playlists_ui)

    def _refresh_sc_playlists_ui(self):
        row = self.query_one("#sc-playlists-bar-row", HorizontalScroll)
        # Remove any non-button children (like static messages)
        for child in list(row.children):
            if not isinstance(child, Button):
                child.remove()

        if not self.sc_playlists:
            row.remove_children()
            row.mount(Static(" [dim italic]No SoundCloud playlists found[/]"))
            return

        existing = list(row.query(Button))
        # Remove excess buttons if sc_playlists has fewer items than before
        while len(existing) > len(self.sc_playlists):
            excess = existing.pop()
            excess.remove()

        for i, p in enumerate(self.sc_playlists):
            cls = "genre-tag-btn active" if i == self.active_sc_playlist_idx else "genre-tag-btn"
            title = p.get("title", f"Playlist {i+1}")
            if len(title) > 28:
                title = title[:25] + "..."
            count = p.get("track_count", 0)
            icon = p.get("icon", "📂")
            count_str = f" ({count})" if count else ""
            label = f"{icon} {title}{count_str}"

            if i < len(existing):
                btn = existing[i]
                btn.label = label
                btn.sc_playlist_idx = i
                btn.set_classes(cls)
            else:
                btn = Button(label, classes=cls)
                btn.sc_playlist_idx = i
                btn.can_focus = False
                row.mount(btn)

        if self.sc_playlists and 0 <= self.active_sc_playlist_idx < len(self.sc_playlists):
            self._load_sc_playlist_tracks(self.active_sc_playlist_idx)

    def _select_sc_playlist(self, idx: int):
        if not self.sc_playlists or idx >= len(self.sc_playlists):
            return
        self.active_sc_playlist_idx = idx
        buttons = list(self.query_one("#sc-playlists-bar-row", HorizontalScroll).query(Button))
        for i, btn in enumerate(buttons):
            if i == idx:
                btn.add_class("active")
            else:
                btn.remove_class("active")
        self._load_sc_playlist_tracks(idx)

    @work(thread=True)
    def _load_sc_playlist_tracks(self, idx: int):
        if not self.sc_playlists or idx >= len(self.sc_playlists):
            return
        pl = self.sc_playlists[idx]
        self.notify(f"Loading '{pl['title']}'...", timeout=3)
        if pl.get("type") == "local":
            raw_tracks = pl.get("tracks", [])
            tracks = [Track.from_dict(t) if isinstance(t, dict) else t for t in raw_tracks]
        else:
            tracks = self.api.get_playlist_full_tracks(pl)
        self.call_from_thread(self._display_tracks, tracks, pl["title"])

    def _display_tracks(self, tracks: List[Track], title: str = ""):
        table = self.query_one(TrackTable)
        current_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
        table.set_tracks(tracks, current_id, self.storage.is_favorite)
        if (not self.queue_mgr.queue or self.player.state == "stopped") and tracks:
            self.queue_mgr.set_queue(tracks, 0)
            self._update_counts()
        if tracks:
            self.notify(f"Loaded {len(tracks)} tracks for '{title}'", timeout=2)
            table.focus()
        else:
            self.notify("No tracks found", timeout=2)

    @work(thread=True)
    def _run_search(self, query: str):
        self.notify(f"Searching SoundCloud for '{query}'...", timeout=3)
        tracks = self.api.search_tracks(query, limit=40)
        self.call_from_thread(self._display_search_results, tracks, query)

    def _display_search_results(self, tracks: List[Track], query: str):
        table = self.query_one(TrackTable)
        current_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
        table.set_tracks(tracks, current_id, self.storage.is_favorite)
        if tracks:
            self.notify(f"Found {len(tracks)} tracks for '{query}'", timeout=3)
            table.focus()
        else:
            self.notify("No tracks found", severity="warning", timeout=3)

    @work(thread=True)
    def _load_genre(self, genre: str):
        self.notify(f"Loading {genre} trending tracks...", timeout=2)
        tracks = self.api.get_genre_tracks(f"{genre} music", limit=35)
        self.call_from_thread(self._display_genre_results, tracks, genre)

    def _display_genre_results(self, tracks: List[Track], genre: str):
        table = self.query_one(TrackTable)
        current_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
        table.set_tracks(tracks, current_id, self.storage.is_favorite)
        self.notify(f"Loaded {len(tracks)} tracks for '{genre}'", timeout=2)

    @work(thread=True)
    def _resolve_url_worker(self, url: str):
        self.notify(f"Resolving URL: {url}", timeout=3)
        kind, result, meta = self.api.resolve_url(url)
        self.call_from_thread(self._handle_url_resolved, kind, result, meta, url)

    def _handle_url_resolved(self, kind: str, result: any, meta: dict, url: str):
        table = self.query_one(TrackTable)

        if kind == "track" and result:
            self.queue_mgr.add_to_queue(result)
            self._update_counts()
            self._start_playback(result)
            self.notify(f"Loaded and playing track: {result.title}", timeout=4)
        elif kind in ("playlist", "user") and result:
            self.queue_mgr.set_queue(result, 0)
            table.set_tracks(result, result[0].id if result else None, self.storage.is_favorite)
            self._update_counts()
            if result:
                self._start_playback(result[0])
            self.notify(f"Loaded {len(result)} tracks from {kind}!", timeout=4)
        else:
            err = meta.get("error", "Unknown error")
            self.notify(f"Failed to resolve URL: {err}", severity="error", timeout=4)

    # --- Action Handlers ---
    def action_toggle_play(self):
        if self.player.state == "playing":
            self.player.pause()
        elif self.player.state == "paused":
            self.player.resume()
        else:
            curr = self.queue_mgr.get_current()
            if curr:
                self._start_playback(curr)
            else:
                table = self.query_one(TrackTable)
                sel = table.get_selected_track()
                if sel:
                    all_tracks = table.get_all_tracks()
                    start_idx = 0
                    for i, t in enumerate(all_tracks):
                        if str(t.id) == str(sel.id):
                            start_idx = i
                            break
                    self.queue_mgr.set_queue(all_tracks, start_index=start_idx)
                    self._update_counts()
                    self._start_playback(sel)
                else:
                    all_tracks = table.get_all_tracks()
                    if all_tracks:
                        self.queue_mgr.set_queue(all_tracks, 0)
                        self._update_counts()
                        self._start_playback(all_tracks[0])

    def action_seek_forward(self):
        self.player.seek(5.0)

    def action_seek_backward(self):
        self.player.seek(-5.0)

    def action_seek_forward_big(self):
        self.player.seek(30.0)

    def action_seek_backward_big(self):
        self.player.seek(-30.0)

    def action_next_track(self):
        if not self.queue_mgr.queue:
            table = self.query_one(TrackTable)
            all_tracks = table.get_all_tracks()
            if all_tracks:
                self.queue_mgr.set_queue(all_tracks, start_index=0)
                self._update_counts()
                self._start_playback(all_tracks[0])
                self.notify(f"Playing next: {all_tracks[0].title}", timeout=2)
                return

        nxt = self.queue_mgr.next_track(is_manual=True)
        if nxt:
            self._start_playback(nxt)
            self.notify(f"Playing next: {nxt.title}", timeout=2)
        else:
            self.notify("End of queue", timeout=2)

    def action_prev_track(self):
        if not self.queue_mgr.queue:
            table = self.query_one(TrackTable)
            all_tracks = table.get_all_tracks()
            if all_tracks:
                self.queue_mgr.set_queue(all_tracks, start_index=0)
                self._update_counts()
                self._start_playback(all_tracks[0])
                self.notify(f"Playing previous: {all_tracks[0].title}", timeout=2)
                return

        prev = self.queue_mgr.previous_track()
        if prev:
            self._start_playback(prev)
            self.notify(f"Playing previous: {prev.title}", timeout=2)

    def action_volume_up(self):
        self.player.volume_up(5)

    def action_volume_down(self):
        self.player.volume_down(5)

    def action_toggle_mute(self):
        self.player.toggle_mute()

    def action_cycle_loop(self):
        new_mode = self.queue_mgr.cycle_loop_mode()
        bar = self.query_one(PlayerBar)
        bar.loop_mode = new_mode
        self.notify(f"Loop mode: {new_mode.label()}", timeout=2)

    def action_toggle_shuffle(self):
        shuff = self.queue_mgr.toggle_shuffle()
        bar = self.query_one(PlayerBar)
        bar.is_shuffled = shuff
        if self.current_tab == "queue":
            table = self.query_one(TrackTable)
            curr_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
            table.set_tracks(self.queue_mgr.queue, curr_id, self.storage.is_favorite)
        self.notify(f"Shuffle: {'ON' if shuff else 'OFF'}", timeout=2)

    def action_focus_search(self):
        self.action_tab_search()
        inp = self.query_one("#search-input", Input)
        inp.focus()

    def action_tab_sc_likes(self):
        self._switch_tab("sc_likes")

    def action_tab_sc_playlists(self):
        self._switch_tab("sc_playlists")

    def action_prev_sc_playlist(self):
        if self.sc_playlists:
            new_idx = (self.active_sc_playlist_idx - 1) % len(self.sc_playlists)
            self._select_sc_playlist(new_idx)

    def action_next_sc_playlist(self):
        if self.sc_playlists:
            new_idx = (self.active_sc_playlist_idx + 1) % len(self.sc_playlists)
            self._select_sc_playlist(new_idx)

    def action_tab_search(self):
        self._switch_tab("search")

    def action_tab_explore(self):
        self._switch_tab("explore")

    def action_tab_queue(self):
        self._switch_tab("queue")

    def action_tab_favorites(self):
        self._switch_tab("sc_likes")

    def action_tab_history(self):
        self._switch_tab("history")

    def action_tab_playlists(self):
        self._switch_tab("playlists")

    def action_add_to_queue(self):
        table = self.query_one(TrackTable)
        sel = table.get_selected_track()
        if sel:
            self.queue_mgr.add_to_queue(sel)
            self._update_counts()
            self.notify(f"Added to queue: {sel.title}", timeout=2)

    def action_toggle_favorite(self):
        table = self.query_one(TrackTable)
        target = table.get_selected_track() or self.queue_mgr.get_current()
        if target:
            is_fav = self.storage.toggle_favorite(target)
            self._update_counts()
            table.update_playing_track(
                self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None,
                is_favorite_checker=self.storage.is_favorite,
            )
            status = "Added to" if is_fav else "Removed from"
            self.notify(f"{status} Favorites: {target.title}", timeout=2)

    def action_add_to_playlist(self):
        table = self.query_one(TrackTable)
        sel = table.get_selected_track() or self.queue_mgr.get_current()
        if not sel:
            self.notify("No track selected", severity="warning", timeout=2)
            return

        playlists = list(self.storage.get_playlists().keys())

        def handle_result(chosen_playlist: Optional[str]):
            if chosen_playlist:
                self.storage.add_to_playlist(chosen_playlist, sel)
                self.notify(f"Added '{sel.title}' to '{chosen_playlist}'", timeout=3)
                if self.current_tab == "playlists":
                    self._refresh_playlists_ui()

        self.push_screen(PlaylistPickerModal(playlists), handle_result)

    def action_new_playlist(self):
        def handle_name(name: Optional[str]):
            if name:
                if self.storage.create_playlist(name):
                    self.active_playlist_name = name
                    self.notify(f"Created playlist '{name}'", timeout=3)
                    self._refresh_playlists_ui()
                else:
                    self.notify(f"Playlist '{name}' already exists or invalid", severity="warning", timeout=3)

        self.push_screen(NewPlaylistModal(), handle_name)

    def action_delete_item(self):
        table = self.query_one(TrackTable)
        sel = table.get_selected_track()
        if not sel:
            return

        if self.current_tab == "queue":
            idx = table.cursor_row
            if idx is not None:
                self.queue_mgr.remove(idx)
                self._update_counts()
                curr_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
                table.set_tracks(self.queue_mgr.queue, curr_id, self.storage.is_favorite)
                self.notify(f"Removed '{sel.title}' from queue", timeout=2)

        elif self.current_tab == "playlists" and self.active_playlist_name:
            self.storage.remove_from_playlist(self.active_playlist_name, sel.id)
            self._refresh_playlists_ui()
            self.notify(f"Removed '{sel.title}' from playlist", timeout=2)

        elif self.current_tab == "favorites":
            self.storage.remove_favorite(sel.id)
            self._update_counts()
            favs = self.storage.get_favorites()
            curr_id = self.queue_mgr.get_current().id if self.queue_mgr.get_current() else None
            table.set_tracks(favs, curr_id, self.storage.is_favorite)
            self.notify(f"Removed '{sel.title}' from favorites", timeout=2)

    def action_clear_queue(self):
        if self.current_tab == "queue":
            self.queue_mgr.clear()
            self._update_counts()
            table = self.query_one(TrackTable)
            table.set_tracks([], None)
            self.notify("Queue cleared", timeout=2)

    def action_open_url_dialog(self):
        def handle_url(url: Optional[str]):
            if url:
                self._resolve_url_worker(url)

        self.push_screen(UrlModal(), handle_url)

    def action_show_help(self):
        self.push_screen(HelpModal())

    def action_quit(self):
        self.player.shutdown()
        self.exit()


SoundCloudApp = LiquidCloudApp  # Backwards compatibility


def main():
    app = LiquidCloudApp()
    app.run()


if __name__ == "__main__":
    main()

