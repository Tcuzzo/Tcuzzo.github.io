#!/usr/bin/env python3
"""Render the Hydra flow charts on hydra/index.html to static SVG.

The site ships no JavaScript, so the Mermaid sources in hydra/charts/*.mmd are
rendered ahead of time with the Mermaid CLI and served as plain images. Every
color and the font stack come from design-tokens.json; nothing visual is
hardcoded here. Node classes used in the sources (ok, bad, step, req, opt) are
defined from the same tokens at render time.

    python3 tools/render_hydra_charts.py

Needs Node (npx) and a Chrome or Chromium. Set PUPPETEER_EXECUTABLE_PATH if
Puppeteer cannot find a browser on its own. Writes hydra/figures/<name>.svg.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKENS = ROOT / "design-tokens.json"
CHARTS = ROOT / "hydra" / "charts"
FIGURES = ROOT / "hydra" / "figures"
MERMAID_CLI = os.environ.get("MERMAID_CLI", "@mermaid-js/mermaid-cli@11")


def resolve(doc: dict, ref):
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


def oklch_to_hex(value: str) -> str:
    """Mermaid's color math needs sRGB, so convert the oklch tokens."""
    inner = value.strip()[len("oklch("):-1].split("/")[0].split()
    lum, chroma, hue = (float(x) for x in inner)
    a = chroma * math.cos(math.radians(hue))
    b = chroma * math.sin(math.radians(hue))
    l_ = (lum + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (lum - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (lum - 0.0894841775 * a - 1.2914855480 * b) ** 3
    rgb = (
        4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
        -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
        -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_,
    )

    def gamma(c: float) -> int:
        c = min(max(c, 0.0), 1.0)
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        return round(c * 255)

    return "#" + "".join(f"{gamma(c):02x}" for c in rgb)


def palette(doc: dict) -> dict[str, str]:
    p = doc["primitive"]["color"]
    return {k: oklch_to_hex(resolve(doc, v["$value"])) for k, v in p.items()}


def font_stack(doc: dict) -> str:
    stack = resolve(doc, doc["primitive"]["type"]["display"]["$value"])
    return ", ".join(f'"{f}"' if " " in f else f for f in stack)


def class_defs(c: dict[str, str]) -> str:
    rows = {
        "ok": (c["white"], c["green"], c["ink"]),
        "bad": (c["white"], c["orange"], c["ink"]),
        "step": (c["white"], c["line"], c["ink"]),
        "req": (c["white"], c["cyanDark"], c["ink"]),
        "opt": (c["paper"], c["orange"], c["ink"]),
    }
    return "\n".join(
        f"    classDef {name} fill:{f},stroke:{s},color:{t},stroke-width:2px;"
        for name, (f, s, t) in rows.items()
    )


def config(doc: dict) -> dict:
    c = palette(doc)
    return {
        "theme": "base",
        "htmlLabels": False,
        "flowchart": {"htmlLabels": False, "curve": "basis", "padding": 12},
        "sequence": {"mirrorActors": False},
        "themeVariables": {
            "fontFamily": font_stack(doc),
            "fontSize": "16px",
            "background": c["paper"],
            "primaryColor": c["white"],
            "primaryBorderColor": c["cyanDark"],
            "primaryTextColor": c["ink"],
            "secondaryColor": c["paperDeep"],
            "tertiaryColor": c["paper"],
            "lineColor": c["inkSoft"],
            "textColor": c["ink"],
            "edgeLabelBackground": c["paper"],
            "clusterBkg": c["paperDeep"],
            "clusterBorder": c["line"],
            "actorBkg": c["white"],
            "actorBorder": c["cyanDark"],
            "signalColor": c["ink"],
            "noteBkgColor": c["paperDeep"],
        },
    }


def main() -> None:
    doc = json.loads(TOKENS.read_text())
    FIGURES.mkdir(parents=True, exist_ok=True)
    defs = class_defs(palette(doc))
    with tempfile.TemporaryDirectory() as tmp:
        cfg = Path(tmp) / "mermaid.json"
        cfg.write_text(json.dumps(config(doc)))
        pup = Path(tmp) / "puppeteer.json"
        pup_cfg = {"args": ["--no-sandbox"]}
        if os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
            pup_cfg["executablePath"] = os.environ["PUPPETEER_EXECUTABLE_PATH"]
        pup.write_text(json.dumps(pup_cfg))
        for src in sorted(CHARTS.glob("*.mmd")):
            text = src.read_text()
            if text.lstrip().startswith("flowchart"):
                text = text.rstrip() + "\n" + defs + "\n"
            staged = Path(tmp) / src.name
            staged.write_text(text)
            out = FIGURES / f"{src.stem}.svg"
            subprocess.run(
                ["npx", "-y", "-p", MERMAID_CLI, "mmdc", "-q", "-i", str(staged),
                 "-o", str(out), "-c", str(cfg), "-p", str(pup), "-b", "transparent"],
                check=True,
            )
            print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
