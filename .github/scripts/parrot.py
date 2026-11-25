"""The animated parrot, built from the Noto Emoji 🦜 (Apache 2.0, see assets/emoji/NOTICE.md).

The emoji's shapes are split into parts (body, wing, lower beak, eye, feet) so each can move:
the wing flaps, the beak chatters, the eye blinks and the body bobs. Used by the parrot
speech bubble, the stats and the sea serpent chase.
"""

import re
from pathlib import Path

EMOJI = Path(__file__).resolve().parents[2] / "assets" / "emoji" / "parrot.svg"

# Noto paths are identified by their fill colour
ROLES = {
    "#FEBA02": "feet",
    "#FFD51D": "beak",
    "#FF2B23": "head",
    "#FF600D": "jaw",
    "#A02A1B": "beak",
    "#EC80AF": "head",
    "#FBD3B3": "eye",
    "#312F2A": "eye",
    "#01AB46": "tail",
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
            fill, role = f"url(#{prefix}-plumage)", "body"
        else:
            role = ROLES.get(fill.upper(), "body")
        parts.append((role, fill, " ".join(d.split())))
    return " ".join(gradient.split()), parts


def parrot(prefix, x, y, size, *, face_right=True, feet=True, extra_class=""):
    """Markup for one parrot in a size x size box at (x, y), animated by parrot_css(prefix)."""
    gradient, parts = _parts(prefix)

    def path(fill, d):
        return f'<path fill="{fill}" d="{d}"/>'

    feet_markup = "".join(path(f, d) for role, f, d in parts if role == "feet") if feet else ""
    eye = "".join(path(f, d) for role, f, d in parts if role == "eye")
    body = []
    eye_done = False
    for role, fill, d in parts:
        if role == "feet":
            continue
        if role == "eye":
            if not eye_done:
                body.append(f'<g class="{prefix}-eye">{eye}</g>')
                eye_done = True
            continue
        if role == "wing":
            body.append(f'<path class="{prefix}-wing" fill="{fill}" d="{d}"/>')
        elif role == "jaw":
            body.append(f'<path class="{prefix}-jaw" fill="{fill}" d="{d}"/>')
        else:
            body.append(path(fill, d))
    flip = ' transform="translate(128 0) scale(-1 1)"' if face_right else ""
    return (
        f'<g class="{extra_class}">'
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 128 128" overflow="visible">'
        f"<defs>{gradient}</defs>"
        f"<g{flip}>"
        f'<g class="{prefix}-feet">{feet_markup}</g>'
        f'<g class="{prefix}-body">{"".join(body)}</g>'
        f"</g></svg></g>"
    )


def parrot_css(prefix, *, flap="0.9s", wing_angle=14, talk=True, bob=True):
    """CSS animating the parts of parrot(prefix, ...)."""
    rules = [
        f".{prefix}-wing {{ transform-box: fill-box; transform-origin: 40% 4%; "
        f"animation: {prefix}-flap {flap} ease-in-out infinite alternate; }}",
        f"@keyframes {prefix}-flap {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(-{wing_angle}deg); }} }}",
        f".{prefix}-eye {{ transform-box: fill-box; transform-origin: 50% 50%; animation: {prefix}-blink 4.2s infinite; }}",
        f"@keyframes {prefix}-blink {{ 0%, 93%, 100% {{ transform: scaleY(1); }} 96% {{ transform: scaleY(0.1); }} }}",
    ]
    if talk:
        rules += [
            f".{prefix}-jaw {{ transform-box: fill-box; transform-origin: 95% 8%; "
            f"animation: {prefix}-talk 2.4s ease-in-out infinite; }}",
            f"@keyframes {prefix}-talk {{ 0%, 40%, 100% {{ transform: rotate(0deg); }} "
            f"48%, 64%, 80% {{ transform: rotate(-22deg); }} 56%, 72%, 88% {{ transform: rotate(0deg); }} }}",
        ]
    if bob:
        rules += [
            f".{prefix}-body {{ transform-box: fill-box; transform-origin: 45% 96%; "
            f"animation: {prefix}-bob 2.4s ease-in-out infinite; }}",
            f"@keyframes {prefix}-bob {{ 0%, 40%, 100% {{ transform: rotate(0deg); }} "
            f"52% {{ transform: rotate(-5deg) translateY(-2px); }} 76% {{ transform: rotate(3deg); }} }}",
        ]
    return "\n    ".join(rules)
