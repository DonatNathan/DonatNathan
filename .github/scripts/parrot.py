"""The talking parrot, built from the Noto Emoji 🦜 (Apache 2.0, see assets/emoji/NOTICE.md).

The emoji's shapes are split into parts so each can move: the wing flaps,
the beak chatters, the eye blinks and the body bobs.
"""

import re
from pathlib import Path

EMOJI = Path(__file__).resolve().parents[2] / "assets" / "emoji" / "parrot.svg"

# Noto paths are identified by their fill colour
ROLES = {
    "#FEBA02": "feet",
    "#FF600D": "jaw",
    "#FBD3B3": "eye",
    "#312F2A": "eye",
    "#B7D019": "wing",
}


def _parts(prefix):
    src = EMOJI.read_text(encoding="utf-8")
    gradient = re.search(r"<linearGradient.*?</linearGradient>", src, re.S).group(0)
    gradient = gradient.replace("SVGID_1_", f"{prefix}-plumage")
    parts = []
    for style, d in re.findall(r'<path style="([^"]*)" d="([^"]*)"', src, re.S):
        fill = re.search(r"fill:([^;]+);", style).group(1)
        if fill.startswith("url("):
            fill = f"url(#{prefix}-plumage)"
        parts.append((ROLES.get(fill.upper(), "body"), fill, " ".join(d.split())))
    return " ".join(gradient.split()), parts


def parrot(prefix, x, y, size, *, extra_class=""):
    """Markup for one parrot facing right, in a size x size box at (x, y), animated by parrot_css(prefix)."""
    gradient, parts = _parts(prefix)
    feet = "".join(f'<path fill="{f}" d="{d}"/>' for role, f, d in parts if role == "feet")
    eye = "".join(f'<path fill="{f}" d="{d}"/>' for role, f, d in parts if role == "eye")
    body, eye_done = [], False
    for role, fill, d in parts:
        if role == "feet":
            continue
        if role == "eye":
            if not eye_done:
                body.append(f'<g class="{prefix}-eye">{eye}</g>')
                eye_done = True
        elif role in ("wing", "jaw"):
            body.append(f'<path class="{prefix}-{role}" fill="{fill}" d="{d}"/>')
        else:
            body.append(f'<path fill="{fill}" d="{d}"/>')
    return (
        f'<g class="{extra_class}">'
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 128 128" overflow="visible">'
        f"<defs>{gradient}</defs>"
        f'<g transform="translate(128 0) scale(-1 1)">'  # the emoji faces left: mirror it
        f"{feet}"
        f'<g class="{prefix}-body">{"".join(body)}</g>'
        f"</g></svg></g>"
    )


def parrot_css(prefix):
    """CSS animating the parts of parrot(prefix, ...): flap, blink, chatter and bob."""
    return "\n    ".join([
        f".{prefix}-wing {{ transform-box: fill-box; transform-origin: 40% 4%; "
        f"animation: {prefix}-flap 0.9s ease-in-out infinite alternate; }}",
        f"@keyframes {prefix}-flap {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(-14deg); }} }}",
        f".{prefix}-eye {{ transform-box: fill-box; transform-origin: 50% 50%; animation: {prefix}-blink 4.2s infinite; }}",
        f"@keyframes {prefix}-blink {{ 0%, 93%, 100% {{ transform: scaleY(1); }} 96% {{ transform: scaleY(0.1); }} }}",
        f".{prefix}-jaw {{ transform-box: fill-box; transform-origin: 95% 8%; "
        f"animation: {prefix}-talk 2.4s ease-in-out infinite; }}",
        f"@keyframes {prefix}-talk {{ 0%, 40%, 100% {{ transform: rotate(0deg); }} "
        f"48%, 64%, 80% {{ transform: rotate(-22deg); }} 56%, 72%, 88% {{ transform: rotate(0deg); }} }}",
        f".{prefix}-body {{ transform-box: fill-box; transform-origin: 45% 96%; "
        f"animation: {prefix}-bob 2.4s ease-in-out infinite; }}",
        f"@keyframes {prefix}-bob {{ 0%, 40%, 100% {{ transform: rotate(0deg); }} "
        f"52% {{ transform: rotate(-5deg) translateY(-2px); }} 76% {{ transform: rotate(3deg); }} }}",
    ])
