import json
import os
import math
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

    .ring-bg {{ stroke: #1f2a3a; stroke-width: {stroke}; fill: none; opacity: 1; }}
    .ring-cutout {{ fill: #0b1220; }}
  </style>

  <rect x="0" y="0" width="720" height="220" rx="16" class="card"/>

  <text x="24" y="42" class="title">LeetCode Dashboard — {username}</text>
  <text x="24" y="66" class="muted">Updated: {updated}</text>

  <line x1="24" y1="84" x2="696" y2="84" class="divider"/>

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

  <text x="520" y="120" class="label">Difficulty Mix</text>

  <circle cx="{cx}" cy="{cy}" r="{r}" class="ring-bg"/>

  <!-- Easy -->
  <circle cx="{cx}" cy="{cy}" r="{r}"
          class="seg"
          stroke="{easy_color}" stroke-width="{stroke}"
          fill="none"
          stroke-linecap="round"
          stroke-dasharray="{easy_dash} {circ}"
          stroke-dashoffset="{easy_offset}">
    <title>Easy: {easy} ({easy_pct:.1f}%) • Acceptance rate: {easy_ar}</title>
  </circle>

  <!-- Medium -->
  <circle cx="{cx}" cy="{cy}" r="{r}"
          class="seg"
          stroke="{medium_color}" stroke-width="{stroke}"
          fill="none"
          stroke-linecap="round"
          stroke-dasharray="{medium_dash} {circ}"
          stroke-dashoffset="{medium_offset}">
    <title>Medium: {medium} ({medium_pct:.1f}%) • Acceptance rate: {medium_ar}</title>
  </circle>

  <!-- Hard -->
  <circle cx="{cx}" cy="{cy}" r="{r}"
          class="seg"
          stroke="{hard_color}" stroke-width="{stroke}"
          fill="none"
          stroke-linecap="round"
          stroke-dasharray="{hard_dash} {circ}"
          stroke-dashoffset="{hard_offset}">
    <title>Hard: {hard} ({hard_pct:.1f}%) • Acceptance rate: {hard_ar}</title>
  </circle>

  <circle cx="{cx}" cy="{cy}" r="{inner_r}" class="ring-cutout"/>

  <text x="{cx}" y="{cy_title}" text-anchor="middle" class="value" style="font-size:18px;">{all_solved}</text>
  <text x="{cx}" y="{cy_sub}" text-anchor="middle" class="muted">Solved</text>

  <text x="520" y="206" class="muted">Overall acceptance rate: {overall_ar}</text>
</svg>
"""

def fmt_pct(v):
    """Format percentage number (0..100) or None -> 'N/A'."""
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.0f}%"
    except Exception:
        return "N/A"

def main():
    with open("data/leetcode.json", "r", encoding="utf-8") as f:
        d = json.load(f)

    solved = d.get("solved", {})
    easy = int(solved.get("Easy", 0) or 0)
    medium = int(solved.get("Medium", 0) or 0)
    hard = int(solved.get("Hard", 0) or 0)
    total = int(solved.get("All", easy + medium + hard) or 0)

    denom = max(1, easy + medium + hard)

    easy_pct = (easy / denom) * 100.0
    medium_pct = (medium / denom) * 100.0
    hard_pct = (hard / denom) * 100.0

    # Donut geometry
    cx, cy = 610, 155
    r = 42
    stroke = 18
    inner_r = r - stroke / 2

    circ = 2 * math.pi * r

    easy_dash = circ * (easy / denom)
    medium_dash = circ * (medium / denom)
    hard_dash = circ * (hard / denom)

    # start at 12 o'clock: offset by 1/4 circumference
    base = circ * 0.25
    easy_offset = base
    medium_offset = base - easy_dash
    hard_offset = base - easy_dash - medium_dash

    # LeetCode-ish colors
    easy_color = "#00b8a3"
    medium_color = "#ffc01e"
    hard_color = "#ff375f"

    # Acceptance rates from fetch
    ar = d.get("acceptanceRate", {}) or {}
    overall_ar = fmt_pct(ar.get("All"))
    easy_ar = fmt_pct(ar.get("Easy"))
    medium_ar = fmt_pct(ar.get("Medium"))
    hard_ar = fmt_pct(ar.get("Hard"))

    os.makedirs("assets", exist_ok=True)

    svg = SVG_TEMPLATE.format(
        username=d.get("username", "—"),
        rank=d.get("ranking", "—"),

        all_solved=total,
        easy=easy,
        medium=medium,
        hard=hard,

        updated=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),

        cx=cx, cy=cy, r=r,
        stroke=stroke,
        inner_r=inner_r,
        circ=circ,

        easy_dash=easy_dash,
        medium_dash=medium_dash,
        hard_dash=hard_dash,

        easy_offset=easy_offset,
        medium_offset=medium_offset,
        hard_offset=hard_offset,

        easy_pct=easy_pct,
        medium_pct=medium_pct,
        hard_pct=hard_pct,

        easy_color=easy_color,
        medium_color=medium_color,
        hard_color=hard_color,

        overall_ar=overall_ar,
        easy_ar=easy_ar,
        medium_ar=medium_ar,
        hard_ar=hard_ar,

        cy_title=cy - 2,
        cy_sub=cy + 18,
    )

    with open("assets/leetcode.svg", "w", encoding="utf-8") as f:
        f.write(svg)

    print("Wrote assets/leetcode.svg")

if __name__ == "__main__":
    main()
