#!/usr/bin/env python3
"""
Build a daily task dashboard from GitHub Issues and inject it into README.md.

Each issue labeled `task` becomes a row:
  - open issue   -> pending / in progress
  - closed issue -> done
  - issue comments -> the latest one is shown as the "comment"

The dashboard is written between these markers in your README:
  <!-- TASKS:START -->   ...generated content...   <!-- TASKS:END -->
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

REPO        = os.environ["GITHUB_REPOSITORY"]          # "owner/repo"
TOKEN       = os.environ["GITHUB_TOKEN"]
LABEL       = os.environ.get("TASK_LABEL", "task")
README_PATH = os.environ.get("README_PATH", "README.md")
API         = "https://api.github.com"
START, END  = "<!-- TASKS:START -->", "<!-- TASKS:END -->"


def gh_get(url):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "task-dashboard")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def get_issues():
    """All issues (open + closed) carrying the task label, excluding pull requests."""
    issues, page = [], 1
    label = urllib.parse.quote(LABEL)
    while True:
        url = f"{API}/repos/{REPO}/issues?state=all&labels={label}&per_page=100&page={page}"
        batch = gh_get(url)
        if not batch:
            break
        issues += [i for i in batch if "pull_request" not in i]
        if len(batch) < 100:
            break
        page += 1
    return issues


def latest_comment(issue):
    if issue.get("comments", 0) == 0:
        return ""
    comments = gh_get(issue["comments_url"])
    return comments[-1]["body"] if comments else ""


def clean(text, n=90):
    text = " ".join(text.split())            # collapse whitespace / newlines
    text = text.replace("|", "\\|")          # don't break the markdown table
    return text if len(text) <= n else text[: n - 1] + "…"


def fmt_date(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")


def build_section(issues):
    total = len(issues)
    done = sum(1 for i in issues if i["state"] == "closed")
    pending = total - done
    pct = round(done / total * 100) if total else 0

    # Summary badges (shields.io images render fine on profile READMEs)
    badges = (
        f"![Total](https://img.shields.io/badge/total-{total}-informational) "
        f"![Done](https://img.shields.io/badge/done-{done}-success) "
        f"![Pending](https://img.shields.io/badge/pending-{pending}-yellow) "
        f"![Progress](https://img.shields.io/badge/progress-{pct}%25-blue)"
    )

    # open tasks first (by newest), then completed ones
    issues.sort(key=lambda i: (i["state"] != "open", i["updated_at"]), reverse=False)
    issues.sort(key=lambda i: i["state"] == "closed")

    rows = ["| Status | Task | Added | Latest comment |",
            "|:------:|------|:-----:|----------------|"]
    if not issues:
        rows.append("| — | _No tasks yet. Open an issue labeled "
                    f"`{LABEL}` to add one._ | — | — |")
    for i in issues:
        status = "✅" if i["state"] == "closed" else "⏳"
        title = f"[{clean(i['title'], 60)}]({i['html_url']})"
        added = fmt_date(i["created_at"])
        comment = clean(latest_comment(i)) or "—"
        rows.append(f"| {status} | {title} | {added} | {comment} |")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{START}\n"
        f"## 🗂️ Daily Task Dashboard\n\n"
        f"{badges}\n\n"
        + "\n".join(rows) +
        f"\n\n<sub>⏳ pending · ✅ done — add a task by opening an issue labeled "
        f"`{LABEL}`, comment on it to add notes. Last updated {stamp}.</sub>\n"
        f"{END}"
    )


def main():
    issues = get_issues()
    section = build_section(issues)

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    if START in readme and END in readme:
        readme = re.sub(
            re.escape(START) + r".*?" + re.escape(END),
            section, readme, flags=re.DOTALL,
        )
    else:
        readme = readme.rstrip() + "\n\n" + section + "\n"

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"Dashboard updated: {len(issues)} task(s).")


if __name__ == "__main__":
    sys.exit(main())
