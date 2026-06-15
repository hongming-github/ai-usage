"""Menu bar app: shows remaining Claude Pro/Max quota in the macOS status bar.

This module is the view layer. It owns no text of its own — every label comes
from :mod:`ai_usage.i18n` via a :class:`~ai_usage.i18n.Translator` — and no
network logic — that lives in :mod:`ai_usage.claude`. Its job is to turn a
:class:`~ai_usage.claude.Usage` (or an :class:`~ai_usage.errors.AppError`) into
menu rows and keep them refreshed.
"""

from __future__ import annotations

import webbrowser

import rumps
from AppKit import (
    NSAttributedString,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
)

from . import config, i18n
from .claude import ClaudeClient, Usage
from .errors import AppError, ErrorKind
from .i18n import Translator

REFRESH_SECONDS = 120
BAR_WIDTH = 10

# Remaining-quota thresholds (percent) for the traffic-light tiers.
_LOW = 15
_MEDIUM = 40

CONFIG_HEADLINE = "headline"
CONFIG_LANGUAGE = "language"
DEFAULT_HEADLINE = "5-hour"


# --- pure presentation helpers (language-independent) ----------------------


def _dot(remaining: int) -> str:
    """Traffic-light emoji for the headline remaining percentage."""
    if remaining <= _LOW:
        return "🔴"
    if remaining <= _MEDIUM:
        return "🟡"
    return "🟢"


def _status_color(remaining: int):
    """Muted traffic-light color for a tier.

    Toned down from the vivid system colors so the menu isn't neon; mid-tones
    stay readable on both light and dark menu backgrounds.
    """
    if remaining <= _LOW:
        rgb = (0.82, 0.20, 0.18)  # red
    elif remaining <= _MEDIUM:
        rgb = (0.80, 0.50, 0.05)  # amber
    else:
        rgb = (0.18, 0.58, 0.28)  # green
    return NSColor.colorWithSRGBRed_green_blue_alpha_(*rgb, 1.0)


def _bar(remaining: int) -> str:
    """A block gauge whose filled cells represent the remaining quota."""
    filled = max(0, min(BAR_WIDTH, round(remaining / 100 * BAR_WIDTH)))
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def _display_width(text: str) -> int:
    """Visual width in half-cells: CJK glyphs count as 2, ASCII as 1."""
    return sum(2 if ord(c) > 0x2E7F else 1 for c in text)


def _pad_to(text: str, target: int) -> str:
    """Right-pad `text` to `target` half-cells (full-width then ASCII spaces).

    The menu uses a proportional font, so plain-space padding can't align CJK
    columns; matching the visual half-cell width does.
    """
    gap = max(0, target - _display_width(text))
    return text + "　" * (gap // 2) + " " * (gap % 2)


def _info_row(text: str, color=None, bold: bool = False) -> rumps.MenuItem:
    """A non-action menu row that renders in full color (not disabled-gray).

    Menu items without a callback are drawn grayed out; a no-op callback keeps
    the text crisp. `bold` lifts contrast on the translucent menu background
    without needing a very dark color.
    """
    item = rumps.MenuItem(text, callback=lambda _: None)
    attributes = {NSForegroundColorAttributeName: color or NSColor.labelColor()}
    if bold:
        size = NSFont.menuFontOfSize_(0.0).pointSize()
        attributes[NSFontAttributeName] = NSFont.systemFontOfSize_weight_(size, 0.3)  # semibold
    item._menuitem.setAttributedTitle_(
        NSAttributedString.alloc().initWithString_attributes_(text, attributes)
    )
    return item


def _checkable(title: str, selected: bool, callback) -> rumps.MenuItem:
    item = rumps.MenuItem(title, callback=callback)
    item.state = 1 if selected else 0
    return item


# --- app -------------------------------------------------------------------


class AIUsageApp(rumps.App):
    def __init__(self) -> None:
        super().__init__("AI Usage", title="…", quit_button=None)
        self._client = ClaudeClient()
        self._config = config.load()
        self._headline = self._config.get(CONFIG_HEADLINE, DEFAULT_HEADLINE)
        language = self._config.get(CONFIG_LANGUAGE, i18n.DEFAULT_LANGUAGE)
        self._tr = Translator(language if i18n.is_supported(language) else i18n.DEFAULT_LANGUAGE)
        self._last_usage: Usage | None = None
        # Window keys offered by the headline switcher; refreshed from real data.
        self._window_keys: list[str] = ["5-hour", "7-day"]

        self._set_menu([rumps.MenuItem(self._tr.starting())])
        self._timer = rumps.Timer(self._tick, REFRESH_SECONDS)
        self._timer.start()
        self._tick(None)  # first paint immediately

    # --- menu construction -------------------------------------------------

    def _set_menu(self, detail_rows: list) -> None:
        """Replace the whole menu: detail rows on top, fixed controls below."""
        self.menu.clear()
        self.menu = [
            *detail_rows,
            None,
            self._headline_submenu(),
            self._language_submenu(),
            rumps.MenuItem(self._tr.refresh(), callback=self._on_refresh),
            rumps.MenuItem(self._tr.open_site(), callback=self._on_open_site),
            None,
            rumps.MenuItem(self._tr.quit(), callback=rumps.quit_application),
        ]

    def _headline_submenu(self) -> rumps.MenuItem:
        """Choose which window the menu bar title shows (✓ on the active one)."""
        submenu = rumps.MenuItem(self._tr.headline_menu())
        for key in self._window_keys:
            submenu.add(
                _checkable(self._tr.window_label(key), key == self._headline, self._make_headline_setter(key))
            )
        return submenu

    def _language_submenu(self) -> rumps.MenuItem:
        submenu = rumps.MenuItem(self._tr.language_menu())
        for code, autonym in i18n.LANGUAGES:
            submenu.add(_checkable(autonym, code == self._tr.lang, self._make_language_setter(code)))
        return submenu

    # --- actions -----------------------------------------------------------

    def _make_headline_setter(self, key: str):
        def callback(_):
            if key != self._headline:
                self._headline = key
                self._persist()
                self._repaint()

        return callback

    def _make_language_setter(self, code: str):
        def callback(_):
            if code != self._tr.lang:
                self._tr = Translator(code)
                self._persist()
                self._repaint()

        return callback

    def _on_refresh(self, _) -> None:
        self._tick(None)

    def _on_open_site(self, _) -> None:
        webbrowser.open("https://claude.ai")

    def _persist(self) -> None:
        self._config[CONFIG_HEADLINE] = self._headline
        self._config[CONFIG_LANGUAGE] = self._tr.lang
        config.save(self._config)

    def _repaint(self) -> None:
        """Re-render from cached data (a settings change needs no network call)."""
        if self._last_usage is not None:
            self._render(self._last_usage)
        else:
            self._tick(None)

    # --- refresh cycle -----------------------------------------------------

    def _tick(self, _) -> None:
        try:
            usage = self._client.get_usage()
        except AppError as e:
            self._render_error(e)
        except Exception as e:  # noqa: BLE001 — never let the timer die
            self._render_error(AppError(ErrorKind.UNKNOWN, str(e)))
        else:
            self._render(usage)

    def _render(self, usage: Usage) -> None:
        self._last_usage = usage
        self._window_keys = [w.label for w in usage.windows]

        # Headline the chosen window; fall back to the most-consumed one.
        head = next((w for w in usage.windows if w.label == self._headline), usage.primary)
        self.title = f"{_dot(head.remaining)} {head.remaining}%"

        label_width = max(_display_width(self._tr.window_label(w.label)) for w in usage.windows)
        rows: list = [_info_row(usage.plan), None]
        for w in usage.windows:
            label = _pad_to(self._tr.window_label(w.label), label_width)
            rows.append(_info_row(self._tr.row(label, _bar(w.remaining), w.remaining), _status_color(w.remaining), bold=True))
        rows.append(None)
        for w in usage.windows:
            rows.append(_info_row(self._tr.reset(self._tr.window_label(w.label), w.resets_at), NSColor.secondaryLabelColor()))
        self._set_menu(rows)

    def _render_error(self, error: AppError) -> None:
        self.title = "⚠️"
        self._set_menu([_info_row(f"⚠️ {self._tr.error(error.kind, error.detail)}", NSColor.systemRedColor())])


def main() -> None:
    AIUsageApp().run()


if __name__ == "__main__":
    main()
