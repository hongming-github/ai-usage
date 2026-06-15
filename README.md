# AI Usage

A tiny macOS menu bar app that shows how much of your AI quota is left, so you
don't have to keep opening the website to check.

Currently supports **Claude Pro / Max** (claude.ai subscription usage). The
design is provider-agnostic so other tools can be added later.

The status bar shows a traffic-light dot plus the remaining percentage of a
chosen window. Click it for a per-window gauge with reset times:

```
Claude Pro
────────────────
5小时 ██████░░░░  剩 55%
7天   █████████░  剩 95%
────────────────
5小时窗口 16:30 重置
7天窗口 周六 16:00 重置
```

## How it works

Claude **Pro/Max subscription** usage has no official public API. This app reads
the same internal endpoint the claude.ai web client uses:

```
GET https://claude.ai/api/organizations/{org}/usage
```

To authenticate it reuses **your own** login: it reads the `sessionKey` cookie
from the **Claude desktop app's** cookie store (`~/Library/Application Support/
Claude/Cookies`) and decrypts it with the key in your macOS Keychain — the same
scheme Chrome uses. The cookie store is opened **read-only**; nothing is sent
anywhere except claude.ai.

The first launch triggers a macOS Keychain prompt ("AI Usage wants to use the
Claude Safe Storage key") — click **Always Allow**.

> ⚠️ **Unofficial & use at your own risk.** This relies on an undocumented
> endpoint and may break whenever Anthropic changes it. Only ever used with your
> own account. Not affiliated with Anthropic.

## Requirements

- macOS on Apple Silicon (M1+) or Intel
- The **Claude desktop app**, installed and logged in
- Python 3.10+

## Setup

```bash
git clone https://github.com/<your-username>/ai-usage.git
cd ai-usage
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run

Foreground (stops when you close the terminal):

```bash
.venv/bin/python run.py
```

Background — stays in the menu bar after the terminal/SSH session closes:

```bash
cd /path/to/ai-usage
nohup .venv/bin/python run.py >/tmp/aiusage.log 2>&1 &
```

Stop / restart it with:

```bash
pkill -f run.py
```

It refreshes every 2 minutes; click **刷新** to force an update.

### Launch at login (no .app needed)

Add the background command to the end of your `~/.zshrc`, guarded so it only
starts one copy (replace `/path/to/ai-usage` with where you cloned it):

```bash
pgrep -f "ai-usage/.*run.py" >/dev/null || \
  (cd /path/to/ai-usage && nohup .venv/bin/python run.py >/tmp/aiusage.log 2>&1 &)
```

The first run shows a macOS Keychain prompt — click **Always Allow**.

## Package as a standalone .app (optional)

```bash
.venv/bin/pip install py2app
.venv/bin/python setup.py py2app
open dist/
```

Drag `AI Usage.app` to `/Applications`, and add it to **System Settings → General
→ Login Items** to launch at startup.

## Languages

The UI ships in 简体中文 / 繁體中文 / English — switch live via **菜单 →
语言 / Language**; the choice is remembered.

## Project layout

```
ai_usage/
  app.py      # view: menu bar UI (owns no text or network logic)
  claude.py   # data: fetch + model the usage from claude.ai
  cookies.py  # auth: decrypt the sessionKey from the Claude desktop app
  i18n.py     # all user-facing strings + locale formatting
  config.py   # persisted preferences (Application Support)
  errors.py   # AppError + ErrorKind (UI translates kinds to text)
```

### Adding a language

Edit `i18n.py` only: append a `(code, autonym)` to `LANGUAGES` and add a matching
entry to `_TEXT`, `_WINDOW_LABELS`, and `_WEEKDAYS`. No other file hard-codes a
human string, so nothing else needs to change.

## Roadmap

- [ ] Package a signed `.app` + login-item helper
- [ ] Support more providers (OpenAI, Cursor, …)
- [x] Configurable which window headlines the bar (菜单 → 标题显示)
- [x] UI language switching (简体中文 / 繁體中文 / English)

## License

MIT
