#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import HTTPError

START = "<!-- MONKEYTYPE:START -->"
END = "<!-- MONKEYTYPE:END -->"

BASE = "https://api.monkeytype.com"
APEKEY = os.environ.get("MONKEYTYPE_APE_KEY", "").strip()


def api_get(path):
    if not APEKEY:
        print("Missing MONKEYTYPE_APE_KEY", file=sys.stderr)
        sys.exit(1)

    req = Request(
        f"{BASE}{path}",
        headers={
            "Authorization": f"Bearer {APEKEY}",
            "Accept": "application/json",
        },
    )

    try:
        with urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} → {body}") from e


def seconds_to_hm(seconds):
    m = int(seconds) // 60
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def fmt_date(ts):
    if not ts:
        return "—"
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def main():
    stats = api_get("/users/stats")
    streak = api_get("/users/streak")
    last = api_get("/results/last")
    pbs_time = api_get("/users/personalBests?mode=time")
    pbs_words = api_get("/users/personalBests?mode=words")

    s = stats.get("data", {})
    st = streak.get("data", {})
    lr = last.get("data", {})

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    block = f"""
*Last updated:* **{now}**

### 🔥 Streak
- Current: {st.get('length', 0)} days
- Max: {st.get('maxLength', 0)} days

### 📊 Overall Stats
- Tests Completed: {s.get('completedTests', 0)}
- Tests Started: {s.get('startedTests', 0)}
- Time Typing: {seconds_to_hm(s.get('timeTyping', 0))}

### ⏱ Last Test
- {lr.get('wpm', '—')} WPM
- {lr.get('acc', '—')}% accuracy
- Mode: {lr.get('mode', '')} {lr.get('mode2', '')}
- Date: {fmt_date(lr.get('timestamp'))}

> Auto-updated via Monkeytype API
""".strip()

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme):
        raise RuntimeError("MONKEYTYPE markers not found in README")

    updated = pattern.sub(f"{START}\n{block}\n{END}", readme)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README updated successfully.")


if __name__ == "__main__":
    main()
