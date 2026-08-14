#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_demo_gif.py — render assets/demo.gif (terminal-style animation).

Content is REAL output from verify_refs.py captured 2026-08-15: 8 references,
3 of them deliberately planted fabrications (fake DOI / dead URL / no URL),
all 3 caught. Regenerate after forking: python tools/make_demo_gif.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 800, 450
BG, BAR = (13, 17, 23), (22, 27, 34)
FG, DIM = (230, 237, 243), (139, 148, 158)
GREEN, YELLOW, RED, BLUE = (63, 185, 80), (210, 153, 34), (248, 81, 73), (88, 166, 255)
FS, LH, PAD_X, PAD_Y = 15, 22, 18, 42
MAX_LINES = (H - PAD_Y - 12) // LH
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

font = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", FS)
font_b = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", FS)
font_med = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 16)
font_big = ImageFont.truetype(r"C:\Windows\Fonts\consolab.ttf", 40)
font_tag = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", 18)


def seg_width(segs):
    w = 0
    for t, _, b in segs:
        w += ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(t, font=font_b if b else font)
    return w


def render(lines=None, cursor_on=False, end_card=False):
    lines = lines or []
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    if end_card:
        d.text((W // 2, 150), "CITE HOLMES", font=font_big, fill=FG, anchor="mm")
        d.text((W // 2, 205), "deep research that interrogates its own sources",
               font=font_tag, fill=DIM, anchor="mm")
        d.text((W // 2, 245), "8 refs in -> 3 planted fakes caught -> 0 in report",
               font=font_tag, fill=GREEN, anchor="mm")
        d.text((W // 2, 300), "zero hallucinated citations", font=font_tag, fill=RED, anchor="mm")
        d.text((W // 2, 355), "github.com/docsor1212/cite-holmes", font=font_med,
               fill=BLUE, anchor="mm")
        return img
    d.rectangle([0, 0, W, 28], fill=BAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 16 + i * 20
        d.ellipse([cx, 9, cx + 11, 20], fill=c)
    d.text((W // 2, 14), "cite-holmes — research session", font=font_med, fill=DIM, anchor="mm")
    visible = lines[-MAX_LINES:]
    y = PAD_Y
    for segs in visible:
        x = PAD_X
        for t, col, b in segs:
            f = font_b if b else font
            d.text((x, y), t, font=f, fill=col)
            x += d.textlength(t, font=f)
        y += LH
    if cursor_on and visible:
        cy = PAD_Y + (len(visible) - 1) * LH
        d.rectangle([PAD_X + seg_width(visible[-1]) + 2, cy, PAD_X + seg_width(visible[-1]) + 10,
                     cy + LH - 5], fill=FG)
    return img


frames = []


def hold(state, ms, blink=False):
    frames.append((render(state, cursor_on=not blink), ms))
    if blink:
        frames.append((render(state, cursor_on=True), 250))
        frames.append((render(state, cursor_on=False), 250))


def out(state, segs, ms=230):
    frames.append((render(state + [segs]), ms))
    state.append(segs)


def typed(state, segs, ms=70, step=2):
    total = sum(len(t) for t, _, _ in segs)
    for k in range(step, total + 1, step):
        left, partial = k, []
        for t, col, b in segs:
            take = max(0, min(len(t), left))
            partial.append((t[:take], col, b))
            left -= take
            if left <= 0:
                break
        frames.append((render(state + [partial], cursor_on=True), ms))
    state.append(segs)


def cut(s, n=70):
    return s if len(s) <= n else s[:n - 3] + "..."


state = []
hold(state, 900, blink=True)

typed(state, [("$ ", GREEN, False), ("claude", FG, False)])
out(state, [("> ", BLUE, False), ("deep research: what changed in the agent-skills"
           " ecosystem this year?", BLUE, False)], ms=500)

for t in ["* plan: 3 sub-questions | budget 12 searches | EN+CN",
          "* searching 1..12 ... done", "* drafting report ... 8 references collected"]:
    out(state, [(t, DIM, False)], ms=170)

out(state, [("# Agent Skills in 2026", FG, True)], ms=170)
for t in ["- spec opened as an open standard [1][2]",
          "- 60k+ public skills; hallucinated citations",
          "  became a systemic crisis [3]", "8 references attached"]:
    out(state, [(t, FG, False)], ms=170)
out(state, [("", DIM, False)], ms=250)

typed(state, [("$ ", GREEN, False),
              ("python scripts/verify_refs.py --refs research_refs.json", FG, False)])
out(state, [("", DIM, False)], ms=120)

verdicts = [
    ("OK", GREEN, False, "Equipping agents for the real world with..."),
    ("PARTIAL", YELLOW, False, "awesome-claude-skills: curated list"),
    ("OK", GREEN, False, "Hallucinated citations are polluting the..."),
    ("PARTIAL", YELLOW, False, "Skill registry and trending tracker"),
    ("PARTIAL", YELLOW, False, "Best Claude Code Skills to Try in 2026"),
    ("BUSTED", RED, True, "A longitudinal study of citation... [PLANTED FAKE DOI]"),
    ("BUSTED", RED, True, "Agent Skills adoption survey: 60k... [PLANTED DEAD URL]"),
    ("BUSTED", RED, True, "Meta-analysis of retrieval grounding... [PLANTED NO-URL]"),
]
for i, (v, col, bold, title) in enumerate(verdicts, 1):
    ms = 420 if v == "BUSTED" else 230
    out(state, [(f"[{i}/8] ", DIM, False), (f"{v:<8}", col, bold),
                (cut(title, 68), col if v == "BUSTED" else FG, v == "BUSTED")], ms=ms)

out(state, [("", DIM, False)], ms=200)
out(state, [("3 of 8 citations FAILED verification -> excluded from report", RED, True)], ms=550)
out(state, [("  #6 fake DOI | #7 dead URL | #8 no URL/DOI", RED, False)], ms=450)
out(state, [("5 verified sources remain. report regenerated.", GREEN, True)], ms=550)

frames.append((render(state), 600))
frames.append((render(end_card=True), 3200))

out_path = os.path.join(ROOT, "assets", "demo.gif")
imgs, durs = [f for f, _ in frames], [d for _, d in frames]
imgs[0].save(out_path, save_all=True, append_images=imgs[1:], duration=durs,
             loop=0, optimize=True)
print(f"frames={len(imgs)} duration={sum(durs)/1000:.1f}s size="
      f"{os.path.getsize(out_path)/1024/1024:.2f}MB -> {out_path}")
