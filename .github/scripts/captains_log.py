"""Daily update of the profile README.

Writes the header (captain's name, day at sea), the last seen plundering with the parrot
(assets/parrot.svg), the Ship's Ledger stats, the latest recruits (assets/recruits/*.svg)
and the bottles washed ashore into README.md.

Runs from .github/workflows/captains-log.yml. Uses only the standard library.
"""

import base64
import hashlib
import html
import json
import os
import random
import re
import textwrap
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = os.environ.get("GH_USER", "DonatNathan")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
ASSETS = ROOT / "assets"
BOTTLE_TITLE = "Message in a bottle"
HIDE_LABEL = "sunk"  # put this label on a bottle issue to hide it from the README

# --------------------------------------------------------------------------- helpers

def fetch(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "readme-captains-log", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def get_json(url, headers=None):
    return json.loads(fetch(url, headers))


def gh(path):
    headers = {"Accept": "application/vnd.github+json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    return get_json(f"https://api.github.com/{path}", headers)


def parse_date(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def time_ago(when, now):
    seconds = (now - when).total_seconds()
    for unit, size in (("year", 31_536_000), ("month", 2_592_000), ("week", 604_800), ("day", 86_400), ("hour", 3_600)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return "moments ago"


def md_safe(text, limit=160):
    """Make user-written text safe to drop into Markdown: one line, no HTML, no links or images."""
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    text = html.escape(text)
    return re.sub(r"([\\`*_{}\[\]()#+!|~>-])", r"\\\1", text)


# --------------------------------------------------------------------------- pirate translator

PIRATE_WORDS = {
    "fix": "patch up", "fixed": "patched up", "fixes": "patches up", "fixing": "patchin' up",
    "bug": "scurvy bug", "bugs": "scurvy bugs",
    "add": "bring aboard", "added": "brought aboard", "adds": "brings aboard", "adding": "bringin' aboard",
    "remove": "throw overboard", "removed": "threw overboard", "removes": "throws overboard",
    "delete": "make walk the plank", "deleted": "made walk the plank",
    "update": "refit", "updated": "refitted", "updates": "refits",
    "edit": "scribble on", "edited": "scribbled on",
    "refactor": "rebuild the riggin' of", "refactored": "rebuilt the riggin' of",
    "test": "inspection", "tests": "inspections",
    "merge": "lash together", "merged": "lashed together",
    "release": "set sail", "deploy": "set sail", "deployed": "set sail",
    "error": "leak", "errors": "leaks",
    "file": "scroll", "files": "scrolls",
    "readme": "ship's papers", "readme.md": "ship's papers",
    "code": "booty", "feature": "new cannon", "features": "new cannons", "feat": "new cannon",
    "docs": "charts", "doc": "chart", "documentation": "charts",
    "config": "riggin'", "configuration": "riggin'", "settings": "riggin'",
    "init": "maiden voyage", "initial": "maiden", "first": "maiden",
    "commit": "loot", "data": "cargo", "database": "cargo hold",
    "server": "fortress", "user": "landlubber", "users": "landlubbers",
    "my": "me", "you": "ye", "your": "yer", "is": "be", "are": "be", "the": "th'",
    "hello": "ahoy", "hi": "ahoy", "friend": "matey", "friends": "mateys", "yes": "aye",
    "stop": "avast", "look": "spy", "fast": "swift", "money": "doubloons",
    "wip": "still swabbin' the deck", "some": "some o'", "of": "o'", "and": "an'",
    "banner": "flag", "profile": "ship", "build": "shipbuild", "crash": "shipwreck",
    "test:": "inspection:", "issue": "barnacle", "issues": "barnacles",
}
PIRATE_OPENERS = ["Arr!", "Yo ho!", "Shiver me timbers!", "Blimey!", "Avast!", "Ahoy!"]
PIRATE_CLOSERS = [", matey!", ", arr!", "! Yo ho ho!", ", ye scallywag!", "! Hoist the colours!"]


def piratify(message):
    rng = random.Random(hashlib.sha256(message.encode()).hexdigest())

    def swap(match):
        word = match.group(0)
        new = PIRATE_WORDS.get(word.lower())
        if not new:
            return word
        return new[0].upper() + new[1:] if word[0].isupper() else new

    text = re.sub(r"[A-Za-z][A-Za-z.']*[A-Za-z]|[A-Za-z]", swap, message.strip())
    text = text.rstrip(".!?")
    return f"{rng.choice(PIRATE_OPENERS)} {text}{rng.choice(PIRATE_CLOSERS)}"


def last_plunder(now):
    """Most recently pushed repo (other than this profile repo) and the captain's latest commit in it."""
    repos = gh(f"users/{USER}/repos?sort=pushed&per_page=15")
    for repo in repos:
        if repo["fork"] or repo["name"].lower() == USER.lower():
            continue
        try:
            commits = gh(f"repos/{repo['full_name']}/commits?author={USER}&per_page=1")
        except Exception:
            continue
        if commits:
            commit = commits[0]["commit"]
            return {
                "repo": repo["name"],
                "url": repo["html_url"],
                "ago": time_ago(parse_date(commit["author"]["date"]), now),
                "message": commit["message"].splitlines()[0],
            }
    return None


# --------------------------------------------------------------------------- stats

def fetch_stats():
    user = gh(f"users/{USER}")
    repos = gh(f"users/{USER}/repos?per_page=100")
    try:
        commits = gh(f"search/commits?q=author:{USER}")["total_count"]
    except Exception:
        commits = 0
    return {
        "name": user["name"] or user["login"],
        "created": parse_date(user["created_at"]).date(),
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "commits": commits,
    }


# --------------------------------------------------------------------------- header

def header(stats, now):
    days = (now.date() - stats["created"]).days
    return "\n".join([
        f'<h2 align="center">⚓ Captain {html.escape(stats["name"])} · Day {days:,} at sea</h2>',
        "<br />",
    ])


# --------------------------------------------------------------------------- the parrot

PARROT_EMOJI = ASSETS / "emoji" / "parrot.svg"  # Noto Emoji parrot, Apache 2.0 (see assets/emoji/NOTICE.md)


def parrot_image():
    """The emoji parrot, mirrored so it faces the speech bubble."""
    data = base64.b64encode(PARROT_EMOJI.read_bytes()).decode()
    return (f'<image href="data:image/svg+xml;base64,{data}" x="14" y="36" width="160" height="160" '
            f'transform="translate(188 0) scale(-1 1)"/>')


def parrot_svg(sentence):
    lines = textwrap.wrap(sentence, 38) or [""]
    if len(lines) > 4:
        lines = lines[:4]
        lines[-1] = lines[-1][:37].rstrip() + "…"
    line_h, pad = 32, 30
    bx, by, bw = 200, 20, 480
    bh = pad * 2 + line_h * len(lines) - 8
    height = max(236, by + bh + 24)
    text = "".join(
        f'<text x="{bx + bw / 2}" y="{by + pad + 22 + i * line_h}" text-anchor="middle">{html.escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    beak_y = 78
    tail_top, tail_bottom = max(by + 18, beak_y - 14), max(by + 42, beak_y + 12)
    r = 18
    bubble = (f"M{bx + r} {by} H {bx + bw - r} a {r} {r} 0 0 1 {r} {r} V {by + bh - r} a {r} {r} 0 0 1 -{r} {r} "
              f"H {bx + r} a {r} {r} 0 0 1 -{r} -{r} V {tail_bottom} L 176 {beak_y} L {bx} {tail_top} V {by + r} a {r} {r} 0 0 1 {r} -{r} Z")
    sx, sy = bx + bw - 26, by + bh - 24  # skull stamp, bottom-right corner
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="700" height="{height}" viewBox="0 0 700 {height}">
  <defs>
    <radialGradient id="parchment" cx="50%" cy="45%" r="65%">
      <stop offset="0%" stop-color="#f7e9c4"/>
      <stop offset="70%" stop-color="#ecd39d"/>
      <stop offset="100%" stop-color="#d6b273"/>
    </radialGradient>
  </defs>
  {parrot_image()}
  <!-- Parchment bubble with a braided rope border -->
  <path d="{bubble}" fill="url(#parchment)"/>
  <path d="{bubble}" fill="none" stroke="#5a3a1c" stroke-width="7" stroke-linejoin="round"/>
  <path d="{bubble}" fill="none" stroke="#c9995a" stroke-width="4" stroke-linejoin="round" stroke-dasharray="6 4"/>
  <path d="{bubble}" fill="none" stroke="#e8c58c" stroke-width="1.2" stroke-linejoin="round" stroke-dasharray="3 7" stroke-dashoffset="-1"/>
  <g font-family="Georgia, 'Times New Roman', serif" font-style="italic" font-weight="700" font-size="24" fill="#3b2414">{text}</g>
  <g transform="translate({sx} {sy})" fill="#5a3a1c" opacity="0.55">
    <path d="M-10 -10 L10 10 M10 -10 L-10 10" stroke="#5a3a1c" stroke-width="3" stroke-linecap="round"/>
    <circle cx="0" cy="-3" r="7"/>
    <rect x="-4" y="2" width="8" height="5" rx="1.5"/>
    <circle cx="-2.6" cy="-3.5" r="1.8" fill="#f0dcaa"/>
    <circle cx="2.6" cy="-3.5" r="1.8" fill="#f0dcaa"/>
  </g>
</svg>
"""


def captains_log(plunder):
    if not plunder:
        (ASSETS / "parrot.svg").write_text(parrot_svg("Squawk! The captain be restin' today!"), encoding="utf-8")
        return '<p align="center"><img src="./assets/parrot.svg" width="640" alt="The parrot squawks" /></p>'
    (ASSETS / "parrot.svg").write_text(parrot_svg(piratify(plunder["message"])), encoding="utf-8")
    order = html.escape(plunder["message"].replace("`", "'"))
    if len(order) > 120:
        order = order[:119] + "…"
    return "\n".join([
        "<br /><br /><br />",
        "",
        f'<h3 align="center">🗺️ Last seen plundering <a href="{plunder["url"]}">{html.escape(plunder["repo"])}</a></h3>',
        f'<p align="center"><sub>{plunder["ago"]}</sub></p>',
        "",
        f'<p align="center"><a href="{plunder["url"]}"><img src="./assets/parrot.svg" width="640" alt="The parrot repeats the last commit in pirate speak" /></a></p>',
        "",
        f'<p align="center"><sub>🦜 The parrot overheard <code>{order}</code> and won\'t stop repeating it.</sub></p>',
        "",
        "<br /><br /><br />",
    ])


# --------------------------------------------------------------------------- ship's ledger

def ledger(stats):
    """Four stats as a transparent image: big teal numbers, grey labels, thin dividers."""
    cells = [
        (stats["commits"], "Commits plundered"),
        (stats["repos"], "Ships commanded"),
        (stats["stars"], "Stars stolen"),
        (stats["followers"], "Crew members"),
    ]
    col = 190
    parts = []
    for i, (value, label) in enumerate(cells):
        cx = col * i + col / 2
        parts.append(
            f'<text x="{cx}" y="52" text-anchor="middle" class="num">{value:,}</text>'
            f'<text x="{cx}" y="80" text-anchor="middle" class="label">{label}</text>'
        )
        if i:
            parts.append(f'<line x1="{col * i}" y1="18" x2="{col * i}" y2="84" stroke="#8b949e" stroke-opacity="0.35"/>')
    (ASSETS / "stats.svg").write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" width="{col * 4}" height="100" viewBox="0 0 {col * 4} 100">
  <style>
    .num {{ font: 700 38px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #2c9ab7; }}
    .label {{ font: 600 12px -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; fill: #8b949e; letter-spacing: 1.5px; text-transform: uppercase; }}
  </style>
  {''.join(parts)}
</svg>
""", encoding="utf-8")
    return '<p align="center"><img src="./assets/stats.svg" width="680" alt="' + ", ".join(f"{v:,} {l.lower()}" for v, l in cells) + '" /></p>'


# --------------------------------------------------------------------------- latest recruits

RECRUITS = 8
RECRUITS_DIR = ASSETS / "recruits"


def latest_followers(total):
    if not total:
        return []
    last_page = (total - 1) // 100 + 1
    found = []
    for page in range(last_page, 0, -1):
        found = gh(f"users/{USER}/followers?per_page=100&page={page}") + found
        if len(found) >= RECRUITS:
            break
    return list(reversed(found))[:RECRUITS]  # API lists oldest first


def recruit_svg(follower):
    """One follower: round avatar wearing a tricorn hat, name underneath, transparent background."""
    url = follower["avatar_url"]
    raw = fetch(f"{url}&s=128" if "?" in url else f"{url}?s=128")
    mime = "image/jpeg" if raw[:2] == b"\xff\xd8" else "image/png"
    avatar = f"data:{mime};base64," + base64.b64encode(raw).decode()
    login = follower["login"] if len(follower["login"]) <= 11 else follower["login"][:10] + "…"
    cx, cy, r = 60, 76, 36
    top = cy - r
    hat = top + 8  # brim sits on the head
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="120" height="150" viewBox="0 0 120 150">
  <clipPath id="c"><circle cx="{cx}" cy="{cy}" r="{r}"/></clipPath>
  <circle cx="{cx}" cy="{cy}" r="{r + 3}" fill="#137177"/>
  <image href="{avatar}" x="{cx - r}" y="{top}" width="{2 * r}" height="{2 * r}" clip-path="url(#c)"/>
  <path d="M{cx - 44} {hat + 4} Q {cx} {hat - 10} {cx + 44} {hat + 4} Q {cx + 25} {hat - 6} {cx + 17} {hat - 27} Q {cx} {hat - 37} {cx - 17} {hat - 27} Q {cx - 25} {hat - 6} {cx - 44} {hat + 4} Z" fill="#141414" stroke="#d4a017" stroke-width="2"/>
  <circle cx="{cx}" cy="{hat - 15}" r="4.5" fill="#f4ecd8"/>
  <path d="M{cx - 5} {hat - 7} L {cx + 5} {hat - 3} M {cx + 5} {hat - 7} L {cx - 5} {hat - 3}" stroke="#f4ecd8" stroke-width="1.6"/>
  <text x="{cx}" y="{cy + r + 26}" text-anchor="middle" font-family="-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif" font-size="14" font-weight="600" fill="#8b949e">{html.escape(login)}</text>
</svg>
"""


def recruits(followers):
    RECRUITS_DIR.mkdir(parents=True, exist_ok=True)
    for old in RECRUITS_DIR.glob("*.svg"):
        old.unlink()
    if not followers:
        return "*No recruits yet... the crew be waiting for ye!*"
    links = []
    for i, follower in enumerate(followers, 1):
        try:
            (RECRUITS_DIR / f"{i}.svg").write_text(recruit_svg(follower), encoding="utf-8")
        except Exception:
            continue
        links.append(
            f'  <a href="{follower["html_url"]}"><img src="./assets/recruits/{i}.svg" width="90" '
            f'alt="{html.escape(follower["login"])}" /></a>'
        )
    return '<p align="center">\n' + "\n".join(links) + "\n</p>"


# --------------------------------------------------------------------------- bottles

def bottles(now):
    try:
        issues = gh(f"repos/{USER}/{USER}/issues?state=all&per_page=50")
    except Exception:
        return None
    found = []
    for issue in issues:
        if "pull_request" in issue or BOTTLE_TITLE.lower() not in issue["title"].lower():
            continue
        if any(label["name"].lower() == HIDE_LABEL for label in issue["labels"]):
            continue
        body = re.sub(r"^\s*Ahoy Captain!?\s*", "", issue.get("body") or "", flags=re.I)
        if not body.strip():
            continue
        found.append(
            f"> 🍾 *\"{md_safe(body)}\"*  \n"
            f"> — washed ashore from **[{md_safe(issue['user']['login'], 40)}]({issue['user']['html_url']})**, "
            f"{time_ago(parse_date(issue['created_at']), now)} · [read the bottle]({issue['html_url']})"
        )
        if len(found) == 3:
            break
    if not found:
        return "> *No bottles have washed ashore yet... be the first to throw one!*"
    return "\n>\n".join(found).replace("\n>\n> 🍾", "\n\n> 🍾")


# --------------------------------------------------------------------------- main

def replace_block(text, name, content):
    return re.sub(
        rf"(<!-- {name}:START -->\n).*?(<!-- {name}:END -->)",
        lambda m: m.group(1) + content + "\n" + m.group(2),
        text,
        flags=re.S,
    )


def main():
    now = datetime.now(timezone.utc)
    stats = fetch_stats()
    ASSETS.mkdir(exist_ok=True)

    text = README.read_text(encoding="utf-8")
    text = replace_block(text, "HEADER", header(stats, now))
    text = replace_block(text, "CAPTAINS-LOG", captains_log(last_plunder(now)))
    text = replace_block(text, "LEDGER", ledger(stats))
    text = replace_block(text, "RECRUITS", recruits(latest_followers(stats["followers"])))
    washed = bottles(now)
    if washed is not None:
        text = replace_block(text, "BOTTLES", washed)
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
