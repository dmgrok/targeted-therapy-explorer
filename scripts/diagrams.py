#!/usr/bin/env python3
"""Inline SVG diagrams for the steps front door.

Risograph print identity: paper #f4efe4, teal ink #1b4f4c, pink inks
#b02058 / #d13a72. Two-ink look: teal line art over a slightly
mis-registered pink plate, with a soft ink-edge filter on plates only.
Text is never placed on a texture; every <text> carries data-bg (the solid
colour behind it) so the contrast gate can measure it.

Each figure is emitted twice: a wide layout (desktop) and a tall layout
(mobile), switched by CSS. Both carry role="img", <title> and <desc>.
Labels sit on the drawn objects; connectors are minimal flow lines only.
No new claims: every label is taken from the page text, the static AI
boxes, or the verified case data file.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAPER = "#f4efe4"
INK = "#1b4f4c"
DEEP = "#122e2c"
PINK = "#b02058"
PINK_L = "#d13a72"
WHITE = "#ffffff"

HEAD = "'Barlow Condensed', 'Arial Narrow', sans-serif"
BODY = "'Source Sans 3', 'Source Sans Pro', Arial, sans-serif"


def e(s: str) -> str:
    return escape(s, quote=True)


# ---------------------------------------------------------------- primitives

def text(x, y, s, *, size=16, fill=DEEP, bg=PAPER, weight=400, family=BODY,
         anchor="start", spacing=None, upper=False) -> str:
    ls = f' letter-spacing="{spacing}"' if spacing is not None else ""
    content = s.upper() if upper else s
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{ls} '
        f'data-bg="{bg}">{e(content)}</text>'
    )


def wrap(s: str, maxchars: int) -> list[str]:
    words = s.split()
    lines, cur = [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= maxchars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def lines_text(x, y, lines, *, lh=20, **kw) -> str:
    return "".join(text(x, y + i * lh, ln, **kw) for i, ln in enumerate(lines))


def defs(p: str) -> str:
    return (
        "<defs>"
        f'<filter id="{p}-ink" x="-10%" y="-10%" width="120%" height="120%">'
        '<feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="n"/>'
        '<feDisplacementMap in="SourceGraphic" in2="n" scale="2.4" xChannelSelector="R" yChannelSelector="G"/>'
        "</filter>"
        f'<pattern id="{p}-dots" width="7" height="7" patternUnits="userSpaceOnUse">'
        f'<circle cx="3.5" cy="3.5" r="1.5" fill="{PINK_L}"/></pattern>'
        f'<marker id="{p}-arr" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M1 1 L9 5 L1 9" fill="none" stroke="{INK}" stroke-width="1.8"/></marker>'
        f'<marker id="{p}-arrp" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M1 1 L9 5 L1 9" fill="none" stroke="{PINK}" stroke-width="1.8"/></marker>'
        "</defs>"
    )


def plate(x, y, w, h, p, dx=6, dy=6, opacity=0.55) -> str:
    """Mis-registered pink plate under a shape (risograph overprint)."""
    return (
        f'<rect x="{x + dx:.1f}" y="{y + dy:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{PINK_L}" opacity="{opacity}" filter="url(#{p}-ink)" '
        'style="mix-blend-mode:multiply"/>'
    )


def line(x1, y1, x2, y2, p, *, color=INK, dash=False, width=2.4, pink=False) -> str:
    d = ' stroke-dasharray="7 6"' if dash else ""
    m = f"{p}-arrp" if pink else f"{p}-arr"
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" '
        f'stroke-width="{width}"{d} marker-end="url(#{m})"/>'
    )


def svg_open(p: str, w: int, h: int, title: str, desc: str, cls: str) -> str:
    return (
        f'<svg class="{cls}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-labelledby="{p}-t {p}-d" xmlns="http://www.w3.org/2000/svg" '
        'preserveAspectRatio="xMidYMin meet">'
        f'<title id="{p}-t">{e(title)}</title><desc id="{p}-d">{e(desc)}</desc>'
        + defs(p)
    )


# ------------------------------------------------------------------- glyphs

def glyph(kind: str, cx: float, cy: float, p: str) -> str:
    """Small geometric line glyph (teal) over an offset pink ink dot."""
    s = f'stroke="{INK}" stroke-width="2.6" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    under = (
        f'<circle cx="{cx + 5:.1f}" cy="{cy + 4:.1f}" r="15" fill="{PINK_L}" opacity="0.5" '
        f'filter="url(#{p}-ink)" style="mix-blend-mode:multiply"/>'
    )
    g = f'<g transform="translate({cx:.1f} {cy:.1f})">'
    if kind == "tissue":
        body = (f'<path d="M-15 2 C-15 -12 -2 -16 7 -12 C17 -8 17 6 9 11 C1 16 -15 14 -15 2 Z" {s}/>'
                f'<circle cx="-4" cy="0" r="2.4" fill="{INK}"/><circle cx="5" cy="-3" r="2.4" fill="{INK}"/>'
                f'<circle cx="3" cy="6" r="2.4" fill="{INK}"/>')
    elif kind == "drop":
        body = (f'<path d="M-6 -16 C-9 -6 -18 0 -14 9 C-11 15 -1 15 1 8 C3 0 -4 -6 -6 -16 Z" {s}/>'
                f'<path d="M6 -14 L6 14 M2 14 L10 14 M3 -14 L9 -14" {s}/>'
                f'<path d="M12 -14 L12 10 C12 16 18 16 18 10 L18 -14" {s}/>')
    elif kind == "lens":
        body = f'<circle cx="-4" cy="-4" r="11" {s}/><path d="M4 4 L15 15" {s} stroke-width="4"/>'
    elif kind == "report":
        body = (f'<path d="M-12 -16 L6 -16 L12 -10 L12 16 L-12 16 Z" {s}/>'
                f'<path d="M-7 -6 L7 -6 M-7 1 L7 1 M-7 8 L3 8" {s}/>')
    elif kind == "helix":
        body = (f'<path d="M-8 -16 C8 -8 8 8 -8 16" {s}/><path d="M8 -16 C-8 -8 -8 8 8 16" {s}/>'
                f'<path d="M-4 -10 L4 -10 M-6 0 L6 0 M-4 10 L4 10" {s} stroke-width="2"/>')
    elif kind == "snapshot":
        body = (f'<path d="M-15 -8 L-15 -14 L-9 -14 M9 -14 L15 -14 L15 -8 M15 8 L15 14 L9 14 M-9 14 L-15 14 L-15 8" {s}/>'
                f'<circle cx="0" cy="0" r="5" fill="{INK}"/>')
    elif kind == "docs":
        body = (f'<rect x="-14" y="-12" width="20" height="26" {s}/>'
                f'<rect x="-6" y="-17" width="20" height="26" fill="{WHITE}" stroke="{INK}" stroke-width="2.6"/>'
                f'<path d="M-2 -9 L10 -9 M-2 -3 L10 -3 M-2 3 L6 3" {s} stroke-width="2"/>')
    elif kind == "person":
        body = f'<circle cx="0" cy="-8" r="6.5" {s}/><path d="M-13 15 C-13 3 13 3 13 15" {s}/>'
    elif kind == "table":
        dots = "".join(
            f'<circle cx="{x}" cy="{y}" r="3.4" fill="{INK}"/>'
            for x, y in ((0, -17), (16, -5), (10, 14), (-10, 14), (-16, -5))
        )
        body = f'<circle cx="0" cy="0" r="9" {s}/>' + dots
    elif kind == "folder":
        body = (f'<path d="M-16 -10 L-5 -10 L-2 -6 L16 -6 L16 13 L-16 13 Z" {s}/>'
                f'<path d="M-16 -1 L16 -1" {s} stroke-width="2"/>')
    elif kind == "chart":
        body = (f'<path d="M-16 -15 L-16 14 L16 14" {s}/>'
                f'<path d="M-11 6 L-3 -2 L4 3 L12 -9" {s}/>'
                f'<circle cx="-11" cy="6" r="2.4" fill="{INK}"/><circle cx="-3" cy="-2" r="2.4" fill="{INK}"/>'
                f'<circle cx="4" cy="3" r="2.4" fill="{INK}"/><circle cx="12" cy="-9" r="2.4" fill="{INK}"/>')
    elif kind == "return":
        body = (f'<path d="M12 -6 A13 13 0 1 0 13 5" {s}/>'
                f'<path d="M5 -9 L12 -6 L15 -13" {s}/>')
    elif kind == "gate":
        body = (f'<path d="M-14 15 L-14 -15 L14 -15 L14 15" {s}/>'
                f'<path d="M-14 -15 L2 -10 L2 18 L-14 15" fill="{WHITE}" stroke="{INK}" stroke-width="2.6" stroke-linejoin="round"/>'
                f'<circle cx="-2" cy="3" r="1.8" fill="{INK}"/>')
    else:
        raise ValueError(kind)
    return under + g + body + "</g>"


# ----------------------------------------------------------------- overview

STEP_NODES = [
    (1, "Diagnosis", "Pathologist’s report", "step-diagnosis"),
    (2, "Molecular testing", "Tissue or blood", "step-testing"),
    (3, "Second opinion", "Another specialist", "step-second-opinion"),
    (4, "Tumour board", "Specialists meet", "step-tumour-board"),
    (5, "Matching", "Drug pages link here", "step-matching"),
    (6, "Monitoring", "Markers can change", "step-monitoring"),
    (7, "Access routes", "Before full authorisation", "step-access"),
]

OVERVIEW_TITLE = "The shared path: seven steps"
OVERVIEW_DESC = (
    "Step 1, diagnosis and pathology, leads to step 2, molecular testing, "
    "then step 3, a second opinion, then step 4, the tumour board, then "
    "step 5, matching to options or trials. Matching and step 6, monitoring "
    "and re-testing, form a loop: results are followed over time, and a "
    "re-test feeds back into matching. Step 7, access routes, branches off "
    "from matching. This is a common path, not a care plan."
)


def node(x, y, w, h, n, title, sub, p, *, hub=False, tsize=27, ssize=16, subchars=24) -> str:
    fill = INK if hub else WHITE
    fg = PAPER if hub else DEEP
    tag = PAPER if hub else PINK
    out = [plate(x, y, w, h, p)]
    out.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
        f'stroke="{INK}" stroke-width="2.4"/>'
    )
    out.append(text(x + 16, y + 26, f"Step {n}", size=13, weight=700, fill=tag,
                    bg=fill, family=BODY, spacing="1.6", upper=True))
    out.append(text(x + 16, y + 26 + tsize + 6, title, size=tsize, weight=600,
                    fill=fg, bg=fill, family=HEAD))
    sy = y + 26 + tsize + 6 + ssize + 12
    if hub:
        tw = len(sub) * ssize * 0.5 + 24
        out.append(f'<rect x="{x + 14}" y="{sy - ssize - 2}" width="{tw:.0f}" height="{ssize + 12}" '
                   f'rx="{(ssize + 12) / 2:.0f}" fill="{PAPER}"/>')
        out.append(text(x + 26, sy + 2, sub, size=ssize - 1, weight=600, fill=DEEP, bg=PAPER))
    else:
        out.append(lines_text(x + 16, sy, wrap(sub, subchars), lh=ssize + 4,
                              size=ssize, fill=INK, bg=fill))
    return "".join(out)


def pill(cx, cy, label, *, size=16, h=30) -> str:
    w = len(label) * size * 0.52 + 30
    return (
        f'<rect x="{cx - w / 2:.1f}" y="{cy - h / 2:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
        f'fill="{WHITE}" stroke="{PINK}" stroke-width="2.4"/>'
        + text(cx, cy + size * 0.36, label, size=size, weight=700, fill=PINK, bg=WHITE,
               anchor="middle")
    )


def overview_wide() -> str:
    p = "ov-w"
    W, H = 1200, 590
    nw, nh = 240, 122
    xs = [51, 337, 623, 909]
    out = [svg_open(p, W, H, OVERVIEW_TITLE, OVERVIEW_DESC, "dg-wide")]
    # Row 1: steps 1–4
    for i, x in enumerate(xs):
        n, t, s, _ = STEP_NODES[i]
        out.append(node(x, 46, nw, nh, n, t, s, p))
    for i in range(3):
        out.append(line(xs[i] + nw + 8, 107, xs[i + 1] - 10, 107, p))
    # Row 2: 6 (left) and 5 (right, hub); loop between
    x5, y5 = 909, 270
    x6, y6 = 509, 270
    out.append(line(1029, 46 + nh + 8, 1029, y5 - 10, p))
    # halftone loop field behind the loop connectors
    # 5 -> 6 is an ordinary next step; only the 6 -> 5 return is pink (re-test).
    out.append(line(x5 - 8, y5 + 40, x6 + nw + 12, y5 + 40, p))
    out.append(f'<rect x="{x6 + nw + 10}" y="{y5 + 68}" width="{x5 - x6 - nw - 20}" height="44" '
               f'fill="url(#{p}-dots)" opacity="0.7"/>')
    out.append(line(x6 + nw + 8, y5 + 90, x5 - 12, y5 + 90, p, color=PINK, pink=True))
    out.append(pill((x6 + nw + x5) / 2, y5 + 90, "Re-test"))
    out.append(node(x6, y6, nw, nh, *STEP_NODES[5][:3], p))
    out.append(node(x5, y5, nw, nh, *STEP_NODES[4][:3], p, hub=True))
    # Row 3: 7 branches from 5
    y7 = 450
    out.append(line(1029, y5 + nh + 8, 1029, y7 - 10, p, dash=True))
    out.append(node(x5, y7, nw, nh, *STEP_NODES[6][:3], p))
    # Left: a quiet title block, on paper
    out.append(text(51, 318, "One shared path", size=34, weight=700, fill=DEEP, family=HEAD))
    out.append(lines_text(51, 350, ["Not a care plan. The same path", "wherever you live."], lh=22,
                          size=17, fill=INK))
    # Key, row 3 left: drawn swatches with labels on paper
    ky = 486
    out.append(f'<line x1="51" y1="{ky}" x2="111" y2="{ky}" stroke="{INK}" stroke-width="2.4" marker-end="url(#{p}-arr)"/>')
    out.append(text(126, ky + 6, "Next step", size=16, fill=DEEP))
    out.append(f'<line x1="271" y1="{ky}" x2="331" y2="{ky}" stroke="{PINK}" stroke-width="2.4" marker-end="url(#{p}-arrp)"/>')
    out.append(text(346, ky + 6, "Loop: re-testing feeds matching", size=16, fill=DEEP))
    out.append(f'<line x1="51" y1="{ky + 44}" x2="111" y2="{ky + 44}" stroke="{INK}" stroke-width="2.4" stroke-dasharray="7 6" marker-end="url(#{p}-arr)"/>')
    out.append(text(126, ky + 50, "Branch: access routes", size=16, fill=DEEP))
    out.append("</svg>")
    return "".join(out)


def overview_tall() -> str:
    p = "ov-t"
    W = 400
    nw, nh = 300, 96
    x = 50
    ys = [20, 146, 272, 398, 524]
    out_nodes = []
    out = []
    for i, y in enumerate(ys[:4]):
        n, t, s, _ = STEP_NODES[i]
        out_nodes.append(node(x, y, nw, nh, n, t, s, p, tsize=24, ssize=15, subchars=30))
    for i in range(4):
        out.append(line(200, ys[i] + nh + 7, 200, ys[i + 1] - 9, p))
    out_nodes.append(node(x, ys[4], nw, nh, *STEP_NODES[4][:3], p, hub=True, tsize=24, ssize=15))
    y67 = ys[4] + nh + 100
    sw, sh = 172, 118
    x7, x6 = 18, 210
    # loop 5 <-> 6 (right), branch 5 -> 7 (left)
    # 5 -> 6 next step (teal); 6 -> 5 return is the pink re-test loop.
    out.append(line(x6 + 30, ys[4] + nh + 7, x6 + 30, y67 - 9, p))
    out.append(f'<rect x="{x6 + sw - 70}" y="{ys[4] + nh + 12}" width="80" height="76" '
               f'fill="url(#{p}-dots)" opacity="0.7"/>')
    out.append(line(x6 + sw - 30, y67 - 7, x6 + sw - 30, ys[4] + nh + 9, p, color=PINK, pink=True))
    out.append(pill(x6 + sw - 30, ys[4] + nh + 50, "Re-test", size=15, h=28))
    out.append(line(x7 + 60, ys[4] + nh + 7, x7 + 60, y67 - 9, p, dash=True))
    out_nodes.append(node(x6, y67, sw, sh, *STEP_NODES[5][:3], p, tsize=22, ssize=15, subchars=18))
    out_nodes.append(node(x7, y67, sw, sh, *STEP_NODES[6][:3], p, tsize=22, ssize=15, subchars=18))
    H = y67 + sh + 24
    return (svg_open(p, W, H, OVERVIEW_TITLE, OVERVIEW_DESC, "dg-tall")
            + "".join(out) + "".join(out_nodes) + "</svg>")


def overview_figure() -> str:
    return (
        '<figure class="dg dg-overview" id="path-diagram">'
        + overview_wide() + overview_tall()
        + "</figure>"
    )


# --------------------------------------------------------------- step panels

STEP_SPECS = {
    "step-diagnosis": {
        "title": "Step 1, diagnosis and pathology",
        "flow": [("tissue", "Tissue from a biopsy or surgery"),
                 ("lens", "A pathologist studies it"),
                 ("report", "The report is the diagnosis")],
        "who": ["Pathologist", "Your doctor", "You"],
        "can": ["A short glossary of hard words", "Questions for the visit"],
        "not": ["Interpret the report before your doctor has seen it"],
    },
    "step-testing": {
        "title": "Step 2, molecular testing",
        "flow": [("drop", "Tissue or a blood sample"),
                 ("helix", "Test for gene and protein markers"),
                 ("snapshot", "Result: a snapshot")],
        "who": ["Doctors", "Hospital platforms (France)", "Your care team"],
        "can": ["Explain types of tests", "Help you prepare questions"],
        "not": ["Predict a result", "Match a person to a drug"],
    },
    "step-second-opinion": {
        "title": "Step 3, second opinion",
        "flow": [("docs", "Your reports and questions"),
                 ("person", "Another specialist")],
        "who": ["You", "Another specialist"],
        "can": ["Help you organise reports and questions"],
        "not": ["Be a second opinion", "Pick a doctor for you"],
    },
    "step-tumour-board": {
        "title": "Step 4, tumour board",
        "flow": [("folder", "Your file"),
                 ("table", "Specialists meet (RCP in France)"),
                 ("lens", "Some centres: a molecular review")],
        "who": ["A group of specialists"],
        "can": ["Explain what the meeting is for"],
        "not": ["Second-guess the board", "Take the place of a molecular review"],
    },
    "step-matching": {
        "title": "Step 5, matching to options or trials",
        "branch": (("helix", "Gene-test result"),
                   ["Approved drug", ("Off-label use", "A use not listed on the label"), "Clinical trial"]),
        "who": ["You", "Treating doctor"],
        "can": ["Summarise an official trial record as it stands"],
        "not": ["Declare that a person is eligible for a trial or a drug"],
    },
    "step-monitoring": {
        "title": "Step 6, monitoring and re-testing",
        "flow": [("chart", "Markers followed over time"),
                 ("return", "The cancer comes back"),
                 ("helix", "The team may test again")],
        "who": ["Your care team"],
        "can": ["Help you list questions for a follow-up visit"],
        "not": ["Read a scan or a lab file and declare news", "Advise a new biopsy"],
    },
    "step-access": {
        "title": "Step 7, access routes",
        "branch": (("gate", "Before full authorisation"),
                   ["Early access (AAP)", "Compassionate access (AAC)", "EU compassionate use"]),
        "who_head": "Who runs it",
        "who": ["HAS (AAP)", "ANSM (AAC)", "EU Member States"],
        "can": ["Say which kind of route a public record describes", "Point to the official page"],
        "not": ["Say that a person qualifies"],
    },
}


def _chips(x0, y0, W, labels, size=15) -> tuple[str, float]:
    out, x, y, h = [], x0, y0, 32
    for lab in labels:
        w = len(lab) * size * 0.54 + 42
        if x + w > x0 + W and x > x0:
            x, y = x0, y + h + 8
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h}" rx="{h / 2}" '
                   f'fill="{PAPER}" stroke="{INK}" stroke-width="2"/>')
        out.append(f'<circle cx="{x + 15:.1f}" cy="{y + h / 2:.1f}" r="4" fill="{PINK}"/>')
        out.append(text(x + 26, y + h / 2 + size * 0.36, lab, size=size, weight=600,
                        fill=DEEP, bg=PAPER))
        x += w + 10
    return "".join(out), y + h - y0


def panel_what(spec: dict, x0: float, y0: float, W: float, p: str) -> tuple[str, float]:
    out = [text(x0, y0 + 16, "What happens", size=13, weight=700, fill=PINK,
                spacing="1.6", upper=True)]
    top = y0 + 30
    oh = 128
    if "flow" in spec:
        items = spec["flow"]
        n = len(items)
        gap = 36
        ow = (W - (n - 1) * gap) / n
        chars = max(10, int(ow / 8.3))
        most = max(len(wrap(lab, chars)) for _g, lab in items)
        oh = max(oh, 80 + (most - 1) * 19 + 26)
        for i, (g, lab) in enumerate(items):
            ox = x0 + i * (ow + gap)
            out.append(f'<rect x="{ox:.1f}" y="{top}" width="{ow:.1f}" height="{oh}" '
                       f'fill="{WHITE}" stroke="{INK}" stroke-width="2"/>')
            out.append(glyph(g, ox + ow / 2, top + 34, p))
            lns = wrap(lab, chars)
            out.append("".join(
                text(ox + ow / 2, top + 80 + k * 19, ln, size=15.5, weight=600, fill=DEEP,
                     bg=WHITE, anchor="middle")
                for k, ln in enumerate(lns)))
            if i < n - 1:
                out.append(line(ox + ow + 5, top + 34, ox + ow + gap - 7, top + 34, p))
    else:
        (g, lab), opts = spec["branch"]
        sw = min(130, W * 0.34)
        bx = x0 + sw + 48
        bw = x0 + W - bx
        bg_ = 13
        ochars = max(12, int((bw - 26) / 8.3))
        wrapped, subs = [], []
        for o in opts:
            lab_o, sub_o = (o if isinstance(o, tuple) else (o, ""))
            wrapped.append(wrap(lab_o, ochars))
            subs.append(wrap(sub_o, int((bw - 26) / 7.2)) if sub_o else [])
        hs = [34 + 19 * (len(w) - 1) + 18 * len(s) for w, s in zip(wrapped, subs)]
        total = sum(hs) + bg_ * (len(hs) - 1)
        slines = wrap(lab, max(10, int(sw / 8.3)))
        oh = max(oh, total, 80 + (len(slines) - 1) * 19 + 26)
        oy = top + (oh - total) / 2
        out.append(f'<rect x="{x0}" y="{top}" width="{sw:.1f}" height="{oh}" '
                   f'fill="{WHITE}" stroke="{INK}" stroke-width="2"/>')
        out.append(glyph(g, x0 + sw / 2, top + 34, p))
        out.append("".join(
            text(x0 + sw / 2, top + 80 + k * 19, ln, size=15.5, weight=600, fill=DEEP,
                 bg=WHITE, anchor="middle")
            for k, ln in enumerate(slines)))
        by = oy
        for w, sb, bh in zip(wrapped, subs, hs):
            out.append(line(x0 + sw + 5, top + oh / 2, bx - 7, by + bh / 2, p))
            out.append(plate(bx, by, bw, bh, p, dx=4, dy=4, opacity=0.45))
            out.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh}" '
                       f'fill="{WHITE}" stroke="{INK}" stroke-width="2"/>')
            out.append("".join(
                text(bx + 14, by + 22.5 + k * 19, ln, size=15.5, weight=600, fill=DEEP, bg=WHITE)
                for k, ln in enumerate(w)))
            out.append("".join(
                text(bx + 14, by + 22.5 + len(w) * 19 + k * 18, ln, size=13.5, weight=400,
                     fill=DEEP, bg=WHITE)
                for k, ln in enumerate(sb)))
            by += bh + bg_
    wy = top + oh + 24
    out.append(text(x0, wy + 14, spec.get("who_head", "Who is involved"), size=13,
                    weight=700, fill=PINK, spacing="1.6", upper=True))
    chips, ch = _chips(x0, wy + 26, W, spec["who"])
    out.append(chips)
    return "".join(out), (wy + 26 + ch) - y0


def panel_ai(spec: dict, x0: float, y0: float, W: float, p: str) -> tuple[str, float]:
    out = [text(x0, y0 + 16, "How AI can help — and its limits", size=13, weight=700,
                fill=PINK, spacing="1.6", upper=True)]
    chars = max(18, int((W - 52) / 8.1))

    def block(y, kind, items):
        lines = []
        for it in items:
            for k, ln in enumerate(wrap(it, chars)):
                lines.append((k == 0, ln))
        h = 46 + 22 * len(lines) + 6
        if kind == "can":
            fill, fg, tagfill, tagfg, tagtxt = INK, PAPER, PAPER, DEEP, "AI can"
            o = [plate(x0, y, W, h, p, dx=5, dy=5, opacity=0.5),
                 f'<rect x="{x0}" y="{y}" width="{W}" height="{h}" fill="{INK}"/>']
        else:
            fill, fg, tagfill, tagfg, tagtxt = WHITE, DEEP, PINK, WHITE, "Must not"
            o = [f'<rect x="{x0}" y="{y}" width="{W}" height="{h}" fill="{WHITE}" '
                 f'stroke="{PINK}" stroke-width="2.6"/>']
        tw = len(tagtxt) * 8.6 + 22
        o.append(f'<rect x="{x0 + 14}" y="{y + 12}" width="{tw:.0f}" height="24" fill="{tagfill}"/>')
        o.append(text(x0 + 25, y + 29, tagtxt, size=13, weight=700, fill=tagfg, bg=tagfill,
                      spacing="1.4", upper=True))
        for i, (first, ln) in enumerate(lines):
            ly = y + 60 + 22 * i
            if first:
                if kind == "can":
                    o.append(f'<rect x="{x0 + 16}" y="{ly - 10}" width="8" height="8" fill="{PAPER}"/>')
                else:
                    o.append(f'<path d="M{x0 + 15} {ly - 11} l9 9 m0 -9 l-9 9" stroke="{PINK}" stroke-width="2.4"/>')
            o.append(text(x0 + 34, ly, ln, size=16, fill=fg, bg=fill))
        return "".join(o), h

    b1, h1 = block(y0 + 30, "can", spec["can"])
    b2, h2 = block(y0 + 30 + h1 + 14, "not", spec["not"])
    out += [b1, b2]
    return "".join(out), 30 + h1 + 14 + h2


def _step_desc(spec: dict) -> str:
    if "flow" in spec:
        labs = [lab for _g, lab in spec["flow"]]
        what = ", then ".join([labs[0]] + [l[0].lower() + l[1:] for l in labs[1:]]) + "."
    else:
        (_g, lab), opts = spec["branch"]
        what = f"{lab} can lead to: " + ", ".join(
            f"{o[0]} ({o[1][0].lower() + o[1][1:]})" if isinstance(o, tuple) else o for o in opts) + "."
    who = spec.get("who_head", "Who is involved") + ": " + ", ".join(spec["who"]) + "."
    can = "AI can: " + "; ".join(spec["can"]) + "."
    nott = "AI must not: " + "; ".join(spec["not"]) + "."
    return f"What happens: {what} {who} {can} {nott}"


def step_figure(step_id: str) -> str:
    spec = STEP_SPECS[step_id]
    title = f"{spec['title']}: what happens, who is involved, and what AI can and must not do"
    desc = _step_desc(spec)
    # wide: two panels side by side
    p = f"{step_id}-w"
    W1, gap = 452, 44
    a, ha = panel_what(spec, 4, 6, W1, p)
    b, hb = panel_ai(spec, 4 + W1 + gap, 6, W1 - 8, p)
    Hw = int(max(ha, hb) + 20)
    Ww = int(4 + W1 + gap + W1 - 8 + 10)
    divider = (f'<line x1="{4 + W1 + gap / 2}" y1="10" x2="{4 + W1 + gap / 2}" y2="{Hw - 10}" '
               f'stroke="{INK}" stroke-width="1" opacity="0.35"/>')
    wide = svg_open(p, Ww, Hw, title, desc, "dg-wide") + a + divider + b + "</svg>"
    # tall: stacked
    p = f"{step_id}-t"
    Wt = 360
    a, ha = panel_what(spec, 4, 6, Wt - 8, p)
    b, hb = panel_ai(spec, 4, 6 + ha + 28, Wt - 14, p)
    Ht = int(6 + ha + 28 + hb + 18)
    tall = svg_open(p, Wt, Ht, title, desc, "dg-tall") + a + b + "</svg>"
    return f'<figure class="dg dg-step" id="dg-{e(step_id)}">' + wide + tall + "</figure>"


# --------------------------------------------------------------- Sid timeline

# Short labels keyed by the exact date string in data/cases/sijbrandij.json.
# A date missing from this map fails the build, so the drawing cannot drift
# from the verified case data.
NOT_STATED = "Then the next phase; his sources give no reason for this step."
_MON = {m: m[:3] for m in ["January", "February", "March", "April", "May", "June", "July",
                            "August", "September", "October", "November", "December"]}


def sid_case() -> dict:
    return json.loads((ROOT / "data" / "cases" / "sijbrandij.json").read_text(encoding="utf-8"))


def when_bounds(when: str) -> tuple[str, str]:
    """'Jan–Feb 2023' -> ('Jan 2023', 'Feb 2023'); 'From Oct 2023' -> ('Oct 2023', 'Oct 2023')."""
    w = when.replace("From ", "").strip()
    parts = [x.strip() for x in w.replace(" – ", "–").split("–")]
    start, end = parts[0], parts[-1]
    if not any(ch.isdigit() for ch in start):
        start = f"{start} {end.split()[-1]}"
    return start, end


def phase_span(ph: dict) -> str:
    s = when_bounds(ph["actions"][0]["when"])[0]
    e_ = when_bounds(ph["actions"][-1]["when"])[1]
    if s == e_:
        return s
    if s.split()[-1] == e_.split()[-1] and len(s.split()) == 2 and len(e_.split()) == 2:
        return f"{s.split()[0]} – {e_[0].lower() + e_[1:]}"
    return f"{s} – {e_}"


def sid_phases() -> tuple[list[dict], list[dict]]:
    d = sid_case()
    phases, links = d["phases"], d["phase_links"]
    src = d["phase_sources"]
    for ph in phases:
        for a in ph["actions"]:
            if a["url"] not in src:
                raise SystemExit(f"Sid phase action {a['what']!r} has a URL not in phase_sources")
            if not a.get("evidence") and not a.get("quote"):
                raise SystemExit(f"Sid phase action {a['what']!r} has no evidence rows or quote")
    for ln in links:
        if ln.get("cause") and not all(s.get("quote") and s.get("url") in src for s in ln.get("sources", [])):
            raise SystemExit(f"Sid link {ln['from']}->{ln['to']} states a cause without a sourced quote")
        if ln.get("cause") and not ln.get("sources"):
            raise SystemExit(f"Sid link {ln['from']}->{ln['to']} states a cause without sources")
    return phases, links


SID_TITLE = "Sid Sijbrandij’s published story in five phases, and what led from one to the next"


def _sid_desc(phases, links) -> str:
    out = []
    for i, ph in enumerate(phases):
        acts = "; ".join(f"{a['when']}: {a['what']}" for a in ph["actions"])
        out.append(f"Phase {i + 1}, {ph['title'].strip('“”')}, {phase_span(ph)}. {acts}.")
        if i < len(links):
            ln = links[i]
            out.append(("Why the next phase: " + ln["cause"]) if ln.get("cause") else NOT_STATED)
    out.append("One person’s story, not evidence that a treatment works.")
    return " ".join(out)


def _sid_svg(p: str, wide: bool) -> str:
    phases, links = sid_phases()
    W = 860 if wide else 400
    body = []
    y = 8
    for i, ph in enumerate(phases):
        rows = ph["actions"]
        if wide:
            lw, rx = 214, 228
            dcol = 132
            tchars = int((W - rx - dcol - 30) / 7.6)
            row_lines = [wrap(a["what"], tchars) for a in rows]
            rows_h = sum(max(1, len(l)) * 21 + 10 for l in row_lines) + 26
            tlines = wrap(ph["title"], 15)
            left_h = 30 + 24 + 14 + len(tlines) * 28 + 18
            h = max(rows_h, left_h)
            body.append(plate(0, y, lw, h, p, dx=5, dy=5, opacity=0.5))
            body.append(f'<rect x="0" y="{y}" width="{lw}" height="{h}" fill="{INK}"/>')
            body.append(text(18, y + 28, f"Phase {i + 1}", size=13, weight=700, fill=PAPER, bg=INK,
                             spacing="1.6", upper=True))
            body.append(text(18, y + 52, phase_span(ph), size=15.5, weight=600, fill=PAPER, bg=INK))
            body.append(lines_text(18, y + 88, tlines, lh=28, size=26, weight=700, fill=PAPER,
                                   bg=INK, family=HEAD))
            body.append(f'<rect x="{rx}" y="{y}" width="{W - rx - 2}" height="{h}" fill="{WHITE}" '
                        f'stroke="{INK}" stroke-width="2"/>')
            ry = y + 30
            for a, ls in zip(rows, row_lines):
                body.append(text(rx + 16, ry, a["when"], size=14.5, weight=700, fill=PINK, bg=WHITE))
                body.append(lines_text(rx + 16 + dcol, ry, ls, lh=21, size=16, weight=600 if "evidence" in a else 400,
                                       fill=DEEP if "evidence" in a else INK, bg=WHITE))
                ry += max(1, len(ls)) * 21 + 10
            cx = lw / 2
        else:
            tlines = wrap(ph["title"], 24)
            band = 26 + 22 + len(tlines) * 26 + 12
            tchars = 36
            row_lines = [wrap(a["what"], tchars) for a in rows]
            rows_h = sum(20 + len(l) * 20 + 10 for l in row_lines) + 18
            h = band + rows_h
            body.append(plate(8, y, W - 16, band, p, dx=4, dy=4, opacity=0.5))
            body.append(f'<rect x="8" y="{y}" width="{W - 16}" height="{band}" fill="{INK}"/>')
            body.append(text(24, y + 26, f"Phase {i + 1} · {phase_span(ph)}", size=14, weight=700,
                             fill=PAPER, bg=INK))
            body.append(lines_text(24, y + 54, tlines, lh=26, size=24, weight=700, fill=PAPER, bg=INK,
                                   family=HEAD))
            body.append(f'<rect x="8" y="{y + band}" width="{W - 16}" height="{rows_h}" fill="{WHITE}" '
                        f'stroke="{INK}" stroke-width="2"/>')
            ry = y + band + 26
            for a, ls in zip(rows, row_lines):
                body.append(text(24, ry, a["when"], size=14, weight=700, fill=PINK, bg=WHITE))
                body.append(lines_text(24, ry + 20, ls, lh=20, size=15.5, weight=600 if "evidence" in a else 400,
                                       fill=DEEP if "evidence" in a else INK, bg=WHITE))
                ry += 20 + len(ls) * 20 + 10
            cx = 40
        y += h
        if i < len(links):
            ln = links[i]
            bx = (cx + 40) if wide else 64
            bw = (W - bx - 8) if not wide else 560
            if ln.get("cause"):
                lines = wrap(ln["cause"], int((bw - 90) / 8.0))
                bh = 22 + len(lines) * 21
                gap = bh + 36
                by = y + 18
                body.append(line(cx, y + 6, cx, y + gap - 8, p))
                body.append(plate(bx, by, bw, bh, p, dx=4, dy=4, opacity=0.45))
                body.append(f'<rect x="{bx:.1f}" y="{by}" width="{bw}" height="{bh}" fill="{PINK}"/>')
                body.append(text(bx + 14, by + 26, "WHY", size=13, weight=700, fill=WHITE, bg=PINK,
                                 spacing="1.6"))
                body.append(lines_text(bx + 66, by + 26, lines, lh=21, size=15.5, weight=600,
                                       fill=WHITE, bg=PINK))
            else:
                # plain next-phase arrow: his sources give no reason for this link
                gap = 52
                body.append(line(cx, y + 6, cx, y + gap - 8, p))
            y += gap
    H = int(y + 12)
    cls = "dg-wide" if wide else "dg-tall"
    return svg_open(p, W, H, SID_TITLE, _sid_desc(phases, links), cls) + "".join(body) + "</svg>"


def sid_figure() -> str:
    return (
        '<figure class="dg dg-sid" id="sid-timeline">' + _sid_svg("sid-w", True) + _sid_svg("sid-t", False)
        + "<figcaption>One person’s story, not evidence that a treatment works. Dates and actions "
        "come from osteosarc.com records and his own posts; plain-weight lines are his own words. "
        "A reason is shown only where his sources give one."
        "</figcaption></figure>"
    )
