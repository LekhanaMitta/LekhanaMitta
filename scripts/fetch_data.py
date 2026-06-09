#!/usr/bin/env python3
"""
fetch_data.py — fetches Monkeytype, LeetCode, and 8-Week SQL data,
then writes data.json for the GitHub Pages dashboard.

Run by the GitHub Action; never needs to run locally.
"""

import json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone, date

# ── helpers ──────────────────────────────────────────────────────────────────
def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def http_post_json(url, body, headers=None):
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        **(headers or {})
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def today_str():
    return date.today().isoformat()

# ── Monkeytype ────────────────────────────────────────────────────────────────
def fetch_monkeytype(ape_key: str) -> dict:
    base = "https://api.monkeytype.com"
    auth = {"Authorization": f"ApeKey {ape_key}"}

    # Recent test results (up to 100)
    try:
        results = http_get(f"{base}/results?limit=100", headers=auth).get("data", [])
    except Exception as e:
        print(f"[MT] results error: {e}", file=sys.stderr)
        results = []

    # Filter to tests from today (UTC)
    today = today_str()
    today_ts_start = int(datetime.strptime(today, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)

    today_results = [r for r in results if r.get("timestamp", 0) >= today_ts_start]
    source = today_results if today_results else results  # fall back to recent if nothing today

    # Group by mode label (e.g. "time 15", "words 50")
    from collections import defaultdict
    groups = defaultdict(list)
    for r in source:
        mode = r.get("mode", "")
        mode2 = r.get("mode2", "")
        label = f"{mode} {mode2}".strip()
        groups[label].append(r)

    modes = []
    for label, items in sorted(groups.items()):
        # Take the MOST RECENT item in each group
        items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        latest = items[0]
        modes.append({
            "name": label,
            "wpm":  round(latest.get("wpm", 0), 1),
            "raw":  round(latest.get("rawWpm", latest.get("raw", 0)), 1),
            "acc":  round(latest.get("acc", 0), 1),
            "con":  round(latest.get("consistency", 0), 1),
        })

    return {
        "username": "theUnbeknownst",
        "lastUpdated": utcnow(),
        "modes": modes,
        "source": "today" if today_results else "recent"
    }

# ── LeetCode ──────────────────────────────────────────────────────────────────
LC_GQL = "https://leetcode.com/graphql"

def fetch_leetcode(username: str) -> dict:
    query = """
    query userStats($username: String!) {
      matchedUser(username: $username) {
        submitStats: submitStatsGlobal {
          acSubmissionNum {
            difficulty
            count
          }
        }
        problemsSolvedBeatsStats {
          difficulty
          percentage
        }
      }
      userContestRanking(username: $username) {
        rating
        globalRanking
      }
    }
    """
    try:
        resp = http_post_json(LC_GQL, {"query": query, "variables": {"username": username}},
                              headers={"Referer": "https://leetcode.com"})
        user = resp.get("data", {}).get("matchedUser", {})
        stats = {s["difficulty"]: s["count"]
                 for s in user.get("submitStats", {}).get("acSubmissionNum", [])}
        total  = stats.get("All", 0)
        easy   = stats.get("Easy", 0)
        medium = stats.get("Medium", 0)
        hard   = stats.get("Hard", 0)

        # acceptance: beats stats don't give a single number; we skip it or default
        beats = {b["difficulty"]: b["percentage"]
                 for b in user.get("problemsSolvedBeatsStats", [])}
        acceptance = round(beats.get("All", 76), 1)

        return {
            "username": username,
            "total": total, "easy": easy, "medium": medium, "hard": hard,
            "acceptance": acceptance,
            "lastUpdated": utcnow()
        }
    except Exception as e:
        print(f"[LC] error: {e}", file=sys.stderr)
        return None

# ── 8-Week SQL Challenge ──────────────────────────────────────────────────────
WEEK_NAMES = [
    "Danny's Diner", "Pizza Runner", "Foodie-Fi", "Data Bank",
    "Data Mart", "Clique Bait", "Balanced Tree", "Fresh Segments"
]

# Possible folder name patterns across repos
WEEK_PATTERNS = [
    "case-study-{n}", "case_study_{n}", "week{n}", "week-{n}",
    "week_{n}", "Case Study #{n}", "Case-Study-{n}",
    "casestudy{n}", "CaseStudy{n}", "{n}",
]

def fetch_sql(repo: str, token: str = None) -> dict:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "dashboard-action"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Get top-level contents
    try:
        contents = http_get(f"https://api.github.com/repos/{repo}/contents", headers=headers)
        folder_names = {item["name"].lower(): item["name"]
                        for item in contents if item["type"] == "dir"}
    except Exception as e:
        print(f"[SQL] contents error: {e}", file=sys.stderr)
        return None

    weeks = []
    for n in range(1, 9):
        folder = None
        for pat in WEEK_PATTERNS:
            candidate = pat.format(n=n).lower()
            if candidate in folder_names:
                folder = folder_names[candidate]
                break

        commits = 0
        if folder:
            try:
                commit_list = http_get(
                    f"https://api.github.com/repos/{repo}/commits?path={folder}&per_page=100",
                    headers=headers
                )
                commits = len(commit_list) if isinstance(commit_list, list) else 0
            except Exception:
                commits = 1  # folder exists, at least started

        done = commits >= 3  # ≥3 commits = "done" heuristic; adjust if you like
        weeks.append({
            "n": n,
            "name": WEEK_NAMES[n - 1],
            "folder": folder,
            "commits": commits,
            "done": done
        })

    return {
        "repo": repo,
        "weeks": weeks,
        "lastUpdated": utcnow()
    }

# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ape_key    = os.environ.get("MONKEYTYPE_APE_KEY", "")
    gh_token   = os.environ.get("GITHUB_TOKEN", "")
    sql_repo   = os.environ.get("SQL_REPO", "LekhanaMitta/8WeekSQLChallenge")
    lc_user    = os.environ.get("LC_USERNAME", "LekhanaRM")
    out_path   = os.environ.get("DATA_JSON_PATH", "data.json")

    print("Fetching Monkeytype…")
    mt = fetch_monkeytype(ape_key) if ape_key else None
    if not mt:
        print("[MT] Skipped (no ApeKey). Add MONKEYTYPE_APE_KEY secret.")

    print("Fetching LeetCode…")
    lc = fetch_leetcode(lc_user)

    print("Fetching 8-Week SQL repo…")
    sql = fetch_sql(sql_repo, gh_token)

    payload = {
        "generatedAt": utcnow(),
        "monkeytype": mt,
        "leetcode": lc,
        "sql": sql,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"✓ Wrote {out_path}")

if __name__ == "__main__":
    sys.exit(main())
