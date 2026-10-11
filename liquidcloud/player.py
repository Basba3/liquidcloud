"""mpv audio player with Unix domain socket IPC."""

import atexit
import json
import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MpvPlayer:
    def __init__(self):
        self.sock_path = os.path.join(
            tempfile.gettempdir(), f"liquidcloud_mpv_{os.getpid()}_{int(time.time())}.sock"
        )
        self.process: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._running = False
        self._event_thread: Optional[threading.Thread] = None

        # Playback states
        self.position: float = 0.0
        self.duration: float = 0.0
        self.is_paused: bool = False
        self.is_idle: bool = True
        self.volume: int = 80
        self.is_muted: bool = False
        self.state: str = "stopped"  # "playing", "paused", "buffering", "stopped"
        self.current_title: str = ""
        self._manual_interrupt: bool = False
        self._last_track_end_time: float = 0.0

        # Callbacks
        self.on_time_update: Optional[Callable[[float, float], None]] = None
        self.on_track_end: Optional[Callable[[], None]] = None
        self.on_state_change: Optional[Callable[[str], None]] = None
        self.on_volume_change: Optional[Callable[[int, bool], None]] = None

        self._start_mpv()
        atexit.register(self.shutdown)

    def _start_mpv(self):
        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except OSError:
                pass

        cmd = [
            "mpv",
            "--no-config",
            "--no-video",
            "--audio-display=no",
            "--idle=yes",
            "--keep-open=no",
            f"--input-ipc-server={self.sock_path}",
            "--really-quiet",
            "--demuxer-max-bytes=8M",
            "--demuxer-readahead-secs=15",
            "--gapless-audio=yes",
            "--ao=pipewire,pulse,alsa,jack",
            f"--volume={self.volume}",
        ]

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )

        # Wait for socket to become available
        connected = False
        for _ in range(30):
            time.sleep(0.08)
            if os.path.exists(self.sock_path):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.connect(self.sock_path)
                    self.sock = s
                    connected = True
                    break
                except Exception:
                    pass

        if not connected:
            logger.error("Failed to connect to mpv IPC socket")
            return

        self._running = True
        self._last_time_update = 0.0
        # Subscribe to property changes
        props = ["time-pos", "duration", "pause", "volume", "mute", "eof-reached"]
        for idx, prop in enumerate(props, start=1):
            self._send_command(["observe_property", idx, prop])

        # Start background event listener thread
        self._event_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_thread.start()

    def _send_command(self, cmd_args: list) -> Optional[dict]:
        with self._lock:
            if not self.sock or not self._running:
                return None
            try:
                msg = json.dumps({"command": cmd_args}) + "\n"
                self.sock.sendall(msg.encode("utf-8"))
            except Exception as e:
                logger.debug(f"Error sending command {cmd_args}: {e}")
                return None
        return None

    def _event_loop(self):
        buffer = b""
        while self._running and self.sock:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.decode("utf-8", errors="ignore"))
                        self._handle_mpv_message(data)
                    except Exception:
                        pass
            except Exception:
                if not self._running:
                    break
                time.sleep(0.1)

    def _handle_mpv_message(self, msg: dict):
        event = msg.get("event")

        if event == "property-change":
            name = msg.get("name")
            val = msg.get("data")

            if name == "time-pos" and val is not None:
                try:
                    self.position = float(val)
                    now = time.time()
                    if now - self._last_time_update >= 0.5:
                        self._last_time_update = now
                        if self.on_time_update:
                            self.on_time_update(self.position, self.duration)
                except (ValueError, TypeError):
                    pass

            elif name == "duration" and val is not None:
                try:
                    self.duration = float(val)
                    if self.on_time_update:
                        self.on_time_update(self.position, self.duration)
                except (ValueError, TypeError):
                    pass

            elif name == "pause":
                self.is_paused = bool(val)
                new_state = "paused" if self.is_paused else ("playing" if not self.is_idle else "stopped")
                if self.state != new_state:
                    self.state = new_state
                    if self.on_state_change:
                        self.on_state_change(self.state)

            elif name == "volume" and val is not None:
                try:
                    self.volume = int(round(float(val)))
                    if self.on_volume_change:
                        self.on_volume_change(self.volume, self.is_muted)
                except (ValueError, TypeError):
                    pass

            elif name == "mute":
                self.is_muted = bool(val)
                if self.on_volume_change:
                    self.on_volume_change(self.volume, self.is_muted)

            elif name == "eof-reached" and val is True:
                if not self.is_idle and self.state == "playing":
                    self._trigger_track_end()

        elif event == "start-file":
            self.is_idle = False
            self.state = "buffering"
            if self.on_state_change:
                self.on_state_change(self.state)

        elif event == "file-loaded":
            self._manual_interrupt = False
            self.is_idle = False
            self.state = "playing"
            if self.on_state_change:
                self.on_state_change(self.state)

        elif event == "end-file":
            reason = msg.get("reason")
            logger.info(f"MPV end-file event with reason: {reason}")
            # ONLY regular EOF should advance to the next track!
            # Reason 'stop' means user skipped or loaded new track manually.
            if reason == "eof" and not self._manual_interrupt:
                self._trigger_track_end()
            elif reason == "error" and not self._manual_interrupt and self.state == "playing":
                logger.warning("MPV playback encountered error, advancing track")
                self._trigger_track_end()

        elif event == "idle":
            self.is_idle = True
            if self.state != "stopped" and self.state != "buffering":
                self.state = "stopped"
                if self.on_state_change:
                    self.on_state_change(self.state)

    def _trigger_track_end(self):
        now = time.time()
        if now - getattr(self, "_last_track_end_time", 0.0) < 1.5:
            return
        self._last_track_end_time = now
        self.is_idle = True
        self.position = 0.0
        self.state = "stopped"
        if self.on_state_change:
            self.on_state_change(self.state)
        if self.on_track_end:
            self.on_track_end()

    def play(self, url: str, title: str = ""):
        self._manual_interrupt = True
        self.current_title = title
        self.position = 0.0
        self.duration = 0.0
        self.is_idle = False
        self.is_paused = False
        self.state = "buffering"
        if self.on_state_change:
            self.on_state_change(self.state)
        self._send_command(["loadfile", url, "replace"])

    def pause(self):
        self._send_command(["set_property", "pause", True])
        self.is_paused = True
        self.state = "paused"
        if self.on_state_change:
            self.on_state_change(self.state)

    def resume(self):
        self._send_command(["set_property", "pause", False])
        self.is_paused = False
        self.state = "playing"
        if self.on_state_change:
            self.on_state_change(self.state)

    def toggle_pause(self):
        if self.is_paused:
            self.resume()
        elif self.state == "playing":
            self.pause()

    def stop(self):
        self._manual_interrupt = True
        self._send_command(["stop"])
        self.state = "stopped"
        self.position = 0.0
        self.is_idle = True
        if self.on_state_change:
            self.on_state_change(self.state)

    def seek(self, seconds: float):
        self._send_command(["seek", seconds, "relative"])

    def seek_absolute(self, position: float):
        self._send_command(["seek", position, "absolute"])

    def set_volume(self, vol: int):
        vol = max(0, min(100, vol))
        self.volume = vol
        self._send_command(["set_property", "volume", vol])
        if self.on_volume_change:
            self.on_volume_change(self.volume, self.is_muted)

    def volume_up(self, step: int = 5):
        self.set_volume(self.volume + step)

    def volume_down(self, step: int = 5):
        self.set_volume(self.volume - step)

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        self._send_command(["set_property", "mute", self.is_muted])
        if self.on_volume_change:
            self.on_volume_change(self.volume, self.is_muted)

    def shutdown(self):
        self._running = False
        if self.sock:
            try:
                self._send_command(["quit"])
                self.sock.close()
            except Exception:
                pass
            self.sock = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        if os.path.exists(self.sock_path):
            try:
                os.remove(self.sock_path)
            except Exception:
                pass
