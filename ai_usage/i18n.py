"""Internationalization: all user-facing text lives here.

Add a language by appending an entry to :data:`LANGUAGES` and filling in the
three tables (:data:`_TEXT`, :data:`_WINDOW_LABELS`, :data:`_WEEKDAYS`). Nothing
else in the app hard-codes a human string, so a new locale needs no other edits.

The :class:`Translator` wraps a single language and exposes intent-named methods
(``refresh()``, ``row()``, ``reset()`` …) rather than raw dictionary lookups, so
call sites read naturally and missing keys are impossible to mistype.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import ErrorKind

ZH_HANS = "zh-Hans"
ZH_HANT = "zh-Hant"
EN = "en"

DEFAULT_LANGUAGE = ZH_HANS

# (code, autonym) — the autonym is shown the same regardless of current UI
# language, which is the conventional way to present a language picker.
LANGUAGES: list[tuple[str, str]] = [
    (ZH_HANS, "简体中文"),
    (ZH_HANT, "繁體中文"),
    (EN, "English"),
]


def is_supported(code: str) -> bool:
    return code in {c for c, _ in LANGUAGES}


# Plain labels and templates. Templates use str.format placeholders.
_TEXT: dict[str, dict[str, str]] = {
    ZH_HANS: {
        "starting": "启动中…",
        "refresh": "刷新",
        "open_site": "打开 claude.ai",
        "quit": "退出",
        "headline_menu": "标题显示",
        "language_menu": "语言",
        "row": "{label}  {bar}  剩 {pct}%",
        "reset": "{label}窗口 {time} 重置",
        "weekday_time": "{weekday} {time}",
        "error.cookie_unavailable": "读取登录信息失败,请确认已安装并登录 Claude 桌面端",
        "error.decrypt_failed": "解密登录信息失败",
        "error.session_expired": "登录已过期,请重新登录 Claude 桌面端",
        "error.no_subscription": "未找到 Claude 订阅",
        "error.network": "网络错误",
        "error.server": "服务器返回异常",
        "error.unknown": "出错了",
    },
    ZH_HANT: {
        "starting": "啟動中…",
        "refresh": "重新整理",
        "open_site": "開啟 claude.ai",
        "quit": "結束",
        "headline_menu": "標題顯示",
        "language_menu": "語言",
        "row": "{label}  {bar}  剩 {pct}%",
        "reset": "{label}時段 {time} 重設",
        "weekday_time": "{weekday} {time}",
        "error.cookie_unavailable": "讀取登入資訊失敗,請確認已安裝並登入 Claude 桌面端",
        "error.decrypt_failed": "解密登入資訊失敗",
        "error.session_expired": "登入已過期,請重新登入 Claude 桌面端",
        "error.no_subscription": "找不到 Claude 訂閱",
        "error.network": "網路錯誤",
        "error.server": "伺服器回應異常",
        "error.unknown": "發生錯誤",
    },
    EN: {
        "starting": "Starting…",
        "refresh": "Refresh",
        "open_site": "Open claude.ai",
        "quit": "Quit",
        "headline_menu": "Menu bar shows",
        "language_menu": "Language",
        "row": "{label}  {bar}  {pct}% left",
        "reset": "{label} resets {time}",
        "weekday_time": "{weekday} {time}",
        "error.cookie_unavailable": "Can't read your Claude login — install and sign in to the Claude desktop app",
        "error.decrypt_failed": "Failed to decrypt your Claude login",
        "error.session_expired": "Session expired — sign in to the Claude desktop app again",
        "error.no_subscription": "No Claude subscription found",
        "error.network": "Network error",
        "error.server": "Unexpected server response",
        "error.unknown": "Something went wrong",
    },
}

# Per-window display labels, keyed by the stable window key from claude.py.
_WINDOW_LABELS: dict[str, dict[str, str]] = {
    ZH_HANS: {"5-hour": "5小时", "7-day": "7天"},
    ZH_HANT: {"5-hour": "5小時", "7-day": "7天"},
    EN: {"5-hour": "5-hour", "7-day": "7-day"},
}

_WEEKDAYS: dict[str, list[str]] = {
    ZH_HANS: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
    ZH_HANT: ["週一", "週二", "週三", "週四", "週五", "週六", "週日"],
    EN: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}

# Error kinds whose technical detail is worth appending for the user.
_DETAILED_ERRORS = {ErrorKind.NETWORK, ErrorKind.SERVER, ErrorKind.UNKNOWN}


@dataclass(frozen=True)
class Translator:
    """All text for one language. Falls back to the default language per key."""

    lang: str

    def _text(self, key: str) -> str:
        table = _TEXT.get(self.lang, _TEXT[DEFAULT_LANGUAGE])
        return table.get(key) or _TEXT[DEFAULT_LANGUAGE][key]

    # Simple labels ---------------------------------------------------------
    def starting(self) -> str:
        return self._text("starting")

    def refresh(self) -> str:
        return self._text("refresh")

    def open_site(self) -> str:
        return self._text("open_site")

    def quit(self) -> str:
        return self._text("quit")

    def headline_menu(self) -> str:
        return self._text("headline_menu")

    def language_menu(self) -> str:
        return self._text("language_menu")

    # Composed strings ------------------------------------------------------
    def window_label(self, window_key: str) -> str:
        labels = _WINDOW_LABELS.get(self.lang, _WINDOW_LABELS[DEFAULT_LANGUAGE])
        return labels.get(window_key, window_key)

    def row(self, label: str, bar: str, pct: int) -> str:
        return self._text("row").format(label=label, bar=bar, pct=pct)

    def reset(self, label: str, resets_at: datetime | None) -> str:
        return self._text("reset").format(label=label, time=self._reset_time(resets_at))

    def error(self, kind: ErrorKind, detail: str = "") -> str:
        message = self._text(f"error.{kind.value}")
        if detail and kind in _DETAILED_ERRORS:
            return f"{message} ({detail})"
        return message

    # Helpers ---------------------------------------------------------------
    def _reset_time(self, dt: datetime | None) -> str:
        """Local time: 'HH:MM' if today, else '<weekday> HH:MM'."""
        if dt is None:
            return "—"
        local = dt.astimezone()
        time_str = f"{local:%H:%M}"
        if local.date() == datetime.now().astimezone().date():
            return time_str
        weekdays = _WEEKDAYS.get(self.lang, _WEEKDAYS[DEFAULT_LANGUAGE])
        return self._text("weekday_time").format(weekday=weekdays[local.weekday()], time=time_str)
