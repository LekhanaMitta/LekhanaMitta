#!/usr/bin/env python3
"""
fetch_data.py  — fetches all dashboard data and writes data.json
Monkeytype : public profile endpoint  (no ApeKey needed for profile)
             ApeKey used for recent results + streak
LeetCode   : GraphQL — solved counts, language stats, skill tags, calendar
SQL        : GitHub API commit counts per folder
"""

import json, os, sys, urllib.request, urllib.error, urllib.parse, traceback
from datetime import datetime, timezone, date
from collections import defaultdict

# ── HTTP helpers ──────────────────────────────────────────────────────────────
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

def safe(fn, label):
    """Run fn(), print errors, return None on failure."""
    try:
        return fn()
    except Exception as e:
        print(f"[{label}] ERROR: {e}", file=sys.stderr)
        traceback.print_exc()
        return None

# ═══════════════════════════════════════════════════════════════════════════════
#  MONKEYTYPE
# ═══════════════════════════════════════════════════════════════════════════════
def fetch_monkeytype(username: str, ape_key: str = "") -> dict:
    base  = "https://api.monkeytype.com"
    auth  = {"Authorization": f"ApeKey {ape_key}"} if ape_key else {}

    # ── 1. Public profile (no ApeKey needed) ──────────────────────────────────
    profile = safe(
        lambda: http_get(f"{base}/users/{username}/profile?isUid=false"),
        "MT-profile"
    )
    pdata = {}
    if profile:
        raw = profile.get("data", profile)
        if isinstance(raw, dict):
            pdata = raw
            print(f"[MT] profile keys: {list(pdata.keys())}", flush=True)

    typing_stats = pdata.get("typingStats", {})
    completed    = typing_stats.get("completedTests", 0)
    time_typing  = typing_stats.get("timeTyping", 0)   # seconds
    streak       = pdata.get("streak", 0)
    max_streak   = pdata.get("maxStreak", 0)
    xp           = pdata.get("xp", 0)

    # ── 2. Personal bests from profile ────────────────────────────────────────
    pb_raw = pdata.get("personalBests", {})
    # Shape: {"time": {"15": [{"wpm":..,"acc":..,"consistency":..}], "60": [...]},
    #         "words": {"50": [...], "100": [...]}}
    personal_bests = {}
    for mode_type, durations in pb_raw.items():
        if not isinstance(durations, dict):
            continue
        for dur, entries in durations.items():
            if not isinstance(entries, list) or not entries:
                continue
            # best entry = highest wpm
            best = max(entries, key=lambda e: e.get("wpm", 0))
            label = f"{mode_type} {dur}"
            personal_bests[label] = {
                "wpm": round(float(best.get("wpm", 0)), 1),
                "raw": round(float(best.get("rawWpm", best.get("wpm", 0))), 1),
                "acc": round(float(best.get("acc", 0)), 1),
                "con": round(float(best.get("consistency", 0)), 1),
            }
    print(f"[MT] personal bests modes: {list(personal_bests.keys())}", flush=True)

    # ── 3. Recent results (ApeKey required) ───────────────────────────────────
    recent_modes = []
    if ape_key:
        results = safe(
            lambda: http_get(f"{base}/results?limit=100", headers=auth),
            "MT-results"
        )
        if results:
            raw_list = results.get("data", [])
            if isinstance(raw_list, list) and raw_list:
                now_utc = datetime.now(timezone.utc)
                day_start_ms = int(datetime(
                    now_utc.year, now_utc.month, now_utc.day,
                    tzinfo=timezone.utc).timestamp() * 1000)
                today_r = [r for r in raw_list
                           if isinstance(r.get("timestamp"), (int,float))
                           and r["timestamp"] >= day_start_ms]
                source  = today_r if today_r else raw_list
                groups  = defaultdict(list)
                for r in source:
                    m  = str(r.get("mode","")).strip()
                    m2 = str(r.get("mode2","")).strip()
                    groups[f"{m} {m2}".strip() if m2 else m].append(r)
                for lbl in sorted(groups):
                    best = max(groups[lbl], key=lambda x: x.get("wpm", 0))
                    recent_modes.append({
                        "name": lbl,
                        "wpm":  round(float(best.get("wpm", 0)), 1),
                        "raw":  round(float(best.get("rawWpm", best.get("wpm", 0))), 1),
                        "acc":  round(float(best.get("acc", 0)), 1),
                        "con":  round(float(best.get("consistency", 0)), 1),
                    })
                print(f"[MT] recent modes: {[m['name'] for m in recent_modes]}", flush=True)

    hours_typed = round(time_typing / 3600, 1)

    return {
        "username":      username,
        "profileUrl":    f"https://monkeytype.com/profile/{username}",
        "streak":        streak,
        "maxStreak":     max_streak,
        "completedTests":completed,
        "hoursTyped":    hours_typed,
        "xp":            xp,
        "personalBests": personal_bests,
        "recentModes":   recent_modes,
        "lastUpdated":   utcnow(),
    }

# ═══════════════════════════════════════════════════════════════════════════════
#  LEETCODE
# ═══════════════════════════════════════════════════════════════════════════════
LC_GQL = "https://leetcode.com/graphql"
LC_HDR = {
    "Content-Type": "application/json",
    "Referer":      "https://leetcode.com",
    "Origin":       "https://leetcode.com",
    "User-Agent":   "Mozilla/5.0 (compatible; dashboard-bot/2.0)",
}

def lc_query(query, variables):
    resp = http_post_json(LC_GQL, {"query": query, "variables": variables}, headers=LC_HDR)
    errs = resp.get("errors")
    if errs:
        print(f"[LC] GraphQL errors: {errs}", file=sys.stderr)
    return (resp.get("data") or {})

def fetch_leetcode(username: str) -> dict:
    # ── query 1: solved counts + beats + ranking ──────────────────────────────
    q1 = """
    query q1($u:String!){
      matchedUser(username:$u){
        profile { ranking reputation }
        submitStatsGlobal {
          acSubmissionNum { difficulty count }
        }
        problemsSolvedBeatsStats { difficulty percentage }
      }
      allQuestionsCount { difficulty count }
    }"""
    d1 = safe(lambda: lc_query(q1, {"u": username}), "LC-q1") or {}
    user       = d1.get("matchedUser") or {}
    all_q      = {x["difficulty"]: x["count"] for x in (d1.get("allQuestionsCount") or [])}
    sub_stats  = user.get("submitStatsGlobal", {})
    counts     = {s["difficulty"]: s["count"] for s in sub_stats.get("acSubmissionNum", [])}
    beats      = {b["difficulty"]: b["percentage"] for b in (user.get("problemsSolvedBeatsStats") or [])}
    profile    = user.get("profile") or {}
    print(f"[LC] counts: {counts}", flush=True)

    total  = counts.get("All",    0)
    easy   = counts.get("Easy",   0)
    medium = counts.get("Medium", 0)
    hard   = counts.get("Hard",   0)
    ranking    = profile.get("ranking", 0)
    reputation = profile.get("reputation", 0)

    # ── query 2: language stats ───────────────────────────────────────────────
    q2 = """
    query q2($u:String!){
      matchedUser(username:$u){
        languageProblemCount { languageName problemsSolved }
      }
    }"""
    d2 = safe(lambda: lc_query(q2, {"u": username}), "LC-q2") or {}
    lang_raw = ((d2.get("matchedUser") or {}).get("languageProblemCount") or [])
    languages = sorted(
        [{"lang": x["languageName"], "solved": x["problemsSolved"]} for x in lang_raw],
        key=lambda x: -x["solved"]
    )[:6]

    # ── query 3: skill tags ───────────────────────────────────────────────────
    q3 = """
    query q3($u:String!){
      matchedUser(username:$u){
        tagProblemCounts {
          advanced     { tagName problemsSolved }
          intermediate { tagName problemsSolved }
          fundamental  { tagName problemsSolved }
        }
      }
    }"""
    d3 = safe(lambda: lc_query(q3, {"u": username}), "LC-q3") or {}
    tpc = ((d3.get("matchedUser") or {}).get("tagProblemCounts") or {})
    skills = []
    for tier in ["advanced", "intermediate", "fundamental"]:
        for t in (tpc.get(tier) or []):
            skills.append({"tag": t["tagName"], "solved": t["problemsSolved"], "tier": tier})
    skills.sort(key=lambda x: -x["solved"])
    top_skills = skills[:8]

    # ── query 4: submission calendar (activity heatmap) ───────────────────────
    q4 = """
    query q4($u:String!,$year:Int){
      matchedUser(username:$u){
        userCalendar(year:$year){
          activeYears
          streak
          totalActiveDays
          submissionCalendar
        }
      }
    }"""
    cur_year = datetime.now(timezone.utc).year
    d4 = safe(lambda: lc_query(q4, {"u": username, "year": cur_year}), "LC-q4") or {}
    cal_raw  = ((d4.get("matchedUser") or {}).get("userCalendar") or {})
    lc_streak       = cal_raw.get("streak", 0)
    total_active    = cal_raw.get("totalActiveDays", 0)
    sub_calendar_str= cal_raw.get("submissionCalendar", "{}")
    # parse calendar: {"timestamp": count, ...} — keep last 30 days
    try:
        cal_dict = json.loads(sub_calendar_str)
        now_ts   = int(datetime.now(timezone.utc).timestamp())
        day_secs = 86400
        cal_30   = {k: v for k, v in cal_dict.items()
                    if now_ts - int(k) <= 30 * day_secs}
    except Exception:
        cal_30 = {}

    return {
        "username":     username,
        "profileUrl":   f"https://leetcode.com/{username}",
        "total":        total,
        "easy":         easy,
        "medium":       medium,
        "hard":         hard,
        "totalEasy":    all_q.get("Easy",   0),
        "totalMedium":  all_q.get("Medium", 0),
        "totalHard":    all_q.get("Hard",   0),
        "beatsEasy":    round(float(beats.get("Easy")   or 0), 1),
        "beatsMedium":  round(float(beats.get("Medium") or 0), 1),
        "beatsHard":    round(float(beats.get("Hard")   or 0), 1),
        "ranking":      ranking,
        "reputation":   reputation,
        "streak":       lc_streak,
        "totalActiveDays": total_active,
        "languages":    languages,
        "topSkills":    top_skills,
        "calendar30":   cal_30,
        "lastUpdated":  utcnow(),
    }

# ═══════════════════════════════════════════════════════════════════════════════
#  8-WEEK SQL
# ═══════════════════════════════════════════════════════════════════════════════
WEEK_NAMES = [
    "Danny's Diner","Pizza Runner","Foodie-Fi","Data Bank",
    "Data Mart","Clique Bait","Balanced Tree","Fresh Segments",
]
WEEK_PATTERNS = [
    "case-study-{n}","case_study_{n}","casestudy{n}",
    "week{n}","week-{n}","week_{n}",
    "case study #{n}","case-study-#{n}","{n}",
]

def fetch_sql(repo: str, token: str = "") -> dict:
    hdrs = {"Accept": "application/vnd.github+json", "User-Agent": "dashboard-action"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    contents = safe(
        lambda: http_get(f"https://api.github.com/repos/{repo}/contents", headers=hdrs),
        "SQL-contents"
    )
    if not contents:
        return None
    folder_map = {item["name"].lower(): item["name"]
                  for item in contents if item["type"] == "dir"}
    print(f"[SQL] folders: {list(folder_map.keys())}", flush=True)

    weeks = []
    for n in range(1, 9):
        folder = next(
            (folder_map[pat.format(n=n).lower()]
             for pat in WEEK_PATTERNS
             if pat.format(n=n).lower() in folder_map),
            None
        )
        commits = 0
        if folder:
            cl = safe(
                lambda f=folder: http_get(
                    f"https://api.github.com/repos/{repo}/commits"
                    f"?path={urllib.parse.quote(f)}&per_page=100",
                    headers=hdrs),
                f"SQL-commits-{n}"
            )
            commits = len(cl) if isinstance(cl, list) else 1
        weeks.append({"n": n, "name": WEEK_NAMES[n-1],
                      "folder": folder, "commits": commits, "done": commits >= 3})
    return {"repo": repo, "weeks": weeks, "lastUpdated": utcnow()}

# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    ape_key  = os.environ.get("MONKEYTYPE_APE_KEY", "").strip()
    gh_token = os.environ.get("GITHUB_TOKEN", "")
    sql_repo = os.environ.get("SQL_REPO",      "LekhanaMitta/8WeekSQLChallenge")
    lc_user  = os.environ.get("LC_USERNAME",   "LekhanaRM")
    mt_user  = os.environ.get("MT_USERNAME",   "theUnbeknownst")
    out_path = os.environ.get("DATA_JSON_PATH", "data.json")

    print("── Monkeytype ──────────────────────", flush=True)
    mt = fetch_monkeytype(mt_user, ape_key)

    print("── LeetCode ────────────────────────", flush=True)
    lc = fetch_leetcode(lc_user)

    print("── 8-Week SQL ──────────────────────", flush=True)
    sql = fetch_sql(sql_repo, gh_token)

    payload = {"generatedAt": utcnow(),
               "monkeytype": mt, "leetcode": lc, "sql": sql}

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\n✓ Wrote {out_path}", flush=True)
    if mt: print(f"  MT:  {len(mt.get('personalBests',{}))} PB modes, streak={mt.get('streak')}")
    if lc: print(f"  LC:  {lc.get('total')} solved, rank={lc.get('ranking')}")
    if sql:print(f"  SQL: {sum(1 for w in sql['weeks'] if w['done'])}/8 done")

if __name__ == "__main__":
    sys.exit(main())
