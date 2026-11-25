"""Daily update of the profile README.

Writes the Captain's Log (day at sea, last seen plundering, the parrot's pirate translation),
the Ship's Ledger (pirate rank and stats), the latest recruits (assets/recruits/*.svg)
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

RANKS = [
    (0, "Cabin Boy"),
    (2_000, "Powder Monkey"),
    (5_000, "Deckhand"),
    (10_000, "Boatswain"),
    (20_000, "Quartermaster"),
    (35_000, "First Mate"),
    (60_000, "Captain"),
    (100_000, "Commodore"),
    (200_000, "Dread Pirate Legend"),
]


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


# --------------------------------------------------------------------------- stats & rank

def fetch_stats():
    user = gh(f"users/{USER}")
    repos = gh(f"users/{USER}/repos?per_page=100")
    try:
        commits = gh(f"search/commits?q=author:{USER}")["total_count"]
    except Exception:
        commits = 0
    stats = {
        "created": parse_date(user["created_at"]).date(),
        "repos": user["public_repos"],
        "followers": user["followers"],
        "stars": sum(r["stargazers_count"] for r in repos),
        "commits": commits,
    }
    stats["bounty"] = (stats["commits"] * 10 + stats["stars"] * 500
                       + stats["followers"] * 250 + stats["repos"] * 100)
    return stats


def rank_for(bounty):
    index = max(i for i, (floor, _) in enumerate(RANKS) if bounty >= floor)
    floor, title = RANKS[index]
    if index + 1 < len(RANKS):
        nxt_floor, nxt_title = RANKS[index + 1]
        progress = (bounty - floor) / (nxt_floor - floor)
    else:
        nxt_floor, nxt_title, progress = None, None, 1.0
    return {"index": index, "title": title, "next": nxt_title, "next_floor": nxt_floor, "progress": progress}


# --------------------------------------------------------------------------- captain's log

def captains_log(stats, plunder, now):
    days = (now.date() - stats["created"]).days
    lines = [f"### Day {days:,} at sea", f"<sub>{now:%d %B %Y}</sub>", ""]
    if plunder:
        order = plunder["message"].replace("`", "'")
        if len(order) > 120:
            order = order[:119] + "…"
        lines += [
            f"🗺️ **Last seen plundering** [{md_safe(plunder['repo'], 60)}]({plunder['url']}), *{plunder['ago']}*",
            "",
            f"🦜 **The parrot overheard** `{order}` and won't stop repeating:",
            "",
            f"> ***{md_safe(piratify(plunder['message']), 200)}***",
        ]
    else:
        lines += ["🗺️ *No plundering spotted lately... the captain must be resting.*"]
    return "\n".join(lines)


# --------------------------------------------------------------------------- ship's ledger

def ledger(stats):
    rank = rank_for(stats["bounty"])
    slots = 20
    filled = round(rank["progress"] * slots)
    bar = "█" * filled + "░" * (slots - filled)
    if rank["next"]:
        progress = f"`{bar}` {round(rank['progress'] * 100)}% of the way to **{rank['next']}**"
    else:
        progress = f"`{bar}` the most feared pirate on the seven seas"
    return "\n".join([
        f"**🏴‍☠️ Rank:** {rank['title']}  ",
        progress,
        "",
        f"**💰 Bounty:** {stats['bounty']:,} doubloons on me head",
        "",
        "| ⚔️ Commits plundered | 🚢 Ships commanded | ⭐ Stars stolen | 🦜 Crew members |",
        "| :-: | :-: | :-: | :-: |",
        f"| **{stats['commits']:,}** | **{stats['repos']:,}** | **{stats['stars']:,}** | **{stats['followers']:,}** |",
    ])


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

    text = README.read_text(encoding="utf-8")
    text = replace_block(text, "CAPTAINS-LOG", captains_log(stats, last_plunder(now), now))
    text = replace_block(text, "LEDGER", ledger(stats))
    text = replace_block(text, "RECRUITS", recruits(latest_followers(stats["followers"])))
    washed = bottles(now)
    if washed is not None:
        text = replace_block(text, "BOTTLES", washed)
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
