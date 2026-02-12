#!/usr/bin/env python3
import json
import re
import sys
from datetime import datetime, timezone
from urllib.request import urlopen

USERNAME = "theUnbeknownst"   # <-- put your monkeytype username here
API_URL = f"https://api.monkeytype.com/users/{USERNAME}"

START = "<!-- MONKEYTYPE:START -->"
END = "<!-- MONKEYTYPE:END -->"


def fetch_data():
    with urlopen(API_URL) as r:
        return json.loads(r.read().decode("utf-8"))


def render(data):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    completed = data.get("completedTests", 0)
    started = data.get("startedTests", 0)
    time_typing = round(data.get("timeTyping", 0) / 3600, 2)

    return f"""
*Last updated:* **{now}**

- **Tests Completed:** {completed}
- **Tests Started:** {started}
- **Hours Typing:** {time_typing}
- **Profile:** https://monkeytype.com/profile/{USERNAME}
"""


def replace_block(readme, content):
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(readme):
        raise RuntimeError("Markers not found in README")
    return pattern.sub(f"{START}\n{content}\n{END}", readme)


def main():
    data = fetch_data()
    block = render(data)

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    updated = replace_block(readme, block)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(updated)

    print("README updated successfully.")


if __name__ == "__main__":
    main()
