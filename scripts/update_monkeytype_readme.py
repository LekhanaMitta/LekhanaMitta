#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

API_URL = "https://api.monkeytype.com/users/personalBests"

START = "<!-- MONKEYTYPE:START -->"
END = "<!-- MONKEYTYPE:END -->"

def http_get_json(url: str, ape_key: str) -> dict:
    req = Request(url, headers={"Authorization": f"ApeKey {ape_key}"})
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def pick_best(pb_list):
    if not pb_list:
        return None
    return max(pb_list, key=lambda x: (x.get("wpm", 0), x.get("acc", 0)))

def fmt_date(ts_ms):
    if not ts_ms:
        return "—"
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")

def pct(x):
    if x is None:
        return "—"
    return f"{float(x):.1f}%"

def num(x):
    if x is None:
        return "—"
    return f"{float(x):.1f}"

def seconds_to_hm(seconds):
    if not seconds:
        return "0h 0m"
    m = int(seconds) // 60
    h, m = divmod(m, 60)
    return f"{h}h {m}m"

def build_table(title: str, block: dict, keys):
    lines = [
        f"**{title}**",
        "",
        "| Mode | WPM | Acc | Raw | Consistency | Date |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for k in keys:
        best = pick_best(block.get(k, []))
        if not best:
            lines.append(f"| {k} | — | — | — | — | — |")
            continue
        lines.append(
            f"| {k} | {num(best.get('wpm'))} | {pct(best.get('acc'))} | {num(best.get('raw'))} | {pct(best.get('consistency'))} | {fmt_date(best.get('timestamp'))} |"
        )
    return "\n".join(lines)

def render_dashboard(data: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    streak = data.get("streak") or {}
    streak_len = streak.get("length", 0)
    streak_max = streak.get("maxLength", 0)

    completed = data.get("completedTests", 0)
    started = data.get("startedTests", 0)
    time_typing = seconds_to_hm(data.get("timeTyping"))

    pbs = data.get("personalBests") or {}
    time_pbs = pbs.get("time") or {}
    words_pbs = pbs.get("words") or {}

    time_keys = ["15", "30", "60", "120"]
    words_keys = ["10", "25", "50", "100"]

    out = []
    out.append(f"*Last updated:* **{now}**")
    out.append("")
    out.append(f"- **Streak:** {streak_len} days (max {streak_max})")
    out.append(f"- **Tests:** {completed} completed / {started} started")
    out.append(f"- **Time typing:** {time_typing}")
    out.append("")
    out.append(build_table("⏱️ Time Personal Bests (seconds)", time_pbs, time_keys))
    out.append("")
    out.append(build_table("🧾 Words Personal Bests (words)", words_pbs, words_keys))
    return "\n".join(out).strip() + "\n"

def replace_block(readme_text: str, new_block: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    replacement = f"{START}\n{new_block}{END}"
    if not pattern.search(readme_text):
        raise RuntimeError("Could not find MONKEYTYPE markers in README.md")
    return pattern.sub(replacement, readme_text)

def main():
    ape_key = os.environ.get("MONKEYTYPE_APE_KEY")
    if not ape_key:
        print("Missing MONKEYTYPE_APE_KEY env var", file=sys.stderr)
        sys.exit(2)

    payload = http_get_json(API_URL, ape_key)
    data = payload.get("data") or {}
    new_block = render_dashboard(data)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    updated = replace_block(readme, new_block)

    if updated == readme:
        print("No changes to README.md")
        return

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README.md updated")

if __name__ == "__main__":
    main()
