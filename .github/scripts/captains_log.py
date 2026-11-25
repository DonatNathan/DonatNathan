"""Update the Captain's Log section of README.md and regenerate assets/bounty.svg.

Runs daily from .github/workflows/captains-log.yml. Uses only the standard library;
if fontTools is installed, the embedded fonts are subset to keep the poster small.
"""

import base64
import io
import json
import os
import random
import re
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path

USER = os.environ.get("GH_USER", "DonatNathan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
BOUNTY = ROOT / "assets" / "bounty.svg"
FONTS = ROOT / "assets" / "fonts"

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


def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-captains-log", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read(), resp.headers.get_content_type()


def get_json(url, headers=None):
    return json.loads(fetch(url, headers)[0])


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
        "name": user["name"] or user["login"],
        "avatar_url": user["avatar_url"],
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


def font_data_uri(filename, text):
    """Embed a font as a data URI, subset to the characters used when fontTools is available."""
    raw = (FONTS / filename).read_bytes()
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont

        font = TTFont(io.BytesIO(raw))
        subsetter = subset.Subsetter(subset.Options())
        subsetter.populate(text=text)
        subsetter.subset(font)
        out = io.BytesIO()
        font.save(out)
        raw = out.getvalue()
    except ImportError:
        pass
    return "data:font/ttf;base64," + base64.b64encode(raw).decode()


def avatar_data_uri(url):
    data, ctype = fetch(f"{url}&s=900" if "?" in url else f"{url}?s=900")
    return f"data:{ctype};base64," + base64.b64encode(data).decode()


def bounty_svg(stats):
    bounty = (stats["commits"] or 0) * 10 + stats["stars"] * 500 + stats["followers"] * 250 + stats["repos"] * 100
    commits = f"{stats['commits']:,}" if stats["commits"] is not None else "???"
    name = stats["name"].upper()
    amount = f"{bounty:,}"
    tagline = "DEAD OR ALIVE"
    crimes = [
        (commits, "COMMITS"),
        (f"{stats['repos']:,}", "SHIPS"),
        (f"{stats['stars']:,}", "STARS"),
        (f"{stats['followers']:,}", "CREW"),
    ]
    heading = "KNOWN CRIMES"
    decree = "By order of the Admiralty of the Seven Seas"

    rye = font_data_uri("Rye-Regular.ttf", "WANTED" + name + amount + "DOUBLOONS")
    fell = font_data_uri("IMFellEnglish-Regular.ttf", tagline + decree + "REWARD")
    typewriter = font_data_uri("SpecialElite-Regular.ttf", heading + "".join(v + l for v, l in crimes) + "—")
    columns = "\n".join(
        f'    <text x="{97.5 + i * 75}" y="612" class="type" font-size="21" text-anchor="middle">{escape(value)}</text>\n'
        f'    <text x="{97.5 + i * 75}" y="631" class="type" font-size="12" text-anchor="middle" letter-spacing="2">{label}</text>'
        for i, (value, label) in enumerate(crimes)
    )
    dividers = "\n".join(
        f'    <line x1="{135 + i * 75}" y1="594" x2="{135 + i * 75}" y2="636" stroke="#2a170b" stroke-width="1"/>' for i in range(3)
    )
    avatar = avatar_data_uri(stats["avatar_url"])

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="420" height="700" viewBox="0 0 420 700">
  <style>
    @font-face {{ font-family: 'Rye'; src: url({rye}) format('truetype'); }}
    @font-face {{ font-family: 'Fell'; src: url({fell}) format('truetype'); }}
    @font-face {{ font-family: 'Typewriter'; src: url({typewriter}) format('truetype'); }}
    .type {{ font-family: 'Typewriter', 'Courier New', monospace; fill: #1f1108; }}
    .rye {{ font-family: 'Rye', Georgia, serif; fill: #2a170b; }}
    .fell {{ font-family: 'Fell', Georgia, serif; fill: #2a170b; }}
  </style>
  <defs>
    <radialGradient id="paperFill" cx="50%" cy="46%" r="68%">
      <stop offset="0%" stop-color="#f1dfb0"/>
      <stop offset="55%" stop-color="#e2c38a"/>
      <stop offset="85%" stop-color="#c49556"/>
      <stop offset="100%" stop-color="#7d4f22"/>
    </radialGradient>

    <!-- Torn edges, coffee/water stains and fibre grain -->
    <filter id="paper" x="-6%" y="-6%" width="112%" height="112%">
      <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="5" seed="4" result="edgeNoise"/>
      <feDisplacementMap in="SourceGraphic" in2="edgeNoise" scale="20" xChannelSelector="R" yChannelSelector="G" result="torn"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.011" numOctaves="3" seed="21" result="blots"/>
      <feColorMatrix in="blots" type="matrix" values="0 0 0 0 0.36  0 0 0 0 0.2  0 0 0 0 0.07  2.6 0 0 0 -1.25" result="stains"/>
      <feComposite in="stains" in2="torn" operator="in" result="stainsOnPaper"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3" seed="9" result="fine"/>
      <feColorMatrix in="fine" type="matrix" values="0 0 0 0 0.25  0 0 0 0 0.14  0 0 0 0 0.05  1.6 0 0 0 -0.62" result="grain"/>
      <feComposite in="grain" in2="torn" operator="in" result="grainOnPaper"/>
      <feMerge>
        <feMergeNode in="torn"/>
        <feMergeNode in="stainsOnPaper"/>
        <feMergeNode in="grainOnPaper"/>
      </feMerge>
    </filter>

    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="6"/>
      <feOffset dx="3" dy="6"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.45"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>

    <!-- Worn letterpress ink: wobbly edges and patchy coverage -->
    <filter id="ink" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.55" numOctaves="2" seed="2" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.2" xChannelSelector="R" yChannelSelector="G" result="wobble"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -2.6 0 0 0 2.25" result="wear"/>
      <feComposite in="wobble" in2="wear" operator="in"/>
    </filter>

    <filter id="inkLight" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.6" numOctaves="2" seed="6" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="1.2" xChannelSelector="R" yChannelSelector="G"/>
    </filter>

    <!-- Old photograph: sepia, crushed contrast, grain -->
    <filter id="sepia" x="0" y="0" width="100%" height="100%">
      <feColorMatrix type="matrix" values="0.39 0.77 0.19 0 0  0.35 0.69 0.17 0 0  0.27 0.53 0.13 0 0  0 0 0 1 0" result="tone"/>
      <feComponentTransfer in="tone" result="contrast">
        <feFuncR type="linear" slope="1.25" intercept="-0.12"/>
        <feFuncG type="linear" slope="1.25" intercept="-0.14"/>
        <feFuncB type="linear" slope="1.2" intercept="-0.14"/>
      </feComponentTransfer>
      <feTurbulence type="fractalNoise" baseFrequency="0.95" numOctaves="2" seed="13" result="pg"/>
      <feColorMatrix in="pg" type="matrix" values="0 0 0 0 0.18  0 0 0 0 0.1  0 0 0 0 0.03  0.9 0 0 0 -0.48" result="pgrain"/>
      <feComposite in="pgrain" in2="SourceGraphic" operator="in" result="pgrainIn"/>
      <feMerge><feMergeNode in="contrast"/><feMergeNode in="pgrainIn"/></feMerge>
    </filter>

    <radialGradient id="vignette" cx="50%" cy="50%" r="62%">
      <stop offset="60%" stop-color="#3a2210" stop-opacity="0"/>
      <stop offset="100%" stop-color="#3a2210" stop-opacity="0.6"/>
    </radialGradient>

    <radialGradient id="nailHead" cx="38%" cy="35%" r="65%">
      <stop offset="0%" stop-color="#d9d4cc"/>
      <stop offset="45%" stop-color="#7c7468"/>
      <stop offset="100%" stop-color="#2c2620"/>
    </radialGradient>

    <clipPath id="photoClip"><rect x="100" y="186" width="220" height="220"/></clipPath>
  </defs>

  <!-- Paper -->
  <g filter="url(#shadow)">
    <rect x="18" y="16" width="384" height="668" fill="url(#paperFill)" filter="url(#paper)"/>
  </g>

  <!-- Printed content -->
  <g filter="url(#ink)">
    <rect x="38" y="36" width="344" height="628" fill="none" stroke="#2a170b" stroke-width="3"/>
    <rect x="45" y="43" width="330" height="614" fill="none" stroke="#2a170b" stroke-width="1"/>

    <text x="210" y="128" class="rye" font-size="84" text-anchor="middle" textLength="300" lengthAdjust="spacingAndGlyphs">WANTED</text>
    <line x1="70" y1="146" x2="350" y2="146" stroke="#2a170b" stroke-width="1.5"/>
    <text x="210" y="164" class="fell" font-size="17" text-anchor="middle" letter-spacing="7">{tagline}</text>

    <rect x="94" y="180" width="232" height="232" fill="none" stroke="#2a170b" stroke-width="4"/>
  </g>

  <!-- Photo -->
  <g clip-path="url(#photoClip)">
    <image x="100" y="186" width="220" height="220" xlink:href="{avatar}" href="{avatar}" preserveAspectRatio="xMidYMid slice" filter="url(#sepia)"/>
    <rect x="100" y="186" width="220" height="220" fill="url(#vignette)"/>
  </g>

  <g filter="url(#ink)">
    <text x="210" y="458" class="rye" font-size="36" text-anchor="middle" textLength="{min(300, 26 * len(name))}" lengthAdjust="spacingAndGlyphs">{escape(name)}</text>
    <text x="210" y="484" class="fell" font-size="14" text-anchor="middle" letter-spacing="4">REWARD</text>
    <text x="210" y="530" class="rye" font-size="44" text-anchor="middle">{amount}</text>
    <text x="210" y="552" class="rye" font-size="15" text-anchor="middle" letter-spacing="5">DOUBLOONS</text>
    <line x1="70" y1="570" x2="350" y2="570" stroke="#2a170b" stroke-width="1.5"/>
  </g>
  <!-- Stats: lighter ink effect so they stay readable -->
  <g filter="url(#inkLight)">
    <text x="210" y="585" class="type" font-size="12" text-anchor="middle" letter-spacing="3">— {heading} —</text>
{columns}
{dividers}
  </g>
  <text x="210" y="651" class="fell" font-size="11" text-anchor="middle" opacity="0.75">{escape(decree)}</text>

  <!-- Nail -->
  <ellipse cx="212" cy="32" rx="9" ry="4" fill="#2a170b" opacity="0.35"/>
  <circle cx="210" cy="28" r="7" fill="url(#nailHead)"/>
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
