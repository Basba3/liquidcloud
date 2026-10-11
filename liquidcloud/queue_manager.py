"""Playback queue and playlist state manager."""

from enum import Enum
import random
from typing import List, Optional

from liquidcloud.api import Track


class LoopMode(str, Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

    def label(self) -> str:
        if self == LoopMode.TRACK:
            return "🔂 TRACK"
        elif self == LoopMode.QUEUE:
            return "🔁 QUEUE"
        return "➡️ OFF"


class QueueManager:
    def __init__(self):
        self.queue: List[Track] = []
        self.current_index: int = -1
        self.loop_mode: LoopMode = LoopMode.OFF
        self.shuffle_enabled: bool = False
        self._original_queue: List[Track] = []

    def set_queue(self, tracks: List[Track], start_index: int = 0):
        self.queue = list(tracks)
        self._original_queue = list(tracks)
        self.current_index = max(0, min(start_index, len(self.queue) - 1)) if self.queue else -1

    def add_to_queue(self, track: Track):
        self.queue.append(track)
        self._original_queue.append(track)
        if self.current_index == -1:
            self.current_index = 0

    def add_next(self, track: Track):
        if self.current_index == -1:
            self.queue.append(track)
            self._original_queue.append(track)
            self.current_index = 0
        else:
            self.queue.insert(self.current_index + 1, track)
            self._original_queue.append(track)

    def remove(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self.queue):
            removed = self.queue.pop(index)
            if index < self.current_index:
                self.current_index -= 1
            elif index == self.current_index and self.current_index >= len(self.queue):
                self.current_index = len(self.queue) - 1
            return removed
        return None

    def clear(self):
        self.queue.clear()
        self._original_queue.clear()
        self.current_index = -1

    def get_current(self) -> Optional[Track]:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

    def jump_to(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self.queue):
            self.current_index = index
            return self.queue[self.current_index]
        return None

    def next_track(self, is_manual: bool = False) -> Optional[Track]:
        if not self.queue:
            return None

        # If looping single track and triggered automatically (not manual skip)
        if not is_manual and self.loop_mode == LoopMode.TRACK:
            return self.get_current()

        if self.current_index + 1 < len(self.queue):
            self.current_index += 1
            return self.queue[self.current_index]

        # End of queue reached
        if self.loop_mode == LoopMode.QUEUE:
            self.current_index = 0
            return self.queue[self.current_index]

        return None

    def previous_track(self) -> Optional[Track]:
        if not self.queue:
            return None

        if self.current_index > 0:
            self.current_index -= 1
            return self.queue[self.current_index]

        if self.loop_mode == LoopMode.QUEUE:
            self.current_index = len(self.queue) - 1
            return self.queue[self.current_index]

        return self.get_current()

    def cycle_loop_mode(self) -> LoopMode:
        if self.loop_mode == LoopMode.OFF:
            self.loop_mode = LoopMode.TRACK
        elif self.loop_mode == LoopMode.TRACK:
            self.loop_mode = LoopMode.QUEUE
        else:
            self.loop_mode = LoopMode.OFF
        return self.loop_mode

    def toggle_shuffle(self) -> bool:
        self.shuffle_enabled = not self.shuffle_enabled
        if self.shuffle_enabled and len(self.queue) > 1:
            current = self.get_current()
            remaining = [t for i, t in enumerate(self.queue) if i != self.current_index]
            random.shuffle(remaining)
            if current:
                self.queue = [current] + remaining
                self.current_index = 0
            else:
                self.queue = remaining
                self.current_index = 0
        elif not self.shuffle_enabled and self._original_queue:
            current = self.get_current()
            self.queue = list(self._original_queue)
            if current:
                try:
                    self.current_index = next(
                        i for i, t in enumerate(self.queue) if str(t.id) == str(current.id)
                    )
                except StopIteration:
                    self.current_index = 0
        return self.shuffle_enabled
