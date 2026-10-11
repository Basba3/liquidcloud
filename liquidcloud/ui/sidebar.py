"""Sidebar navigation menu."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Static


class Sidebar(Widget):
    """Left navigation sidebar."""

    active_tab: reactive[str] = reactive("sc_likes")
    queue_count: reactive[int] = reactive(0)
    fav_count: reactive[int] = reactive(0)
    user_info: reactive[str] = reactive("")
    is_logged_in: reactive[bool] = reactive(False)
    username: reactive[str] = reactive("")

    TABS = [
        ("sc_likes", "❤️ SC Likes", "1"),
        ("sc_playlists", "📂 SC Playlists", "2"),
        ("search", "🔍 Search", "3"),
        ("explore", "🧭 Explore", "4"),
        ("queue", "📑 Queue", "5"),
        ("playlists", "📁 Local Lists", "6"),
        ("history", "🕒 History", "7"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar-container"):
            user_text = self.user_info if self.user_info else "[dim #64748b]Liquid Glass Edition[/]"
            yield Static(
                f"[bold #00f5d4]💧 LIQUID[/][bold #38bdf8]CLOUD[/] 🫧\n{user_text}",
                id="sidebar-logo",
            )
            for tab_id, label, key in self.TABS:
                yield Button(
                    f"[{key}] {label}",
                    id=f"tab-btn-{tab_id}",
                    classes="sidebar-btn" + (" active" if tab_id == self.active_tab else ""),
                )
            yield Static("", id="sidebar-spacer")
            yield Button("[L] 🔑 Sign In", id="tab-btn-auth", classes="sidebar-btn")
            yield Button("[?] Help", id="tab-btn-help", classes="sidebar-btn")

    def watch_user_info(self, info: str):
        try:
            logo = self.query_one("#sidebar-logo", Static)
            user_text = info if info else "[dim #64748b]Liquid Glass Edition[/]"
            logo.update(f"[bold #00f5d4]💧 LIQUID[/][bold #38bdf8]CLOUD[/] 🫧\n{user_text}")
        except Exception:
            pass

    def on_mount(self):
        for btn in self.query(Button):
            btn.can_focus = False

    def watch_active_tab(self, tab: str):
        self._refresh_buttons()

    def watch_queue_count(self, count: int):
        self._refresh_buttons()

    def watch_fav_count(self, count: int):
        self._refresh_buttons()

    def watch_is_logged_in(self, val: bool):
        self._update_auth_label()

    def watch_username(self, val: str):
        self._update_auth_label()

    def _update_auth_label(self):
        try:
            btn = self.query_one("#tab-btn-auth", Button)
            if self.is_logged_in and self.username:
                btn.label = f"[L] 👤 @{self.username[:12]}"
            else:
                btn.label = "[L] 🔑 Sign In"
        except Exception:
            pass

    def _refresh_buttons(self):
        for tab_id, label, key in self.TABS:
            try:
                btn = self.query_one(f"#tab-btn-{tab_id}", Button)
                badge = ""
                if tab_id == "queue" and self.queue_count > 0:
                    badge = f" ({self.queue_count})"
                elif tab_id == "sc_likes" and self.fav_count > 0:
                    badge = f" ({self.fav_count})"

                btn.label = f"[{key}] {label}{badge}"
                if tab_id == self.active_tab:
                    btn.add_class("active")
                else:
                    btn.remove_class("active")
            except Exception:
                pass
