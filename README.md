# BACKS AIOS — public website

The hero, the Reflex Seam section, and the public project directory are in
`index.html`. The illustrated research paper is in `research/index.html`. This is a
static site: no runtime API, analytics, form, app credentials, or third-party
JavaScript.

## The Reflex Seam diagram

`tools/render_reflex_seam.py` renders `assets/reflex-seam-light.svg` and
`assets/reflex-seam-dark.svg` from `design-tokens.json`. One generator, two themes,
both resolved from the same `semantic.theme.*` keys, so light and dark cannot drift
apart. No color, size, or font is hardcoded in the generator.

    python3 tools/render_reflex_seam.py

The landing page uses the light file, because the page paints a light ground. The dark
file is for the sibling repositories' READMEs, where GitHub flips the theme. Both files
are copied into `HydraAgent_public`, `bucks`, and `backs-aios-skills` and embedded
there with `<picture>`.

## Check

Run `node --test *.test.mjs` from this directory. Serve this directory with any static HTTP server to preview the real pages. The authored sources need no install, build, or JavaScript to read.

## Publish

GitHub Pages uses main at the repository root. `.nojekyll` preserves the static assets. Publication is operator-directed. Keep private runtime files and operational records out of this repository.

## Credits

Architecture, story, and BACKS-native work: Truitt Cuzzo. The paper names Matt Pocock, Robert C. Martin, and other published source contributions. Original BACKS hero media is reused from the product. Conceptual imagery is not live runtime evidence. OpenMontage is identified as a fork with an upstream link. Linked projects retain their own licenses; this site does not relicense them.
