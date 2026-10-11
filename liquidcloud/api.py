import glob
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Track:
    id: str | int
    title: str
    artist: str
    duration_ms: int
    permalink_url: str
    artwork_url: str = ""
    genre: str = ""
    playback_count: int = 0
    likes_count: int = 0
    stream_url: str = ""
    transcodings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def duration_sec(self) -> int:
        if self.duration_ms > 1000:
            return int(self.duration_ms / 1000)
        return int(self.duration_ms)

    @property
    def duration_str(self) -> str:
        secs = self.duration_sec
        m, s = divmod(secs, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "artist": self.artist,
            "duration_ms": self.duration_ms,
            "permalink_url": self.permalink_url,
            "artwork_url": self.artwork_url,
            "genre": self.genre,
            "playback_count": self.playback_count,
            "likes_count": self.likes_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", "Unknown Title"),
            artist=data.get("artist") or data.get("uploader", "Unknown Artist"),
            duration_ms=data.get("duration_ms", 0),
            permalink_url=data.get("permalink_url") or data.get("url", ""),
            artwork_url=data.get("artwork_url", ""),
            genre=data.get("genre", ""),
            playback_count=data.get("playback_count", 0),
            likes_count=data.get("likes_count", 0),
        )


class SoundCloudAPI:
    BASE_URL = "https://api-v2.soundcloud.com"
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"
    FALLBACK_CLIENT_ID = "vI5BsvpTIlavDLl7RDbbcFAPg8kls8Bg"

    def __init__(self, cache_dir: Optional[Path] = None, config_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "liquidcloud")
        self.config_dir = config_dir or (Path.home() / ".config" / "liquidcloud")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.client_id_file = self.cache_dir / "client_id.json"
        self.auth_file = self.config_dir / "auth.json"

        # Fallback check from soundcloud-tui legacy config
        legacy_auth = Path.home() / ".config" / "soundcloud-tui" / "auth.json"
        if not self.auth_file.exists() and legacy_auth.exists():
            try:
                import shutil
                shutil.copy2(legacy_auth, self.auth_file)
            except Exception:
                pass

        self._client_id: Optional[str] = None
        self._token: Optional[str] = None
        self._user_profile: Optional[Dict[str, Any]] = None

    def find_browser_token(self) -> Optional[str]:
        patterns = [
            os.path.expanduser("~/.config/mozilla/firefox/*/cookies.sqlite"),
            os.path.expanduser("~/.mozilla/firefox/*/cookies.sqlite"),
            os.path.expanduser("~/.config/zen/*/cookies.sqlite"),
            os.path.expanduser("~/.config/floorp/*/cookies.sqlite"),
            os.path.expanduser("~/.config/librewolf/*/cookies.sqlite"),
            os.path.expanduser("~/.librewolf/*/cookies.sqlite"),
            os.path.expanduser("~/.var/app/org.mozilla.firefox/.mozilla/firefox/*/cookies.sqlite"),
            os.path.expanduser("~/.var/app/app.zen_browser.zen/.config/zen/*/cookies.sqlite"),
            os.path.expanduser("~/.var/app/io.gitlab.librewolf-community/.librewolf/*/cookies.sqlite"),
            os.path.expanduser("~/snap/firefox/common/.mozilla/firefox/*/cookies.sqlite"),
        ]
        for pat in patterns:
            for p in glob.glob(pat):
                try:
                    conn = sqlite3.connect(f"file:{p}?immutable=1", uri=True)
                    cur = conn.cursor()
                    cur.execute('SELECT value FROM moz_cookies WHERE host LIKE "%soundcloud%" AND name = "oauth_token"')
                    row = cur.fetchone()
                    if row and row[0]:
                        return row[0]
                except Exception:
                    pass
        return None

    def get_token(self) -> Optional[str]:
        if self._token:
            return self._token
        if self.auth_file.exists():
            try:
                with open(self.auth_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    tok = data.get("oauth_token")
                    if tok:
                        self._token = tok
                        return tok
            except Exception:
                pass
        tok = self.find_browser_token()
        if tok:
            self._token = tok
            try:
                with open(self.auth_file, "w", encoding="utf-8") as f:
                    json.dump({"oauth_token": tok}, f, indent=2)
            except Exception:
                pass
            return tok
        return None

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify token validity by requesting the /me profile."""
        token = token.strip()
        if not token:
            return None
        try:
            client_id = self.get_client_id()
            params = urllib.parse.urlencode({"client_id": client_id})
            url = f"{self.BASE_URL}/me?{params}"
            headers = {
                "User-Agent": self.USER_AGENT,
                "Authorization": f"OAuth {token}",
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "id": data.get("id"),
                    "username": data.get("username", "Unknown"),
                    "avatar_url": data.get("avatar_url", ""),
                    "likes_count": data.get("likes_count", 0),
                    "playlist_count": data.get("playlist_count", 0),
                    "permalink_url": data.get("permalink_url", ""),
                }
        except Exception:
            return None

    def set_token(self, token: str) -> Optional[Dict[str, Any]]:
        token = token.strip()
        profile = self.verify_token(token)
        if profile:
            self._token = token
            self._user_profile = profile
            try:
                with open(self.auth_file, "w", encoding="utf-8") as f:
                    json.dump({"oauth_token": token}, f, indent=2)
            except Exception:
                pass
            return profile
        return None

    def logout(self):
        self._token = None
        self._user_profile = None
        if self.auth_file.exists():
            try:
                self.auth_file.unlink()
            except Exception:
                pass

    def get_client_id(self, force_refresh: bool = False) -> str:
        if self._client_id and not force_refresh:
            return self._client_id

        # Try to load cached client_id
        if not force_refresh and self.client_id_file.exists():
            try:
                with open(self.client_id_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    cached_id = data.get("client_id")
                    timestamp = data.get("timestamp", 0)
                    # Cache valid for 24 hours
                    if cached_id and time.time() - timestamp < 86400:
                        self._client_id = cached_id
                        return cached_id
            except Exception:
                pass

        # Extract client_id dynamically from soundcloud web
        extracted_id = self._extract_client_id()
        if extracted_id:
            self._client_id = extracted_id
            try:
                with open(self.client_id_file, "w", encoding="utf-8") as f:
                    json.dump({"client_id": extracted_id, "timestamp": time.time()}, f)
            except Exception:
                pass
            return extracted_id

        # Fallback to recent hardcoded client_id
        self._client_id = self.FALLBACK_CLIENT_ID
        return self._client_id

    def _extract_client_id(self) -> Optional[str]:
        try:
            req = urllib.request.Request(
                "https://soundcloud.com/",
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
            for s_url in reversed(scripts):
                if not s_url.startswith("http"):
                    continue
                try:
                    s_req = urllib.request.Request(
                        s_url, headers={"User-Agent": self.USER_AGENT}
                    )
                    with urllib.request.urlopen(s_req, timeout=5) as s_resp:
                        js_code = s_resp.read().decode("utf-8", errors="ignore")
                    m = re.search(r'client_id[:=]"([0-9a-zA-Z]{32})"', js_code)
                    if m:
                        return m.group(1)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _request_json(self, endpoint: str, params: Dict[str, Any], use_auth: bool = False) -> Dict[str, Any]:
        client_id = self.get_client_id()
        query_params = dict(params)
        query_params["client_id"] = client_id
        encoded_params = urllib.parse.urlencode(query_params)
        url = f"{self.BASE_URL}/{endpoint}?{encoded_params}"

        headers = {"User-Agent": self.USER_AGENT}
        token = self.get_token()
        if token and (use_auth or endpoint.startswith("me")):
            headers["Authorization"] = f"OAuth {token}"

        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                # Client id might be stale, try refreshing once
                new_client_id = self.get_client_id(force_refresh=True)
                query_params["client_id"] = new_client_id
                url = f"{self.BASE_URL}/{endpoint}?{urllib.parse.urlencode(query_params)}"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            raise

    def _parse_track(self, item: Dict[str, Any]) -> Track:
        user = item.get("user") or {}
        artist = user.get("username") or user.get("name") or "Unknown Artist"
        media = item.get("media") or {}
        transcodings = media.get("transcodings") or []

        return Track(
            id=item.get("id", ""),
            title=item.get("title", "Untitled Track"),
            artist=artist,
            duration_ms=item.get("duration", 0),
            permalink_url=item.get("permalink_url", ""),
            artwork_url=item.get("artwork_url") or user.get("avatar_url") or "",
            genre=item.get("genre") or "",
            playback_count=item.get("playback_count") or 0,
            likes_count=item.get("likes_count") or 0,
            transcodings=transcodings,
        )

    def search_tracks(self, query: str, limit: int = 30, offset: int = 0) -> List[Track]:
        try:
            data = self._request_json(
                "search/tracks",
                {"q": query, "limit": limit, "offset": offset},
            )
            tracks = []
            for item in data.get("collection", []):
                if item.get("kind") == "track" or "title" in item:
                    tracks.append(self._parse_track(item))
            return tracks
        except Exception as e:
            return []

    def search_playlists(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            data = self._request_json(
                "search/playlists",
                {"q": query, "limit": limit},
            )
            playlists = []
            for item in data.get("collection", []):
                playlists.append({
                    "id": item.get("id"),
                    "title": item.get("title", "Untitled Playlist"),
                    "user": item.get("user", {}).get("username", "Unknown"),
                    "track_count": item.get("track_count", 0),
                    "permalink_url": item.get("permalink_url", ""),
                    "artwork_url": item.get("artwork_url", ""),
                })
            return playlists
        except Exception:
            return []

    def get_genre_tracks(self, genre: str, limit: int = 30) -> List[Track]:
        # Search for popular genre tags
        return self.search_tracks(genre, limit=limit)

    def resolve_url(self, url: str) -> Tuple[str, Any, Dict[str, Any]]:
        """
        Resolves a SoundCloud URL (track, playlist, or user profile).
        Returns: (type, result, raw_metadata)
        type is 'track', 'playlist', 'user', or 'error'
        """
        try:
            data = self._request_json("resolve", {"url": url})
            kind = data.get("kind")

            if kind == "track":
                return "track", self._parse_track(data), data
            elif kind == "playlist":
                tracks = []
                for t in data.get("tracks", []):
                    # In playlists, sometimes only track IDs or partial tracks are returned
                    if "title" in t:
                        tracks.append(self._parse_track(t))
                return "playlist", tracks, data
            elif kind == "user":
                user_id = data.get("id")
                # Fetch recent tracks by user
                user_tracks = self._request_json(f"users/{user_id}/tracks", {"limit": 30})
                tracks = [self._parse_track(t) for t in user_tracks.get("collection", [])]
                return "user", tracks, data
            else:
                return "unknown", None, data
        except Exception as e:
            return "error", None, {"error": str(e)}

    def get_stream_url(self, track: Track) -> str:
        """
        Resolves direct streaming URL for a track.
        Falls back to permalink_url if direct stream cannot be fetched.
        """
        if track.stream_url:
            return track.stream_url

        client_id = self.get_client_id()

        # If transcodings are present, inspect them
        transcodings = track.transcodings
        if not transcodings and track.id:
            try:
                data = self._request_json(f"tracks/{track.id}", {})
                transcodings = data.get("media", {}).get("transcodings", [])
                track.transcodings = transcodings
            except Exception:
                pass

        # Prefer progressive (mp3/direct) over hls
        chosen_tc = None
        for tc in transcodings:
            fmt = tc.get("format", {})
            if fmt.get("protocol") == "progressive":
                chosen_tc = tc
                break
        if not chosen_tc and transcodings:
            chosen_tc = transcodings[0]

        if chosen_tc and "url" in chosen_tc:
            stream_api = f"{chosen_tc['url']}?client_id={client_id}"
            try:
                req = urllib.request.Request(stream_api, headers={"User-Agent": self.USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    stream_data = json.loads(resp.read().decode("utf-8"))
                    url = stream_data.get("url")
                    if url:
                        track.stream_url = url
                        return url
            except Exception:
                pass

        # Fallback to permalink URL (mpv handles via yt-dlp)
        return track.permalink_url

    def get_me(self) -> Optional[Dict[str, Any]]:
        if self._user_profile:
            return self._user_profile
        token = self.get_token()
        if not token:
            return None
        try:
            data = self._request_json("me", {}, use_auth=True)
            self._user_profile = {
                "id": data.get("id"),
                "username": data.get("username", "Unknown"),
                "avatar_url": data.get("avatar_url", ""),
                "likes_count": data.get("likes_count", 0),
                "playlist_count": data.get("playlist_count", 0),
                "permalink_url": data.get("permalink_url", ""),
            }
            return self._user_profile
        except Exception:
            return None

    def get_user_likes(self, user_id: Optional[int | str] = None, limit: int = 50) -> List[Track]:
        if not user_id:
            me = self.get_me()
            if not me:
                return []
            user_id = me["id"]
        try:
            data = self._request_json(f"users/{user_id}/likes", {"limit": limit})
            tracks = []
            for item in data.get("collection", []):
                t = item.get("track")
                if t:
                    tracks.append(self._parse_track(t))
            return tracks
        except Exception:
            return []

    def get_user_playlists(self, user_id: Optional[int | str] = None) -> List[Dict[str, Any]]:
        token = self.get_token()
        if token:
            try:
                data = self._request_json("me/library/all", {"limit": 50}, use_auth=True)
                playlists = []
                for item in data.get("collection", []):
                    typ = item.get("type", "")
                    pl = item.get("playlist") or item.get("system_playlist")
                    if not pl:
                        continue
                    title = pl.get("title", "Untitled")
                    count = pl.get("track_count")
                    raw_tracks = pl.get("tracks", [])
                    if count is None and raw_tracks:
                        count = len(raw_tracks)
                    elif count is None:
                        count = 0

                    icon = "📂"
                    if typ == "system-playlist-like":
                        icon = "🎛️"
                    elif typ == "playlist-like":
                        icon = "❤️"

                    playlists.append({
                        "id": pl.get("id"),
                        "urn": pl.get("urn"),
                        "type": typ,
                        "icon": icon,
                        "title": title,
                        "track_count": count,
                        "permalink_url": pl.get("permalink_url", ""),
                        "tracks": raw_tracks,
                    })
                if playlists:
                    return playlists
            except Exception as e:
                logger.error(f"Error fetching me/library/all: {e}")

        # Fallback to users/{user_id}/playlists
        if not user_id:
            me = self.get_me()
            if not me:
                return []
            user_id = me["id"]
        try:
            data = self._request_json(f"users/{user_id}/playlists", {"limit": 30})
            playlists = []
            for p in data.get("collection", []):
                playlists.append({
                    "id": p.get("id"),
                    "title": p.get("title", "Untitled Playlist"),
                    "type": "playlist",
                    "icon": "📂",
                    "track_count": p.get("track_count", 0),
                    "permalink_url": p.get("permalink_url", ""),
                    "tracks": p.get("tracks", []),
                })
            return playlists
        except Exception:
            return []

    def get_playlist_full_tracks(self, playlist_dict: Dict[str, Any]) -> List[Track]:
        tracks_raw = playlist_dict.get("tracks", [])
        # If tracks not provided inline (e.g. for liked playlists in library/all), fetch playlist details
        if not tracks_raw and playlist_dict.get("id"):
            try:
                pid = playlist_dict["id"]
                data = self._request_json(f"playlists/{pid}", {}, use_auth=True)
                tracks_raw = data.get("tracks", [])
                playlist_dict["tracks"] = tracks_raw
            except Exception as e:
                logger.error(f"Error fetching playlist details for {playlist_dict.get('id')}: {e}")

        full_tracks: List[Track] = []
        missing_ids: List[str] = []

        for item in tracks_raw:
            if isinstance(item, dict) and "title" in item:
                full_tracks.append(self._parse_track(item))
            elif isinstance(item, dict) and "id" in item:
                missing_ids.append(str(item["id"]))
            elif isinstance(item, (int, str)):
                missing_ids.append(str(item))

        if missing_ids:
            try:
                for i in range(0, len(missing_ids), 50):
                    chunk = missing_ids[i:i+50]
                    ids_param = ",".join(chunk)
                    res = self._request_json("tracks", {"ids": ids_param})
                    if isinstance(res, list):
                        for t in res:
                            full_tracks.append(self._parse_track(t))
            except Exception:
                pass

        return full_tracks
