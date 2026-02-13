import json
import os
from datetime import datetime

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="180">
  <style>
    .title {{ font: 700 20px system-ui, -apple-system, Segoe UI, Roboto, Arial; }}
    .label {{ font: 500 14px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #444; }}
    .value {{ font: 700 22px system-ui, -apple-system, Segoe UI, Roboto, Arial; }}
    .muted {{ font: 12px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #666; }}
  </style>

  <rect x="0" y="0" width="720" height="180" rx="16" fill="#ffffff" stroke="#e5e7eb"/>

  <text x="24" y="40" class="title">LeetCode Dashboard — {username}</text>

  <text x="24" y="78" class="label">Solved</text>
  <text x="24" y="110" class="value">{all_solved}</text>

  <text x="180" y="78" class="label">Easy</text>
  <text x="180" y="110" class="value">{easy}</text>

  <text x="310" y="78" class="label">Medium</text>
  <text x="310" y="110" class="value">{medium}</text>

  <text x="470" y="78" class="label">Hard</text>
  <text x="470" y="110" class="value">{hard}</text>

  <text x="600" y="78" class="label">Rank</text>
  <text x="600" y="110" class="value">{rank}</text>

  <text x="24" y="150" class="muted">Updated: {updated}</text>
</svg>
"""

def main():
    with open("data/leetcode.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    os.makedirs("assets", exist_ok=True)
    svg = SVG_TEMPLATE.format(
        username=d["username"],
        all_solved=d["solved"]["All"],
        easy=d["solved"]["Easy"],
        medium=d["solved"]["Medium"],
        hard=d["solved"]["Hard"],
        rank=d["ranking"],
        updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )

    with open("assets/leetcode.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("Wrote assets/leetcode.svg")

if __name__ == "__main__":
    main()
