import json
import os
from datetime import datetime

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="720" height="220" viewBox="0 0 720 220">
  <style>
    .title {{ font: 700 20px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #f3f4f6; }}
    .label {{ font: 500 14px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #cbd5e1; }}
    .value {{ font: 800 22px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #ffffff; }}
    .muted {{ font: 12px system-ui, -apple-system, Segoe UI, Roboto, Arial; fill: #94a3b8; }}

    .card {{ fill: #0b1220; stroke: #1f2937; }}
    .divider {{ stroke: #223044; stroke-width: 1; opacity: 0.7; }}

    .seg {{ cursor: default; transition: filter .15s ease, opacity .15s ease; }}
    .seg:hover {{ filter: brightness(1.25); opacity: 0.95; }}

    .ring-bg {{ stroke: #1f2a3a; stroke-width: 18; fill: none; opacity: 1; }}
    .ring-cutout {{ fill: #0b1220; }}
  </style>

  <!-- Card -->
  <rect x="0" y="0" width="720" height="220" rx="16" class="card"/>

  <!-- Header -->
  <text x="24" y="42" class="title">LeetCode Dashboard — {username}</text>
  <text x="24" y="66" class="muted">Updated: {updated}</text>

  <line x1="24" y1="84" x2="696" y2="84" class="divider"/>

  <!-- Left stats -->
  <text x="24" y="120" class="label">Solved</text>
  <text x="24" y="152" class="value">{all_solved}</text>

  <text x="180" y="120" class="label">Easy</text>
  <text x="180" y="152" class="value">{easy}</text>

  <text x="310" y="120" class="label">Medium</text>
  <text x="310" y="152" class="value">{medium}</text>

  <text x="470" y="120" class="label">Hard</text>
  <text x="470" y="152" class="value">{hard}</text>

  <text x="600" y="120" class="label">Rank</text>
  <text x="600" y="152" class="value">{rank}</text>

  <!-- Donut chart area (right side) -->
  <!-- Center (cx, cy) = (610, 155), radius = 42 -->
  <g transform="translate(0,0)">
    <text x="520" y="120" class="label">Difficulty Mix</text>

    <!-- background ring -->
    <circle cx="{cx}" cy="{cy}" r="{r}" class="ring-bg"/>

    <!-- segments (stroke-dasharray based donut) -->
    <!-- Easy -->
    <circle cx="{cx}" cy="{cy}" r="{r}"
            class="seg"
            stroke="{easy_color}" stroke-width="{stroke}"
            fill="none"
            stroke-linecap="round"
            stroke-dasharray="{easy_dash} {circ}"
            stroke-dashoffset="{easy_offset}">
      <title>Easy: {easy} ({easy_pct:.1f}%) • Submission rate: {easy_sr}</title>
    </circle>

    <!-- Medium -->
    <circle cx="{cx}" cy="{cy}" r="{r}"
            class="seg"
            stroke="{medium_color}" stroke-width="{stroke}"
            fill="none"
            stroke-linecap="round"
            stroke-dasharray="{medium_dash} {circ}"
            stroke-dashoffset="{medium_offset}">
      <title>Medium: {medium} ({medium_pct:.1f}%) • Submission rate: {medium_sr}</title>
    </circle>

    <!-- Hard -->
    <circle cx="{cx}" cy="{cy}" r="{r}"
            class="seg"
            stroke="{hard_color}" stroke-width="{stroke}"
            fill="none"
            stroke-linecap="round"
            stroke-dasharray="{hard_dash} {circ}"
            stroke-dashoffset="{hard_offset}">
      <title>Hard: {hard} ({hard_pct:.1f}%) • Submission rate: {hard_sr}</title>
    </circle>

    <!-- center cutout -->
    <circle cx="{cx}" cy="{cy}" r="{inner_r}" class="ring-cutout"/>

    <!-- center text -->
    <text x="{cx}" y="{cy-2}" text-anchor="middle" class="value" style="font-size:18px;">{all_solved}</text>
    <text x="{cx}" y="{cy+18}" text-anchor="middle" class="muted">Solved</text>

    <!-- overall submission rate -->
    <text x="520" y="206" class="muted">Overall submission rate: {overall_sr}</text>
  </g>
</svg>
"""

def _fmt_rate(v):
    """Accept 0.42, 42, '42%', None -> '42%' / 'N/A'."""
    if v is None:
        return "N/A"
    if isinstance(v, str):
        s = v.strip()
        return s if s.endswith("%") else s
    try:
        x = float(v)
    except Exception:
        return "N/A"
    # if given as 0..1
    if 0 <= x <= 1:
        return f"{x * 100:.0f}%"
    return f"{x:.0f}%"

def main():
    with open("data/leetcode.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    solved = d["solved"]
    easy = int(solved.get("Easy", 0))
    medium = int(solved.get("Medium", 0))
    hard = int(solved.get("Hard", 0))
    total = int(solved.get("All", easy + medium + hard))

    # Guard: avoid division by zero
    denom = max(1, easy + medium + hard)

    easy_pct = (easy / denom) * 100
    medium_pct = (medium / denom) * 100
    hard_pct = (hard / denom) * 100

    # Donut math
    cx, cy = 610, 155
    r = 42
    stroke = 18
    inner_r = r - stroke / 2

    import math
    circ = 2 * math.pi * r

    # Segment lengths
    easy_dash = circ * (easy / denom)
    medium_dash = circ * (medium / denom)
    hard_dash = circ * (hard / denom)

    # Offsets: start at top (12 o'clock)
    # SVG circles start at 3 o'clock; rotate by -90deg using dashoffset = circ * 0.25
    base = circ * 0.25
    # We draw in order: Easy then Medium then Hard; each next segment offset accumulates
    easy_offset = base
    medium_offset = base - easy_dash
    hard_offset = base - easy_dash - medium_dash

    # Submission rate fields (optional in your JSON)
    # Supported JSON patterns:
    # d["submission_rate"] = 0.42 or 42 or "42%"
    # d["submission_rate_by_difficulty"] = {"Easy": "...", "Medium": "...", "Hard": "..."}
    overall_sr = _fmt_rate(d.get("submission_rate"))
    by_diff = d.get("submission_rate_by_difficulty", {}) or {}
    easy_sr = _fmt_rate(by_diff.get("Easy"))
    medium_sr = _fmt_rate(by_diff.get("Medium"))
    hard_sr = _fmt_rate(by_diff.get("Hard"))

    # LeetCode-ish colors (dark mode friendly)
    easy_color = "#00b8a3"    # teal/green
    medium_color = "#ffc01e"  # yellow/orange
    hard_color = "#ff375f"    # red/pink

    os.makedirs("assets", exist_ok=True)
    svg = SVG_TEMPLATE.format(
        username=d["username"],
        all_solved=total,
        easy=easy,
        medium=medium,
        hard=hard,
        rank=d.get("ranking", "—"),
        updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),

        cx=cx, cy=cy, r=r, stroke=stroke, inner_r=inner_r, circ=circ,

        easy_dash=easy_dash, medium_dash=medium_dash, hard_dash=hard_dash,
        easy_offset=easy_offset, medium_offset=medium_offset, hard_offset=hard_offset,

        easy_pct=easy_pct, medium_pct=medium_pct, hard_pct=hard_pct,
        overall_sr=overall_sr, easy_sr=easy_sr, medium_sr=medium_sr, hard_sr=hard_sr,

        easy_color=easy_color, medium_color=medium_color, hard_color=hard_color,
    )

    with open("assets/leetcode.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("Wrote assets/leetcode.svg")

if __name__ == "__main__":
    main()
