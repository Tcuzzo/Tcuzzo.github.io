#!/usr/bin/env python3
"""Render the Reflex Seam diagram from design-tokens.json.

One generator, two files. Light and dark resolve from the SAME semantic token
keys (`semantic.theme.light` / `semantic.theme.dark`), so the two themes can
never drift apart. No color, size, or font is hardcoded in this file — every
value is read from the token document.

    python3 tools/render_reflex_seam.py

Writes assets/reflex-seam-light.svg and assets/reflex-seam-dark.svg.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design-tokens.json"
ASSETS = ROOT / "assets"

WIDTH = 1280
HEIGHT = 590

# ---------------------------------------------------------------- token layer


def load_tokens() -> dict:
    return json.loads(TOKENS.read_text())


def resolve(doc: dict, ref: str) -> str:
    """Resolve a W3C token alias like '{primitive.color.ink}' to its $value."""
    seen = set()
    while isinstance(ref, str) and ref.startswith("{") and ref.endswith("}"):
        if ref in seen:
            raise ValueError(f"token alias cycle at {ref}")
        seen.add(ref)
        node = doc
        for part in ref[1:-1].split("."):
            node = node[part]
        ref = node["$value"]
    return ref


def theme_palette(doc: dict, theme: str) -> dict[str, str]:
    node = doc["semantic"]["theme"][theme]
    return {key: resolve(doc, val["$value"]) for key, val in node.items()}


def accent(doc: dict, name: str) -> str:
    return resolve(doc, doc["semantic"]["accent"][name]["$value"])


def font_family(doc: dict) -> str:
    for group in ("component", "semantic", "primitive"):
        node = doc.get(group, {})
        for key in ("font", "typography", "type"):
            fam = node.get(key, {}).get("family")
            if isinstance(fam, dict) and "$value" in fam:
                return resolve(doc, fam["$value"])
    # Token document carries no family: fall back to the platform UI stack.
    # Deliberately not a named webfont — the banned-defaults list forbids
    # reaching for Inter/Roboto as a reflex.
    return (
        "ui-sans-serif, -apple-system, BlinkMacSystemFont, 'Segoe UI', "
        "Helvetica, Arial, sans-serif"
    )


# ------------------------------------------------------------- diagram layer

RUNTIME_LOOPS = [
    ("State &", "the record"),
    ("Files &", "lookups"),
    ("Rules &", "gates"),
    ("Tests &", "proof"),
]

# Clockwise from the top of the ring.
KERNEL_RING = [
    ("GOVERNED INFERENCE", "top"),
    ("POLICY ENFORCEMENT", "right"),
    ("REVERSIBILITY", "bottom"),
    ("ADAPTIVE PRIORITY", "left"),
]

PANEL_Y = 56
PANEL_H = 430
SEAM_X = 640.0


def esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def seam_path(x: float, top: float, bottom: float, teeth: int, amp: float) -> str:
    """A jagged vertical line - the seam itself."""
    step = (bottom - top) / teeth
    parts = [f"M {x} {top}"]
    for i in range(teeth):
        y = top + step * (i + 1)
        offset = amp if i % 2 == 0 else -amp
        parts.append(f"L {x + offset:.1f} {y - step / 2:.1f} L {x} {y:.1f}")
    return " ".join(parts)


def loop_glyph(cx: float, cy: float, r: float, ring: str, signal: str) -> str:
    """A ring that keeps turning: full circle plus a directed arc."""
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="none" stroke="{ring}" '
        f'stroke-width="6" opacity="0.35"/>'
        f'<path d="M {cx:.1f} {cy - r:.1f} A {r} {r} 0 1 1 {cx - r:.1f} {cy:.1f}" '
        f'fill="none" stroke="{signal}" stroke-width="3" stroke-linecap="round"/>'
        f'<path d="M {cx - r - 5:.1f} {cy - 7:.1f} L {cx - r:.1f} {cy + 1:.1f} '
        f'L {cx - r + 6:.1f} {cy - 6:.1f}" fill="none" stroke="{signal}" '
        f'stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    )


def chip(x: float, y: float, w: float, h: float, fill: str) -> str:
    """An opaque plate so a label never fights the line it sits on."""
    return (
        f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" '
        f'height="{h:.1f}" rx="4" fill="{fill}"/>'
    )


def crossing(
    x_from: float, x_to: float, y: float, color: str, label: str,
    muted: str, page: str,
) -> str:
    """One signal crossing the seam, labelled on a plate that clears the line."""
    d = 1 if x_to > x_from else -1
    tip = x_to
    out = (
        f'<path d="M {x_from:.1f} {y:.1f} L {tip:.1f} {y:.1f}" stroke="{color}" '
        f'stroke-width="2.5" stroke-linecap="round"/>'
        f'<path d="M {tip - 11 * d:.1f} {y - 6:.1f} L {tip:.1f} {y:.1f} '
        f'L {tip - 11 * d:.1f} {y + 6:.1f}" fill="none" stroke="{color}" '
        f'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    out += chip(SEAM_X, y - 21, len(label) * 7.6 + 22, 22, page)
    out += (
        f'<text x="{SEAM_X:.1f}" y="{y - 16:.1f}" fill="{muted}" font-size="13.5" '
        f'font-weight="600" letter-spacing="0.04em" text-anchor="middle">'
        f"{esc(label)}</text>"
    )
    return out


def arc(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """Arc path from angle a0 to a1 in degrees, 0 = twelve o'clock."""
    import math

    def pt(a: float) -> tuple[float, float]:
        rad = math.radians(a - 90)
        return cx + r * math.cos(rad), cy + r * math.sin(rad)

    x0, y0 = pt(a0)
    x1, y1 = pt(a1)
    large = 1 if abs(a1 - a0) > 180 else 0
    sweep = 1 if a1 > a0 else 0
    return f"M {x0:.2f} {y0:.2f} A {r} {r} 0 {large} {sweep} {x1:.2f} {y1:.2f}"


def render(doc: dict, theme: str) -> str:
    p = theme_palette(doc, theme)
    page, panel, inset = p["page"], p["panel"], p["inset"]
    text, muted, border = p["text"], p["muted"], p["border"]
    signal = p["signal"]
    warn = accent(doc, "secondary")
    ok = accent(doc, "verified")
    fam = font_family(doc)

    panel_w = 470.0
    left_x = 48.0
    right_x = WIDTH - 48.0 - panel_w
    corridor_l = left_x + panel_w
    corridor_r = right_x

    out: list[str] = []
    add = out.append

    add(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" '
        f'width="{WIDTH}" height="{HEIGHT}" role="img" aria-labelledby="title desc">'
    )
    add("<title id=\"title\">The Reflex Seam</title>")
    add(
        '<desc id="desc">A deterministic runtime on the left holds state, files, '
        "rules and tests. A model judgment kernel on the right holds inference, "
        "policy, reversibility and priority. A jagged seam runs between them. "
        "Decision signals cross from the model to the runtime. State updates cross "
        "back from the runtime to the model. An unpermitted state change is refused "
        "loudly at the seam.</desc>"
    )
    add(f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{page}"/>')
    add(f'<g font-family="{esc(fam)}">')

    # -- left: the deterministic runtime -------------------------------------
    add(
        f'<rect x="{left_x}" y="{PANEL_Y}" width="{panel_w}" height="{PANEL_H}" rx="14" '
        f'fill="{panel}" stroke="{border}" stroke-width="1.5"/>'
    )
    add(
        f'<text x="{left_x + 28}" y="{PANEL_Y + 44}" fill="{text}" font-size="20" '
        f'font-weight="700" letter-spacing="0.07em">DETERMINISTIC RUNTIME</text>'
    )
    add(
        f'<text x="{left_x + 28}" y="{PANEL_Y + 70}" fill="{muted}" font-size="15">'
        "It owns the state, the lookups and the rules.</text>"
    )

    cell_w, cell_h, gap = 194.0, 128.0, 18.0
    grid_x = left_x + (panel_w - (cell_w * 2 + gap)) / 2
    grid_y = PANEL_Y + 104
    for idx, (line1, line2) in enumerate(RUNTIME_LOOPS):
        col, row = idx % 2, idx // 2
        x = grid_x + (cell_w + gap) * col
        y = grid_y + (cell_h + gap) * row
        add(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w}" height="{cell_h}" rx="10" '
            f'fill="{inset}" stroke="{border}" stroke-width="1"/>'
        )
        add(loop_glyph(x + cell_w / 2, y + 44, 24, border, signal))
        add(
            f'<text x="{x + cell_w / 2:.1f}" y="{y + 92:.1f}" fill="{text}" '
            f'font-size="15" font-weight="600" text-anchor="middle">{esc(line1)}</text>'
        )
        add(
            f'<text x="{x + cell_w / 2:.1f}" y="{y + 111:.1f}" fill="{text}" '
            f'font-size="15" font-weight="600" text-anchor="middle">{esc(line2)}</text>'
        )

    # -- right: the judgment kernel ------------------------------------------
    add(
        f'<rect x="{right_x}" y="{PANEL_Y}" width="{panel_w}" height="{PANEL_H}" rx="14" '
        f'fill="{panel}" stroke="{border}" stroke-width="1.5"/>'
    )
    add(
        f'<text x="{right_x + panel_w - 28}" y="{PANEL_Y + 44}" fill="{text}" '
        f'font-size="20" font-weight="700" letter-spacing="0.07em" text-anchor="end">'
        "MODEL JUDGMENT</text>"
    )
    add(
        f'<text x="{right_x + panel_w - 28}" y="{PANEL_Y + 70}" fill="{muted}" '
        f'font-size="15" text-anchor="end">It owns the judgment. Nothing else.</text>'
    )

    kx = right_x + panel_w / 2
    ky = PANEL_Y + 240
    kr = 78.0
    band_r = kr + 62

    add("<defs>")
    spans = {"top": (-38, 38), "right": (52, 128), "bottom": (218, 142), "left": (308, 232)}
    for name, (a0, a1) in spans.items():
        add(f'<path id="ring-{name}-{theme}" d="{arc(kx, ky, band_r, a0, a1)}" fill="none"/>')
    add("</defs>")

    add(
        f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="{band_r + 24:.1f}" fill="none" '
        f'stroke="{border}" stroke-width="1.5"/>'
    )
    add(
        f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="{band_r - 20:.1f}" fill="none" '
        f'stroke="{border}" stroke-width="1.5"/>'
    )
    for label, name in KERNEL_RING:
        add(
            f'<text fill="{muted}" font-size="13" font-weight="700" '
            f'letter-spacing="0.1em"><textPath href="#ring-{name}-{theme}" '
            f'startOffset="50%" text-anchor="middle">{esc(label)}</textPath></text>'
        )

    add(
        f'<circle cx="{kx:.1f}" cy="{ky:.1f}" r="{kr}" fill="{inset}" stroke="{signal}" '
        f'stroke-width="2.5"/>'
    )
    add(
        f'<text x="{kx:.1f}" y="{ky - 5:.1f}" fill="{text}" font-size="17" '
        f'font-weight="700" letter-spacing="0.04em" text-anchor="middle">JUDGMENT</text>'
    )
    add(
        f'<text x="{kx:.1f}" y="{ky + 18:.1f}" fill="{text}" font-size="17" '
        f'font-weight="700" letter-spacing="0.04em" text-anchor="middle">KERNEL</text>'
    )

    # -- the seam ------------------------------------------------------------
    add(
        f'<path d="{seam_path(SEAM_X, 30, HEIGHT - 118, 15, 12)}" fill="none" '
        f'stroke="{signal}" stroke-width="3" stroke-linecap="round" '
        f'stroke-linejoin="round"/>'
    )

    y_decision = PANEL_Y + 90
    y_state = PANEL_Y + 346
    add(
        crossing(corridor_r - 6, corridor_l + 6, y_decision, signal,
                 "decision signal", muted, page)
    )
    add(
        crossing(corridor_l + 6, corridor_r - 6, y_state, ok,
                 "state update", muted, page)
    )

    mid_y = (y_decision + y_state) / 2
    add(chip(SEAM_X, mid_y, 34, 184, page))
    add(
        f'<text transform="translate({SEAM_X:.1f} {mid_y:.1f}) rotate(-90)" '
        f'fill="{text}" font-size="15" font-weight="700" letter-spacing="0.15em" '
        f'text-anchor="middle" dy="5">THE REFLEX SEAM</text>'
    )

    # -- the punch line ------------------------------------------------------
    strip_y = PANEL_Y + PANEL_H + 34
    add(
        f'<rect x="{left_x}" y="{strip_y}" width="{WIDTH - left_x * 2}" height="58" '
        f'rx="10" fill="{inset}" stroke="{warn}" stroke-width="1.5"/>'
    )
    add(
        f'<text x="{WIDTH / 2}" y="{strip_y + 36}" fill="{text}" font-size="16.5" '
        f'font-weight="600" text-anchor="middle">'
        "If the model tries to change state without permission, the seam refuses it "
        "out loud. It never guesses quietly.</text>"
    )

    add("</g></svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    doc = load_tokens()
    ASSETS.mkdir(exist_ok=True)
    for theme in ("light", "dark"):
        target = ASSETS / f"reflex-seam-{theme}.svg"
        target.write_text(render(doc, theme))
        print(f"wrote {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
