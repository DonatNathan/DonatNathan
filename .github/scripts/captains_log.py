"""Update the Captain's Log section of README.md and regenerate assets/bounty.svg.

Runs daily from .github/workflows/captains-log.yml. Uses only the standard library.
"""

import json
import os
import random
import re
import urllib.request
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

USER = os.environ.get("GH_USER", "DonatNathan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
BOUNTY = ROOT / "assets" / "bounty.svg"

QUOTES = [
    "Not all treasure is silver and gold, mate.",
    "The sea fears no man, and no man should fear a segfault.",
    "Take what you can, give nothing back... except pull requests.",
    "A smooth sea never made a skilled sailor.",
    "Dead men tell no tales, and dead code tells no bugs.",
    "Ye can't cross the sea merely by staring at the water.",
    "Me compiler be angry today. Batten down the hatches!",
    "There be no shame in `git push --force`... said no sailor ever.",
    "Every ship needs a good anchor, and every repo needs a good README.",
    "Why is the rum always gone? Same reason the coffee is.",
    "Keep calm and hoist the main sail.",
    "The problem be not the problem. The problem be yer attitude about the problem.",
]

PORTS = [
    ("Saint-Malo", 48.65, -2.03),
    ("Tortuga", 20.06, -72.78),
    ("Nassau", 25.05, -77.35),
    ("Port Royal", 17.94, -76.84),
    ("Cape Town", -33.92, 18.42),
    ("Lisbon", 38.72, -9.14),
    ("Havana", 23.11, -82.37),
    ("Madagascar", -18.15, 49.40),
    ("Reykjavik", 64.15, -21.94),
    ("Valparaíso", -33.05, -71.62),
]

WEATHER_CODES = {
    0: "clear skies ☀️",
    1: "mostly clear 🌤️",
    2: "a few clouds ⛅",
    3: "overcast ☁️",
    45: "fog 🌫️",
    48: "freezing fog 🌫️",
    51: "light drizzle 🌦️",
    53: "drizzle 🌦️",
    55: "heavy drizzle 🌧️",
    61: "light rain 🌧️",
    63: "rain 🌧️",
    65: "heavy rain 🌧️",
    71: "light snow 🌨️",
    73: "snow 🌨️",
    75: "heavy snow ❄️",
    80: "rain showers 🌦️",
    81: "rain showers 🌧️",
    82: "violent squalls ⛈️",
    95: "a thunderstorm ⛈️",
    96: "a thunderstorm with hail ⛈️",
    99: "a thunderstorm with hail ⛈️",
}


def get_json(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-captains-log", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def gh(path):
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return get_json(f"https://api.github.com/{path}", headers)


def weather_report(rng):
    name, lat, lon = rng.choice(PORTS)
    try:
        data = get_json(
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,weather_code"
        )["current"]
        sky = WEATHER_CODES.get(data["weather_code"], "strange skies 🌀")
        return (
            f"Spyglass pointed at **{name}**: {sky}, "
            f"{round(data['temperature_2m'])}°C, winds at {round(data['wind_speed_10m'])} km/h."
        )
    except Exception:
        return f"Spyglass pointed at **{name}**, but the fog be too thick to see anything today. 🌫️"


def fetch_stats():
    user = gh(f"users/{USER}")
    repos = gh(f"users/{USER}/repos?per_page=100")
    stars = sum(r["stargazers_count"] for r in repos)
    try:
        commits = gh(f"search/commits?q=author:{USER}")["total_count"]
    except Exception:
        commits = None
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00")).date()
    return {
        "created": created,
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": stars,
        "commits": commits,
    }


def captains_log(stats, today, rng):
    days = (today - stats["created"]).days
    return "\n".join(
        [
            f"> 📜 **Captain's Log, day {days:,} at sea** ({today:%d %B %Y})",
            ">",
            f"> 🌊 {weather_report(rng)}",
            ">",
            f"> 🦜 *\"{rng.choice(QUOTES)}\"*",
        ]
    )


def bounty_svg(stats):
    bounty = (stats["commits"] or 0) * 10 + stats["stars"] * 500 + stats["followers"] * 250 + stats["repos"] * 100
    lines = [
        ("Commits plundered", stats["commits"] if stats["commits"] is not None else "???"),
        ("Ships (repos) commanded", stats["repos"]),
        ("Stars stolen", stats["stars"]),
        ("Crew (followers)", stats["followers"]),
    ]
    rows = "\n".join(
        f'  <text x="40" y="{300 + i * 34}" class="row">{escape(label)}</text>'
        f'<text x="320" y="{300 + i * 34}" class="row" text-anchor="end">{escape(str(value))}</text>'
        for i, (label, value) in enumerate(lines)
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="360" height="480" viewBox="0 0 360 480">
  <style>
    .title {{ font: bold 64px Georgia, 'Times New Roman', serif; fill: #3b2414; letter-spacing: 6px; }}
    .sub {{ font: italic 18px Georgia, serif; fill: #5a3a22; }}
    .name {{ font: bold 30px Georgia, serif; fill: #3b2414; }}
    .row {{ font: 16px Georgia, serif; fill: #3b2414; }}
    .bounty {{ font: bold 30px Georgia, serif; fill: #7a1f12; }}
  </style>
  <defs>
    <radialGradient id="paper" cx="50%" cy="45%" r="70%">
      <stop offset="0%" stop-color="#f6e7c1"/>
      <stop offset="75%" stop-color="#e3c48d"/>
      <stop offset="100%" stop-color="#b8894d"/>
    </radialGradient>
  </defs>
  <rect x="4" y="4" width="352" height="472" rx="6" fill="url(#paper)" stroke="#6b4423" stroke-width="3"/>
  <rect x="16" y="16" width="328" height="448" fill="none" stroke="#6b4423" stroke-width="1.5" stroke-dasharray="6 4"/>
  <text x="180" y="86" class="title" text-anchor="middle">WANTED</text>
  <text x="180" y="114" class="sub" text-anchor="middle">dead or alive, preferably online</text>
  <g transform="translate(180 170)" fill="#3b2414">
    <circle cx="0" cy="-8" r="30"/>
    <rect x="-16" y="12" width="32" height="18" rx="4"/>
    <circle cx="-11" cy="-10" r="8" fill="#f2deb0"/>
    <circle cx="11" cy="-10" r="8" fill="#f2deb0"/>
    <path d="M-3 4 L0 -2 L3 4 Z" fill="#f2deb0"/>
    <path d="M-48 36 L48 -20 M-48 -20 L48 36" stroke="#3b2414" stroke-width="9" stroke-linecap="round"/>
  </g>
  <text x="180" y="262" class="name" text-anchor="middle">Captain {escape(USER)}</text>
{rows}
  <line x1="40" y1="428" x2="320" y2="428" stroke="#6b4423" stroke-width="1"/>
  <text x="180" y="458" class="bounty" text-anchor="middle">฿ {bounty:,} doubloons</text>
</svg>
"""


def main():
    today = datetime.now(timezone.utc).date()
    rng = random.Random(today.toordinal())  # same log all day, new one every day
    stats = fetch_stats()

    text = README.read_text(encoding="utf-8")
    text = re.sub(
        r"(<!-- CAPTAINS-LOG:START -->\n).*?(\n<!-- CAPTAINS-LOG:END -->)",
        lambda m: m.group(1) + captains_log(stats, today, rng) + m.group(2),
        text,
        flags=re.S,
    )
    README.write_text(text, encoding="utf-8")

    BOUNTY.parent.mkdir(exist_ok=True)
    BOUNTY.write_text(bounty_svg(stats), encoding="utf-8")


if __name__ == "__main__":
    main()
