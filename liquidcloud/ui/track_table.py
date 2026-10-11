"""Interactive Track Table widget using Textual DataTable."""

from typing import List, Optional
from textual.widgets import DataTable

from liquidcloud.api import Track


class TrackTable(DataTable):
    """DataTable specialized for rendering tracks with formatted columns."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._tracks: List[Track] = []
        self._current_track_id: Optional[str] = None

    def on_mount(self):
        self.add_column("#", width=4, key="idx")
        self.add_column("  ", width=3, key="status")
        self.add_column("Title", width=38, key="title")
        self.add_column("Artist", width=22, key="artist")
        self.add_column("Duration", width=9, key="dur")
        self.add_column("Likes", width=9, key="likes")
        self.add_column("Plays", width=10, key="plays")

    @staticmethod
    def format_count(count: int) -> str:
        if not count:
            return "-"
        if count >= 1_000_000:
            return f"{count / 1_000_000:.1f}M"
        if count >= 1_000:
            return f"{count / 1_000:.1f}K"
        return str(count)

    def set_tracks(
        self,
        tracks: List[Track],
        current_track_id: Optional[str | int] = None,
        is_favorite_checker: Optional[callable] = None,
    ):
        self._tracks = list(tracks)
        self._current_track_id = str(current_track_id) if current_track_id else None
        self.clear()

        for idx, track in enumerate(tracks, 1):
            is_playing = (
                self._current_track_id is not None
                and str(track.id) == self._current_track_id
            )
            is_fav = is_favorite_checker(track.id) if is_favorite_checker else False

            status_icon = ""
            if is_playing:
                status_icon = "[bold #00f5d4]▶[/]"
            elif is_fav:
                status_icon = "[#38bdf8]♥[/]"

            title_styled = (
                f"[bold #00f5d4]{track.title}[/]" if is_playing else track.title
            )
            artist_styled = (
                f"[bold #70d6ff]{track.artist}[/]" if is_playing else track.artist
            )

            self.add_row(
                str(idx),
                status_icon,
                title_styled,
                artist_styled,
                track.duration_str,
                self.format_count(track.likes_count),
                self.format_count(track.playback_count),
                key=str(track.id),
            )

    def update_playing_track(
        self,
        current_track_id: Optional[str | int],
        is_favorite_checker: Optional[callable] = None,
    ):
        old_id = self._current_track_id
        new_id = str(current_track_id) if current_track_id else None
        self._current_track_id = new_id

        # Update old track row in place
        if old_id and old_id in self.rows:
            try:
                old_track = next((t for t in self._tracks if str(t.id) == old_id), None)
                if old_track:
                    is_fav = is_favorite_checker(old_track.id) if is_favorite_checker else False
                    self.update_cell(old_id, "status", "[#38bdf8]♥[/]" if is_fav else "")
                    self.update_cell(old_id, "title", old_track.title)
                    self.update_cell(old_id, "artist", old_track.artist)
            except Exception:
                pass

        # Update new track row in place
        if new_id and new_id in self.rows:
            try:
                new_track = next((t for t in self._tracks if str(t.id) == new_id), None)
                if new_track:
                    self.update_cell(new_id, "status", "[bold #00f5d4]▶[/]")
                    self.update_cell(new_id, "title", f"[bold #00f5d4]{new_track.title}[/]")
                    self.update_cell(new_id, "artist", f"[bold #70d6ff]{new_track.artist}[/]")
            except Exception:
                pass

    def get_selected_track(self) -> Optional[Track]:
        if not self._tracks:
            return None
        row_idx = self.cursor_row
        if row_idx is not None and 0 <= row_idx < len(self._tracks):
            return self._tracks[row_idx]
        return None

    def get_all_tracks(self) -> List[Track]:
        return list(self._tracks)
