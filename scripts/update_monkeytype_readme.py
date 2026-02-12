#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import urlopen

START = "<!-- MONKEYTYPE:START -->"
END = "<!-- MONKEYTYPE:END -->"

LANGUAGE = "english"  # you can change to english_1k / english_5k / etc if you want
API_URL = "https://api.monkeytype.com/public/speedHistogram"


def fetch_speed_histogram(language: str) -> dict:
    qs = urlencode({"language": language})
    url = f"{API_URL}?{qs}"
    with urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_histogram(payload: dict):
    # payload usually: { "message": "...", "data": [...] }  (data = buckets)
    data = payload.get("data")
    if not data:
        return None, None, None

    # try to find bucket format robustly
    # buckets are typically like: [{"wpm":10,"count":...}, ...] or {"bucket":10,...}
    def bucket_wpm(item):
        return item.get("wpm") if "wpm" in item else item.get("bucket")

    def bucket_count(item):
        return item.get("count") if "count" in item else item.get("amount") or item.get("users")

    cleaned = []
    for item in data:
        w = bucket_wpm(item)
        c = bucket_count(item)
        if w is None or c is None:
            continue
        cleaned.append((int(w), int(c)))

    if not cleaned:
        return None, None, None

    # Most common bucket
    top_wpm, top_count = max(cleaned, key=lambda x: x[1])

    # Simple average estimate (weighted by bucket midpoints)
    total = sum(c for _, c in cleaned)
    avg = sum(w * c for w, c in cleaned) / total if total else None

    return top_wpm, top_count, avg


def render_block(language: str, top_wpm, top_count, avg):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    avg_str = f"{avg:.1f}" if avg is not None else "—"

    return f"""*Last updated:* **{now}**

**Monkeytype (public) – Speed Histogram**
- **Language set:** `{language}`
- **Most common PB bucket:** **{top_wpm} WPM** (users: {top_count})
- **Estimated average bucket:** **{avg_str} WPM**

> Note: this uses Monkeytype’s public “speedHistogram” endpoint (distribution of users’ PBs by WPM bucket).
"""


def replace_block(readme_text: str, new_block: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme_text):
        raise RuntimeError("Could not find MONKEYTYPE markers in README.md")
    return pattern.sub(f"{START}\n{new_block}\n{END}", readme_text)


def main():
    payload = fetch_speed_histogram(LANGUAGE)
    top_wpm, top_count, avg = parse_histogram(payload)

    if top_wpm is None:
        new_block = render_block(LANGUAGE, "—", "—", None)
    else:
        new_block = render_block(LANGUAGE, top_wpm, top_count, avg)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    updated = replace_block(readme, new_block)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README updated.")


if __name__ == "__main__":
    main()
