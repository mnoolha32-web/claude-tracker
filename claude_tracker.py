"""
Claude Update Tracker
Monitors official Anthropic sources and sends Telegram notifications on new releases.
 
Sources:
  1. PyPI RSS          — anthropic SDK releases (most reliable)
  2. GitHub            — claude-code app releases
  3. GitHub            — anthropic-sdk-python releases
"""
 
import os
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
 
 
# ── Config ────────────────────────────────────────────────────────────────────
 
BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID    = os.environ["TELEGRAM_CHAT_ID"]
STATE_FILE = Path("claude_state.json")
 
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}
 
SOURCES = {
    "pypi":       "https://pypi.org/rss/project/anthropic/releases.xml",
    "claude_app": "https://github.com/anthropics/claude-code/releases",
    "sdk":        "https://github.com/anthropics/anthropic-sdk-python/releases",
}
 
 
# ── Fetching helpers ──────────────────────────────────────────────────────────
 
def fetch(url: str, timeout: int = 15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [fetch] failed for {url}: {e}")
        return None
 
 
def parse_iso_date(raw: str) -> str:
    try:
        return datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        ).strftime("%Y-%m-%d")
    except Exception:
        return raw[:10] if raw else "unknown"
 
 
def parse_rfc_date(raw: str) -> str:
    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:
        return raw[:16] if raw else "unknown"
 
 
def get_release_bullets(release_url: str, max_bullets: int = 3) -> str:
    """Fetch a GitHub release page and return top bullet points as a string."""
    r = fetch(release_url, timeout=10)
    if not r:
        return ""
    soup  = BeautifulSoup(r.text, "html.parser")
    body  = soup.select_one(".markdown-body")
    if not body:
        return ""
    items   = [li.get_text(" ", strip=True) for li in body.find_all("li")]
    bullets = [f"  ↳ {item[:90]}" for item in items[:max_bullets] if item]
    return "\n".join(bullets)
 
 
def get_latest_github_release(url: str):
    """Return (tag, date, release_url) for the latest release, or None on failure."""
    r = fetch(url)
    if not r:
        return None
    soup    = BeautifulSoup(r.text, "html.parser")
    tag_el  = soup.select_one("a[href*='/releases/tag/']")
    time_el = soup.find("relative-time")
    if not tag_el:
        return None
    tag         = tag_el.get_text(strip=True)
    release_url = "https://github.com" + tag_el["href"]
    date        = parse_iso_date(time_el["datetime"] if time_el else "")
    return tag, date, release_url
 
 
# ── Source checkers ───────────────────────────────────────────────────────────
 
def check_pypi() -> dict | None:
    r = fetch(SOURCES["pypi"])
    if not r:
        return None
    soup    = BeautifulSoup(r.content, "xml")
    item    = soup.find("item")
    if not item:
        return None
    version = item.find("title").get_text(strip=True)
    date    = parse_rfc_date(item.find("pubDate").get_text(strip=True))
    url     = item.find("link").get_text(strip=True)
    return {
        "source":    "pypi",
        "label":     "Anthropic SDK — PyPI",
        "version":   version,
        "date":      date,
        "summary":   f"نسخة {version} من مكتبة Anthropic Python الرسمية",
        "url":       url,
        "unique_id": version,
    }
 
 
def check_claude_app() -> dict | None:
    result = get_latest_github_release(SOURCES["claude_app"])
    if not result:
        return None
    tag, date, url = result
    bullets = get_release_bullets(url)
    return {
        "source":    "claude_app",
        "label":     "Claude Code",
        "version":   tag,
        "date":      date,
        "summary":   bullets or f"إصدار جديد {tag}",
        "url":       url,
        "unique_id": tag,
    }
 
 
def check_sdk_github() -> dict | None:
    result = get_latest_github_release(SOURCES["sdk"])
    if not result:
        return None
    tag, date, url = result
    bullets = get_release_bullets(url)
    return {
        "source":    "sdk",
        "label":     "Anthropic Python SDK — GitHub",
        "version":   tag,
        "date":      date,
        "summary":   bullets or f"إصدار {tag} من anthropic-sdk-python",
        "url":       url,
        "unique_id": tag,
    }
 
 
# ── State management ──────────────────────────────────────────────────────────
 
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}
 
 
def save_state(state: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
 
 
def is_new(source: str, current_id: str, state: dict) -> bool:
    return state.get(source, {}).get("unique_id") != current_id
 
 
def mark_seen(source: str, unique_id: str, state: dict) -> None:
    state[source] = {
        "unique_id":    unique_id,
        "last_checked": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }
 
 
# ── Telegram ──────────────────────────────────────────────────────────────────
 
def format_message(u: dict) -> str:
    label   = u["label"]
    version = u["version"]
    date    = u["date"]
    url     = u["url"]
    summary = u.get("summary", "")
 
    parts = [
        "🔔 <b>تحديث جديد في Claude</b>",
        "",
        f"<b>المصدر:</b> {label}",
        f"<b>الإصدار:</b> <code>{version}</code>",
        f"<b>التاريخ:</b> {date}",
    ]
    if summary:
        parts += ["", "<b>الملخص:</b>", summary]
    parts += ["", f"🔗 <a href='{url}'>فتح الرابط</a>"]
    return "\n".join(parts)
 
 
def send_telegram(text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":                  CHAT_ID,
                "text":                     text,
                "parse_mode":               "HTML",
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"  [Telegram] send failed: {e}")
        return False
 
 
# ── Main ──────────────────────────────────────────────────────────────────────
 
def main() -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting checks...")
 
    state  = load_state()
    checks = [check_pypi, check_claude_app, check_sdk_github]
    sent   = 0
 
    for check_fn in checks:
        result = check_fn()
 
        if result is None:
            print(f"  [{check_fn.__name__}] skipped (fetch failed)")
            continue
 
        source = result["source"]
        uid    = result["unique_id"]
        saved  = state.get(source, {}).get("unique_id", "none")
        print(f"  [{source}] latest={uid} | saved={saved}")
 
        if is_new(source, uid, state):
            print(f"  [{source}] ✨ new — sending to Telegram...")
            if send_telegram(format_message(result)):
                print(f"  [{source}] ✓ sent")
                sent += 1
            else:
                print(f"  [{source}] ✗ failed")
 
        mark_seen(source, uid, state)
 
    save_state(state)
    print(f"\nDone — {sent} notification(s) sent.")
 
 
if __name__ == "__main__":
    main()

