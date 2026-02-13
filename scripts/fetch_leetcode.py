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

    # Optional auth via cookies (recommended if you want "from scratch with cookies")
    leetcode_session = os.getenv("LEETCODE_SESSION")
    csrf = os.getenv("LEETCODE_CSRF")

    if leetcode_session and csrf:
        s.cookies.set("LEETCODE_SESSION", leetcode_session, domain=".leetcode.com")
        s.cookies.set("csrftoken", csrf, domain=".leetcode.com")
        s.headers["x-csrftoken"] = csrf

    return s

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

    # Normalize counts
    ac = {row["difficulty"]: row["count"] for row in user["submitStatsGlobal"]["acSubmissionNum"]}
    out = {
        "username": user["username"],
        "ranking": user["profile"]["ranking"],
        "reputation": user["profile"]["reputation"],
        "starRating": user["profile"]["starRating"],
        "solved": {
            "Easy": ac.get("Easy", 0),
            "Medium": ac.get("Medium", 0),
            "Hard": ac.get("Hard", 0),
            "All": ac.get("All", 0),
        },
        # submissionCalendar is a JSON string map: { "timestamp": count, ... }
        "submissionCalendar": user.get("submissionCalendar"),
        "generatedAt": datetime.utcnow().isoformat() + "Z",
    }

    os.makedirs("data", exist_ok=True)
    with open("data/leetcode.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("Wrote data/leetcode.json")

if __name__ == "__main__":
    main()
