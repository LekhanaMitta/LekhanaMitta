import os
import json
import requests
from datetime import datetime

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"

QUERY = """
query userProfile($username: String!) {
  matchedUser(username: $username) {
    username
    profile {
      ranking
      userAvatar
      realName
      reputation
      starRating
    }
    submitStatsGlobal {
      acSubmissionNum {
        difficulty
        count
        submissions
      }
    }
    submissionCalendar
  }
}
"""

def build_session():
    s = requests.Session()
    s.headers.update({
        "Content-Type": "application/json",
        "Referer": "https://leetcode.com",
        "User-Agent": "Mozilla/5.0",
    })

    leetcode_session = os.getenv("LEETCODE_SESSION")
    csrf = os.getenv("LEETCODE_CSRF")

    if leetcode_session and csrf:
        s.cookies.set("LEETCODE_SESSION", leetcode_session, domain=".leetcode.com")
        s.cookies.set("csrftoken", csrf, domain=".leetcode.com")
        s.headers["x-csrftoken"] = csrf

    return s

def pct(ac_count: int, submissions: int):
    """Return acceptance rate as a percentage float (0..100) or None."""
    if submissions is None or submissions <= 0:
        return None
    return (ac_count / submissions) * 100.0

def main():
    username = os.environ["LEETCODE_USERNAME"]

    payload = {
        "query": QUERY,
        "variables": {"username": username},
        "operationName": "userProfile",
    }

    s = build_session()
    r = s.post(LEETCODE_GRAPHQL, data=json.dumps(payload), timeout=30)
    r.raise_for_status()

    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    user = data["data"]["matchedUser"]
    if not user:
        raise RuntimeError("User not found (matchedUser is null). Check username.")

    rows = user["submitStatsGlobal"]["acSubmissionNum"]

    # Build dicts keyed by difficulty: Easy/Medium/Hard/All
    ac_count = {row["difficulty"]: int(row.get("count", 0) or 0) for row in rows}
    submissions = {row["difficulty"]: int(row.get("submissions", 0) or 0) for row in rows}

    # Acceptance rate: solved / submissions
    acc_rate_by_diff = {
        diff: pct(ac_count.get(diff, 0), submissions.get(diff, 0))
        for diff in ["Easy", "Medium", "Hard", "All"]
    }

    out = {
        "username": user["username"],
        "ranking": user["profile"]["ranking"],
        "reputation": user["profile"]["reputation"],
        "starRating": user["profile"]["starRating"],
        "solved": {
            "Easy": ac_count.get("Easy", 0),
            "Medium": ac_count.get("Medium", 0),
            "Hard": ac_count.get("Hard", 0),
            "All": ac_count.get("All", 0),
        },
        "submissions": {
            "Easy": submissions.get("Easy", 0),
            "Medium": submissions.get("Medium", 0),
            "Hard": submissions.get("Hard", 0),
            "All": submissions.get("All", 0),
        },
        # store as numbers (0..100) so renderer can format nicely
        "acceptanceRate": {
            "Easy": acc_rate_by_diff.get("Easy"),
            "Medium": acc_rate_by_diff.get("Medium"),
            "Hard": acc_rate_by_diff.get("Hard"),
            "All": acc_rate_by_diff.get("All"),
        },
        "submissionCalendar": user.get("submissionCalendar"),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }

    os.makedirs("data", exist_ok=True)
    with open("data/leetcode.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("Wrote data/leetcode.json")

if __name__ == "__main__":
    main()
