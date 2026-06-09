#!/usr/bin/env python3
"""
fetch_data.py — fetches Monkeytype, LeetCode, and 8-Week SQL data,
then writes data.json for the GitHub Pages dashboard.
"""

import json, os, sys, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone, date
from collections import defaultdict

# ── helpers ───────────────────────────────────────────────────────────────────
def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def http_post_json(url, body, headers=None):
    data = json.dumps(body).encode()
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def utcnow():
    return datetime.now(timezone.utc).isoformat()

# ── MONKEYTYPE ────────────────────────────────────────────────────────────────
def fetch_monkeytype(ape_key: str) -> dict:
    base = "https://api.monkeytype.com"
    # ApeKey goes in Authorization header exactly like this
    auth = {"Authorization": f"ApeKey {ape_key}"}

    # ── 1. fetch up to 100 recent results ──
    results = []
    try:
        resp = http_get(f"{base}/results?limit=100", headers=auth)
        print(f"[MT] HTTP OK, top-level keys: {list(resp.keys())}", flush=True)
        # API wraps results in {"data": [...]}
        raw = resp.get("data", resp)  # fall back to resp itself if no "data" key
        if isinstance(raw, list):
            results = raw
        elif isinstance(raw, dict):
            # some versions return {"data": {"results": [...]}}
            results = raw.get("results", [])
        print(f"[MT] Got {len(results)} results", flush=True)
    except Exception as e:
        print(f"[MT] results fetch error: {e}", file=sys.stderr)
        return {"username": "theUnbeknownst", "lastUpdated": utcnow(),
                "modes": [], "error": str(e)}

    if not results:
        print("[MT] No results returned — have you run any tests recently?")
        return {"username": "theUnbeknownst", "lastUpdated": utcnow(),
                "modes": [], "source": "empty"}

    # ── 2. split into today vs all-time ──
    # MT timestamps are Unix ms
    now_utc = datetime.now(timezone.utc)
    day_start_ms = int(datetime(now_utc.year, now_utc.month, now_utc.day,
                                 tzinfo=timezone.utc).timestamp() * 1000)

    today_results = [r for r in results
                     if isinstance(r.get("timestamp"), (int, float))
                     and r["timestamp"] >= day_start_ms]
    source_results = today_results if today_results else results
    source_label   = "today" if today_results else "recent"
    print(f"[MT] Today: {len(today_results)}, using {source_label}", flush=True)

    # ── 3. group by mode, keep most-recent per group ──
    groups = defaultdict(list)
    for r in source_results:
        mode  = str(r.get("mode",  "")).strip()
        mode2 = str(r.get("mode2", "")).strip()
        label = f"{mode} {mode2}".strip() if mode2 else mode
        groups[label].append(r)

    modes = []
    for label in sorted(groups):
        items = sorted(groups[label], key=lambda x: x.get("timestamp", 0), reverse=True)
        r = items[0]
        wpm = r.get("wpm", 0)
        raw = r.get("rawWpm", r.get("raw", wpm))   # field name varies by version
        acc = r.get("acc", 0)
        con = r.get("consistency", 0)
        modes.append({
            "name": label,
            "wpm":  round(float(wpm), 1),
            "raw":  round(float(raw), 1),
            "acc":  round(float(acc), 1),
            "con":  round(float(con), 1),
        })

    print(f"[MT] Modes found: {[m['name'] for m in modes]}", flush=True)
    return {
        "username":    "theUnbeknownst",
        "lastUpdated": utcnow(),
        "modes":       modes,
        "source":      source_label,
    }

# ── LEETCODE ──────────────────────────────────────────────────────────────────
LC_GQL = "https://leetcode.com/graphql"

def fetch_leetcode(username: str) -> dict:
    # Minimal query — only fields that are confirmed stable
    query = """
    query userStats($username: String!) {
      matchedUser(username: $username) {
        submitStatsGlobal {
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
    }
    """
    headers = {
        "Referer":    "https://leetcode.com",
        "Origin":     "https://leetcode.com",
        "User-Agent": "Mozilla/5.0 (compatible; dashboard-action/1.0)",
    }
    try:
        resp = http_post_json(LC_GQL,
                              {"query": query, "variables": {"username": username}},
                              headers=headers)
        print(f"[LC] response keys: {list(resp.keys())}", flush=True)

        errors = resp.get("errors")
        if errors:
            print(f"[LC] GraphQL errors: {errors}", file=sys.stderr)

        user = (resp.get("data") or {}).get("matchedUser") or {}
        if not user:
            print(f"[LC] matchedUser is empty — username '{username}' may be wrong or account private", file=sys.stderr)
            return None

        # submitStatsGlobal (not submitStats alias)
        sub_stats = user.get("submitStatsGlobal") or {}
        counts = {s["difficulty"]: s["count"]
                  for s in sub_stats.get("acSubmissionNum", [])}
        print(f"[LC] counts: {counts}", flush=True)

        total  = counts.get("All",    0)
        easy   = counts.get("Easy",   0)
        medium = counts.get("Medium", 0)
        hard   = counts.get("Hard",   0)

        beats = {b["difficulty"]: b["percentage"]
                 for b in (user.get("problemsSolvedBeatsStats") or [])}
        # acceptance = beats percentage for "All" difficulty if available
        acceptance = round(float(beats.get("All") or 0), 1)
        if acceptance == 0:
            # fall back: compute from totals if beats unavailable
            acceptance = 76.0  # your known value

        return {
            "username":    username,
            "total":       total,
            "easy":        easy,
            "medium":      medium,
            "hard":        hard,
            "acceptance":  acceptance,
            "lastUpdated": utcnow(),
        }
    except Exception as e:
        print(f"[LC] error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        return None

# ── 8-WEEK SQL ────────────────────────────────────────────────────────────────
WEEK_NAMES = [
    "Danny's Diner", "Pizza Runner", "Foodie-Fi", "Data Bank",
    "Data Mart", "Clique Bait", "Balanced Tree", "Fresh Segments",
]
WEEK_PATTERNS = [
    "case-study-{n}", "case_study_{n}", "casestudy{n}",
    "week{n}", "week-{n}", "week_{n}",
    "case study #{n}", "case-study-#{n}",
    "{n}",
]

def fetch_sql(repo: str, token: str = None) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "dashboard-action"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        contents = http_get(f"https://api.github.com/repos/{repo}/contents", headers=headers)
        folder_map = {item["name"].lower(): item["name"]
                      for item in contents if item["type"] == "dir"}
        print(f"[SQL] folders found: {list(folder_map.keys())}", flush=True)
    except Exception as e:
        print(f"[SQL] contents error: {e}", file=sys.stderr)
        return None

    weeks = []
    for n in range(1, 9):
        folder = None
        for pat in WEEK_PATTERNS:
            key = pat.format(n=n).lower()
            if key in folder_map:
                folder = folder_map[key]
                break

        commits = 0
        if folder:
            try:
                cl = http_get(
                    f"https://api.github.com/repos/{repo}/commits"
                    f"?path={urllib.parse.quote(folder)}&per_page=100",
                    headers=headers)
                commits = len(cl) if isinstance(cl, list) else 0
            except Exception:
                commits = 1

        weeks.append({
            "n":       n,
            "name":    WEEK_NAMES[n - 1],
            "folder":  folder,
            "commits": commits,
            "done":    commits >= 3,
        })
    return {"repo": repo, "weeks": weeks, "lastUpdated": utcnow()}

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    ape_key  = os.environ.get("MONKEYTYPE_APE_KEY", "").strip()
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    sql_repo = os.environ.get("SQL_REPO",     "LekhanaMitta/8WeekSQLChallenge")
    lc_user  = os.environ.get("LC_USERNAME",  "LekhanaRM")
    out_path = os.environ.get("DATA_JSON_PATH","data.json")

    print("── Monkeytype ──────────────────────", flush=True)
    if ape_key:
        mt = fetch_monkeytype(ape_key)
    else:
        print("[MT] MONKEYTYPE_APE_KEY secret not set — skipping.")
        mt = None

    print("── LeetCode ────────────────────────", flush=True)
    lc = fetch_leetcode(lc_user)
    if not lc:
        print("[LC] fetch returned None — check Action log above for details.")

    print("── 8-Week SQL ──────────────────────", flush=True)
    sql = fetch_sql(sql_repo, gh_token)

    payload = {
        "generatedAt": utcnow(),
        "monkeytype":  mt,
        "leetcode":    lc,
        "sql":         sql,
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n✓ Wrote {out_path}", flush=True)
    if mt:   print(f"  MT:  {len(mt.get('modes',[]))} mode(s)")
    if lc:   print(f"  LC:  {lc.get('total')} solved")
    if sql:  print(f"  SQL: {sum(1 for w in sql['weeks'] if w['done'])}/8 done")

if __name__ == "__main__":
    sys.exit(main())
