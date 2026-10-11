"""Storage management for favorites, history, playlists, and settings."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from liquidcloud.api import Track


class Storage:
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or (Path.home() / ".config" / "liquidcloud")
        self.base_dir.mkdir(parents=True, exist_ok=True)
        # Migrate or fallback from soundcloud-tui if exists
        old_dir = Path.home() / ".config" / "soundcloud-tui"
        if old_dir.exists() and self.base_dir != old_dir:
            for old_file in old_dir.glob("*.json"):
                new_file = self.base_dir / old_file.name
                if not new_file.exists():
                    try:
                        import shutil
                        shutil.copy2(old_file, new_file)
                    except Exception:
                        pass

        self.fav_file = self.base_dir / "favorites.json"
        self.hist_file = self.base_dir / "history.json"
        self.playlist_file = self.base_dir / "playlists.json"
        self.settings_file = self.base_dir / "settings.json"

    def _load_json(self, path: Path, default: any) -> any:
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    def _save_json(self, path: Path, data: any):
        tmp = path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    # --- Favorites ---
    def get_favorites(self) -> List[Track]:
        raw = self._load_json(self.fav_file, [])
        return [Track.from_dict(t) for t in raw]

    def is_favorite(self, track_id: str | int) -> bool:
        favs = self._load_json(self.fav_file, [])
        return any(str(t.get("id")) == str(track_id) for t in favs)

    def add_favorite(self, track: Track) -> bool:
        favs = self._load_json(self.fav_file, [])
        if any(str(t.get("id")) == str(track.id) for t in favs):
            return False
        favs.insert(0, track.to_dict())
        self._save_json(self.fav_file, favs)
        return True

    def remove_favorite(self, track_id: str | int) -> bool:
        favs = self._load_json(self.fav_file, [])
        orig_len = len(favs)
        favs = [t for t in favs if str(t.get("id")) != str(track_id)]
        if len(favs) != orig_len:
            self._save_json(self.fav_file, favs)
            return True
        return False

    def toggle_favorite(self, track: Track) -> bool:
        if self.is_favorite(track.id):
            self.remove_favorite(track.id)
            return False
        else:
            self.add_favorite(track)
            return True

    # --- History ---
    def get_history(self) -> List[Track]:
        raw = self._load_json(self.hist_file, [])
        return [Track.from_dict(t) for t in raw]

    def add_history(self, track: Track, max_items: int = 100):
        hist = self._load_json(self.hist_file, [])
        # Remove previous occurrence if any
        hist = [t for t in hist if str(t.get("id")) != str(track.id)]
        hist.insert(0, track.to_dict())
        if len(hist) > max_items:
            hist = hist[:max_items]
        self._save_json(self.hist_file, hist)

    def clear_history(self):
        self._save_json(self.hist_file, [])

    # --- Playlists ---
    def get_playlists(self) -> Dict[str, List[Track]]:
        raw = self._load_json(self.playlist_file, {})
        result = {}
        for name, tracks in raw.items():
            result[name] = [Track.from_dict(t) for t in tracks]
        return result

    def create_playlist(self, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        data = self._load_json(self.playlist_file, {})
        if name in data:
            return False
        data[name] = []
        self._save_json(self.playlist_file, data)
        return True

    def add_to_playlist(self, name: str, track: Track) -> bool:
        data = self._load_json(self.playlist_file, {})
        if name not in data:
            data[name] = []
        # check duplicate
        if any(str(t.get("id")) == str(track.id) for t in data[name]):
            return False
        data[name].append(track.to_dict())
        self._save_json(self.playlist_file, data)
        return True

    def remove_from_playlist(self, name: str, track_id: str | int) -> bool:
        data = self._load_json(self.playlist_file, {})
        if name not in data:
            return False
        orig_len = len(data[name])
        data[name] = [t for t in data[name] if str(t.get("id")) != str(track_id)]
        if len(data[name]) != orig_len:
            self._save_json(self.playlist_file, data)
            return True
        return False

    def delete_playlist(self, name: str) -> bool:
        data = self._load_json(self.playlist_file, {})
        if name in data:
            del data[name]
            self._save_json(self.playlist_file, data)
            return True
        return False

    # --- Settings ---
    def get_settings(self) -> dict:
        return self._load_json(self.settings_file, {"volume": 80, "loop_mode": "off"})

    def save_settings(self, settings: dict):
        self._save_json(self.settings_file, settings)
