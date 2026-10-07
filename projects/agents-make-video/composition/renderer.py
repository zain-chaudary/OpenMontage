"""Bespoke atelier compositor — OpenMontage animated-explainer.

Renders 1920x1080 @ 30fps frames to stdout (rawvideo) for FFmpeg to encode.
Style playbook: premium-minimalist (off-white field, hairline rules,
single cobalt accent, restrained ease-out motion).

Each scene is a pure function of local time, so cross-fades blend two scenes.

Note on runtime: OpenMontage's bundled browser runtimes (Remotion, HyperFrames)
require a Chrome/Chromium build. In a sandbox where that runtime cannot be
installed, `video_compose` supports the `ffmpeg` runtime; this kit is the
"bespoke atelier" authoring layer that feeds it. On a normal workstation the
same pipeline can run Remotion instead — see FULL_POWER.md.
"""
import math, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "images"
FDIR = ROOT / "assets" / "fonts" / "ttf"
W, H, FPS = 1920, 1080, 30

# ---- playbook: premium-minimalist ----
BG     = (249, 250, 251)
TEXT   = (17, 24, 39)
MUTED  = (107, 114, 128)
ACCENT = (29, 78, 216)
HAIR   = (209, 213, 219)
CARD   = (255, 255, 255)
GOOD   = (21, 128, 61)

# ---- film-level progress (the rail must reflect the whole 62s, not each scene) ----
import json as _json
try:
    _TL = _json.loads((Path(__file__).resolve().parent / "timeline.json").read_text())
    SECTION_START = _TL["section_start_times"]
    TOTAL_S = _TL["total_seconds"]
except Exception:                      # renderer still usable standalone
    SECTION_START, TOTAL_S = [0.0] * 8, 62.0

def rail(base, idx, t):
    """Progress rail for scene `idx` at local time `t` -> global film fraction."""
    base_start = SECTION_START[idx] if idx < len(SECTION_START) else 0.0
    progress_rail(base, (base_start + t) / TOTAL_S)

def font(weight, size):
    return ImageFont.truetype(str(FDIR / f"inter-{weight}.ttf"), size)

class Ctx:
    """Caches fonts and static layers; one instance shared across scenes."""
    def __init__(self):
        self._f = {}
        self._lay = {}

    def f(self, w, s):
        k = (w, s)
        if k not in self._f:
            self._f[k] = font(w, s)
        return self._f[k]

    def plate(self, name, max_zoom=1.14, size=(W, H)):
        k = ("plate", name, max_zoom, size)
        if k not in self._lay:
            im = Image.open(IMG / name).convert("RGB")
            tw, th = size
            ar_t, ar_s = tw / th, im.width / im.height
            if ar_s > ar_t:
                nw = int(im.height * ar_t)
                im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
            else:
                nh = int(im.width / ar_t)
                im = im.crop((0, (im.height - nh) // 2, im.width, (im.height - nh) // 2 + nh))
            self._lay[k] = im.resize((int(tw * max_zoom), int(th * max_zoom)), Image.LANCZOS)
        return self._lay[k]

    def layer(self, key, builder):
        """key MUST include any value that changes the pixels."""
        if key not in self._lay:
            self._lay[key] = builder()
        return self._lay[key]

def sample(plate, zw, zh, zoom, cx=0.5, cy=0.5):
    pw, ph = plate.size
    rw, rh = pw / zoom, ph / zoom
    x = min(max(cx * pw - rw / 2, 0), pw - rw)
    y = min(max(cy * ph - rh / 2, 0), ph - rh)
    return plate.crop((int(x), int(y), int(x + rw), int(y + rh))).resize((zw, zh), Image.LANCZOS)

def ease(t):
    t = max(0.0, min(1.0, t)); return 1 - (1 - t) ** 3

def ease_io(t):
    t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

def text_layer(txt, fnt, fill, tracking=0, line_gap=0.32, max_w=None, align="left"):
    """Render a text block at 2x then downsample for crisp type."""
    S = 2
    fo = ImageFont.truetype(fnt.path, fnt.size * S)
    lines = txt.split("\n")
    if max_w:
        out = []
        for ln in lines:
            words, cur = ln.split(" "), ""
            for w_ in words:
                trial = (cur + " " + w_).strip()
                if fo.getlength(trial) > max_w * S and cur:
                    out.append(cur); cur = w_
                else:
                    cur = trial
            if cur:
                out.append(cur)
        lines = out
    asc, desc = fo.getmetrics()
    lh = int((asc + desc) * (1 + line_gap))
    wid = max(int(fo.getlength(l) + tracking * S * (len(l) - 1)) for l in lines) if lines else 1
    img = Image.new("RGBA", (max(wid, 1) + 8 * S, lh * len(lines) + 8 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        x = 4 * S
        if align == "center":
            x = (img.width - int(fo.getlength(ln))) / 2
        for ci, ch in enumerate(ln):
            nxt = ln[ci + 1] if ci + 1 < len(ln) else ""
            d.text((x, 4 * S + i * lh), ch, font=fo, fill=fill)
            x += fo.getlength(ch) if (nxt and nxt in ".,!?;:") else fo.getlength(ch) + tracking * S
    return img.resize((max(img.width // S, 1), max(img.height // S, 1)), Image.LANCZOS)

def pill(d, xy, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)

def paste(base, layer, xy, alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1.0:
        l = layer.copy()
        l.putalpha(l.getchannel("A").point(lambda v: int(v * alpha)))
    else:
        l = layer
    base.alpha_composite(l, (int(xy[0]), int(xy[1])))

# ---------------------------------------------------------------- primitives
def eyebrow(base, c, label, t_appear=0.0, t=0.0):
    a = ease((t - t_appear) / 0.5)
    lay = c.layer(("eyebrow", label), lambda: text_layer(label.upper(), c.f(600, 21), MUTED, tracking=3.4))
    paste(base, lay, (120, 84), a)
    if a > 0:
        d = ImageDraw.Draw(base)
        d.line((120, 132, 120 + int((W - 240) * min(1.0, a)), 132), fill=HAIR, width=2)

def headline(base, c, txt, y=196, size=68, weight=800, t=0.0, t_appear=0.0, max_w=None, alpha_mult=1.0):
    a = ease((t - t_appear) / 0.55) * alpha_mult
    lay = c.layer(("hl", txt, size, weight, max_w), lambda: text_layer(txt, c.f(weight, size), TEXT, tracking=-0.9, max_w=max_w))
    dy = int((1 - ease((t - t_appear) / 0.55)) * 14)
    paste(base, lay, (120, y + dy), a)
    return lay.height

def progress_rail(base, frac):
    d = ImageDraw.Draw(base)
    d.line((120, 56, W - 120, 56), fill=(229, 231, 235), width=3)
    if frac > 0:
        d.line((120, 56, 120 + int((W - 240) * min(1.0, frac)), 56), fill=ACCENT, width=3)

def caption(base, c, txt, t, t0, t1, dark=False):
    if not txt or t < t0 - 0.18 or t > t1 + 0.18:
        return
    if t < t0:
        a = (t - (t0 - 0.18)) / 0.18
    elif t > t1:
        a = max(0.0, (t1 + 0.18 - t) / 0.18)
    else:
        a = 1.0
    lay = c.layer(("cap", txt, dark), lambda: text_layer(txt, c.f(600, 34), (255, 255, 255) if dark else TEXT))
    pad_x, pad_y = 28, 16
    bw, bh = lay.width + pad_x * 2, lay.height + pad_y * 2
    card = Image.new("RGBA", (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
    pill(d, (0, 0, bw - 1, bh - 1), 10, fill=(17, 24, 39, 190) if dark else (255, 255, 255, 205),
         outline=None if dark else HAIR, width=1)
    card.alpha_composite(lay, (pad_x, pad_y))
    paste(base, card, ((W - bw) // 2, H - 96 - bh), a)

def count_up(v0, v1, t, dur):
    return v0 + (v1 - v0) * ease(t / dur)

def photo_card(c, name, pw, ph, zoom=1.06):
    """Rounded, hairline-bordered photographic inset."""
    im = sample(c.plate(name, 1.12), pw, ph, zoom)
    card = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=8, fill=255)
    card.paste(im, (0, 0), mask)
    ImageDraw.Draw(card).rounded_rectangle((0, 0, pw - 1, ph - 1), radius=8, outline=HAIR, width=2)
    return card

# ---------------------------------------------------------------- scenes
def scene1(c, t):
    """Cold open: prompt chip types, then hard cut to full-bleed plate."""
    PROMPT = "make a video about how agents make videos"
    cut = 2.30
    if t < cut:
        base = Image.new("RGBA", (W, H), BG + (255,))
        n = min(len(PROMPT), max(0, int((t - 0.35) / 0.045)))
        shown = PROMPT[:n]
        lay = c.layer(("promptchip", shown), lambda: text_layer("> " + shown + "|", c.f(500, 34), TEXT))
        pad_x, pad_y = 40, 26
        bw, bh = lay.width + pad_x * 2, lay.height + pad_y * 2
        card = Image.new("RGBA", (bw, bh), (0, 0, 0, 0)); d = ImageDraw.Draw(card)
        pill(d, (0, 0, bw - 1, bh - 1), 14, fill=(255, 255, 255, 255), outline=HAIR, width=2)
        card.alpha_composite(lay, (pad_x, pad_y))
        base.alpha_composite(card, ((W - bw) // 2, (H - bh) // 2))
        lab = c.layer("s1label", lambda: text_layer("THE PITCH", c.f(600, 20), MUTED, tracking=4.0))
        paste(base, lab, ((W - lab.width) // 2, (H - bh) // 2 - 72), 1.0)
    else:
        p = sample(c.plate("img-07-review-room.jpg", 1.12), W, H, 1.0 + 0.10 * ease((t - cut) / 3.6))
        base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); base.paste(p, (0, 0)); base = base.convert("RGBA")
        scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(scrim)
        for i in range(300):
            sd.line((0, H - i, W, H - i), fill=(6, 10, 20, int(150 * (1 - i / 300) ** 1.6)))
        base.alpha_composite(scrim)
    return base

def scene2(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "01  The inversion", 0.0, t)
    headline(base, c, "Generation is the\nsmallest part.", 196, 68, 800, t, 0.1, max_w=760)
    sub = c.layer("s2sub", lambda: text_layer("Most of the work happens before\na single frame exists.", c.f(400, 30), MUTED, line_gap=0.42))
    paste(base, sub, (120, 436), ease((t - 0.5) / 0.6))
    a = ease((t - 0.25) / 0.7); pw, ph = 760, 510
    paste(base, photo_card(c, "img-02-cards.jpg", pw, ph, 1.0 + 0.06 * ease(t / 8.0)),
          (W - 120 - pw + int((1 - a) * 26), 180), a)
    ty = 676; d = ImageDraw.Draw(base)
    if t > 1.2:
        v70 = count_up(0, 70, t - 1.2, 1.1); v30 = count_up(0, 30, t - 1.2, 1.1)
        barw = W - 240; split = int(barw * (v70 / 100))
        d.rounded_rectangle((120, ty, 120 + split, ty + 58), radius=6, fill=ACCENT)
        d.rounded_rectangle((120 + split + 6, ty, W - 120, ty + 58), radius=6, fill=(226, 232, 240))
        l1 = c.layer("s2l1", lambda: text_layer("PRE-PRODUCTION", c.f(600, 20), (255, 255, 255), tracking=2.6))
        l2 = c.layer("s2l2", lambda: text_layer("GENERATION", c.f(600, 20), MUTED, tracking=2.6))
        paste(base, l1, (146, ty + 18), ease((t - 1.4) / 0.5))
        paste(base, l2, (max(120 + split + 32, W - 120 - l2.width - 18), ty + 18), ease((t - 1.4) / 0.5))
        s70 = c.layer(("s2s70", int(round(v70))), lambda: text_layer(f"{int(round(v70))}%", c.f(800, 44), TEXT))
        s30 = c.layer(("s2s30", int(round(v30))), lambda: text_layer(f"{int(round(v30))}%", c.f(800, 44), MUTED))
        paste(base, s70, (120, ty + 74), ease((t - 1.4) / 0.5))
        paste(base, s30, (W - 120 - s30.width, ty + 74), ease((t - 1.4) / 0.5))
    rail(base, 1, t)
    return base

def scene3(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "02  Research", 0.0, t)
    headline(base, c, "Searches first,\nsources cited.", 196, 68, 800, t, 0.1, max_w=520)
    a = ease((t - 0.3) / 0.7)
    paste(base, photo_card(c, "img-03-research.jpg", 440, 300, 1.0 + 0.05 * ease(t / 8.0)),
          (120, 470 + int((1 - a) * 18)), a)
    d = ImageDraw.Draw(base); cx, cy = 790, 600
    node_a = ease((t - 0.35) / 0.5)
    if node_a > 0:
        d.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=ACCENT if node_a > .9 else (147, 178, 240))
        nt = c.layer("s3node", lambda: text_layer("topic", c.f(600, 24), TEXT))
        paste(base, nt, (cx - nt.width // 2, cy + 40), node_a)
    for i, (lab, yy) in enumerate([("forums", cy - 150), ("papers", cy), ("news", cy + 150)]):
        ta = ease((t - (1.0 + i * 0.35)) / 0.55)
        if ta <= 0:
            continue
        x1, x2 = cx + 30, cx + 230
        n = int(10 * min(1.0, ta * 1.6))
        pts = [(x1 + (x2 - x1) * k / n, cy + (yy - cy) * k / n) for k in range(1, n + 1)]
        if len(pts) > 1:
            d.line(pts, fill=HAIR, width=3)
        d.rounded_rectangle((x2, yy - 30, x2 + 330, yy + 30), radius=6, fill=CARD, outline=HAIR, width=2)
        l = c.layer(("s3t", lab), lambda: text_layer(lab, c.f(600, 28), TEXT))
        paste(base, l, (x2 + 28, yy - l.height // 2), ta)
    ca = ease((t - 2.3) / 0.6)
    if ca > 0:
        v = count_up(0, 8, t - 2.3, 0.9)
        sc = c.layer(("s3stat", int(round(v))), lambda: text_layer(f"{int(round(v))}", c.f(800, 96), ACCENT))
        sl = c.layer("s3statl", lambda: text_layer("cited sources in the brief", c.f(500, 24), MUTED))
        paste(base, sc, (120, 786), ca)
        paste(base, sl, (120 + sc.width + 22, 816), ca)
    rail(base, 2, t)
    return base

def scene4(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "03  Script + scene plan", 0.0, t)
    headline(base, c, "Words budgeted\nagainst seconds.", 196, 68, 800, t, 0.1, max_w=820)
    a = ease((t - 0.4) / 0.6); pw, ph = 620, 420
    paste(base, photo_card(c, "img-04-script.jpg", pw, ph, 1.0 + 0.05 * ease(t / 8.0)),
          (W - 120 - pw, 180 + int((1 - a) * 20)), a)
    d = ImageDraw.Draw(base); bx, by, bw, bh = 120, 470, 760, 26
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=13, fill=(226, 232, 240))
    fa = ease((t - 1.0) / 0.9)
    d.rounded_rectangle((bx, by, bx + int(bw * fa), by + bh), radius=13, fill=ACCENT)
    l1 = c.layer("s4l1", lambda: text_layer("146 words", c.f(700, 30), TEXT))
    l2 = c.layer("s4l2", lambda: text_layer("62 seconds", c.f(400, 26), MUTED))
    paste(base, l1, (120, 516), ease((t - 1.2) / 0.5))
    paste(base, l2, (120 + l1.width + 26, 522), ease((t - 1.2) / 0.5))
    n, gapx, ty = 8, 14, 700
    tw = (W - 240 - gapx * (n - 1)) // n
    for i in range(n):
        ba = ease((t - (1.7 + i * 0.10)) / 0.45)
        if ba <= 0:
            continue
        x = 120 + i * (tw + gapx); y = ty + int((1 - ba) * 22)
        d.rounded_rectangle((x, y, x + tw, y + int(120 * min(1, ba))), radius=6,
                            fill=ACCENT if i in (0, 7) else (241, 245, 249), outline=HAIR, width=2)
    lab = c.layer("s4sb", lambda: text_layer("scene plan", c.f(500, 24), MUTED, tracking=2.4))
    paste(base, lab, (120, ty + 150), ease((t - 2.6) / 0.5))
    rail(base, 3, t)
    return base

def scene5(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "04  Assets", 0.0, t)
    headline(base, c, "Routed, then\nwritten down.", 196, 68, 800, t, 0.1, max_w=760)
    d = ImageDraw.Draw(base)
    cols = [("NARRATION", ["narration", "mix"]), ("VISUALS", ["images", "graphics"]), ("MUSIC", ["score", "ducking"])]
    x0, y0, cw, ch, gapx = 120, 430, 430, 180, 30
    for i, (title, chips) in enumerate(cols):
        ca = ease((t - (0.5 + i * 0.45)) / 0.55)
        if ca <= 0:
            continue
        x = x0 + i * (cw + gapx); y = y0 + int((1 - ca) * 24)
        dark = ca > 0.85
        d.rounded_rectangle((x, y, x + cw, y + ch), radius=10, fill=(17, 24, 39, 255) if dark else (241, 245, 249),
                            outline=HAIR, width=2)
        tl = c.layer(("s5t", title, dark), lambda: text_layer(title, c.f(600, 22), (255, 255, 255) if dark else MUTED, tracking=2.8))
        paste(base, tl, (x + 28, y + 24), ca)
        cxoff = x + 28
        for chp in chips:
            cchip = c.layer(("s5c", chp, dark), lambda: text_layer(chp, c.f(500, 24), (255, 255, 255) if dark else TEXT))
            cwid = cchip.width + 40
            if cxoff + cwid > x + cw - 28:
                break
            d.rounded_rectangle((cxoff, y + 78, cxoff + cwid, y + 122), radius=22,
                                fill=None if dark else CARD, outline=(120, 130, 150) if dark else HAIR, width=2)
            paste(base, cchip, (cxoff + 20, y + 88), ca)
            cxoff += cwid + 12
    ra = ease((t - 2.1) / 0.7)
    if ra > 0:
        rx, ry, rw = W - 120 - 260, 420, 260
        d.rounded_rectangle((rx, ry, rx + rw, ry + 206), radius=10, fill=CARD, outline=HAIR, width=2)
        rl = c.layer("s5r", lambda: text_layer("DECISION LOG", c.f(600, 20), MUTED, tracking=2.8))
        paste(base, rl, (rx + 26, ry + 22), ra)
        for i, e in enumerate(["provider", "runtime", "voice", "captions"]):
            ea = ease((t - (2.4 + i * 0.30)) / 0.4)
            if ea <= 0:
                continue
            d.line((rx + 26, ry + 68 + i * 34, rx + 26 + int(46 * ea), ry + 68 + i * 34), fill=HAIR, width=2)
            el = c.layer(("s5e", e), lambda: text_layer(e, c.f(500, 24), TEXT))
            paste(base, el, (rx + 46, ry + 54 + i * 34), ea)
    rail(base, 4, t)
    return base

def scene6(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "05  Edit + render", 0.0, t)
    headline(base, c, "And only then,\nthe render.", 196, 68, 800, t, 0.1, max_w=700)
    a = ease((t - 0.35) / 0.7); pw, ph = 560, 340
    paste(base, photo_card(c, "img-06-edit-suite.jpg", pw, ph, 1.0 + 0.05 * ease(t / 8.0)),
          (W - 120 - pw, 180 + int((1 - a) * 20)), a)
    d = ImageDraw.Draw(base); tx, ty, tw, th = 120, 486, W - 240, 86
    d.rounded_rectangle((tx, ty, tx + tw, ty + th), radius=8, fill=(241, 245, 249), outline=HAIR, width=2)
    segs = [(0.00, 0.16, ACCENT), (0.17, 0.19, (203, 213, 225)), (0.21, 0.38, ACCENT), (0.39, 0.41, (203, 213, 225)),
            (0.43, 0.62, ACCENT), (0.63, 0.65, (203, 213, 225)), (0.67, 0.84, ACCENT), (0.85, 0.87, (203, 213, 225)),
            (0.89, 1.0, ACCENT)]
    rev = ease((t - 0.7) / 1.9)
    for s, e, col in segs:
        if s > rev:
            continue
        e2 = min(e, rev)
        d.rounded_rectangle((tx + 16 + s * (tw - 32), ty + 18, tx + 16 + e2 * (tw - 32), ty + th - 18), radius=4, fill=col)
    if t > 0.7:
        px = tx + 16 + rev * (tw - 32)
        d.line((px, ty + 8, px, ty + th - 8), fill=(17, 24, 39), width=3)
    if t > 2.6:
        pa = ease((t - 2.6) / 1.5); py = ty + th + 46
        d.rounded_rectangle((tx, py, tx + tw, py + 34), radius=17, fill=(226, 232, 240))
        d.rounded_rectangle((tx, py, tx + int(tw * pa), py + 34), radius=17, fill=ACCENT)
        fl = c.layer("s6f", lambda: text_layer("final.mp4", c.f(600, 26), TEXT))
        la = c.layer("s6l", lambda: text_layer("render", c.f(600, 22), MUTED, tracking=2.6))
        paste(base, la, (tx, py + 52), ease((t - 2.8) / 0.5))
        paste(base, fl, (tx + tw - fl.width, py + 48), ease((t - 3.1) / 0.6))
    rail(base, 5, t)
    return base

def scene7(c, t):
    base = Image.new("RGBA", (W, H), BG + (255,))
    eyebrow(base, c, "06  Review", 0.0, t)
    headline(base, c, "The step\nnobody sees.", 196, 68, 800, t, 0.1, max_w=560)
    a = ease((t - 0.35) / 0.7)
    paste(base, photo_card(c, "img-01-studio.jpg", 440, 300, 1.0 + 0.05 * ease(t / 7.0)),
          (120, 470 + int((1 - a) * 18)), a)
    d = ImageDraw.Draw(base); cx, cy, cw, ch = 640, 286, 1130, 560
    ca = ease((t - 0.4) / 0.7)
    if ca > 0:
        d.rounded_rectangle((cx, cy, cx + cw, cy + ch), radius=12, fill=CARD, outline=HAIR, width=2)
        tl = c.layer("s7t", lambda: text_layer("SELF-REVIEW", c.f(700, 22), MUTED, tracking=3.0))
        paste(base, tl, (cx + 36, cy + 30), ca)
    checks = ["Duration within target", "Audio levels in range", "Frames sampled and inspected", "Delivery promise verified"]
    for i, lab in enumerate(checks):
        ia = ease((t - (1.0 + i * 0.55)) / 0.55)
        if ia <= 0:
            continue
        y = cy + 96 + i * 74
        d.rounded_rectangle((cx + 36, y, cx + 78, y + 42), radius=6,
                            fill=(220, 252, 231) if ia > 0.8 else (243, 244, 246), outline=HAIR, width=2)
        if ia > 0.8:
            d.line((cx + 47, y + 22, cx + 56, y + 32), fill=GOOD, width=4)
            d.line((cx + 56, y + 32, cx + 70, y + 12), fill=GOOD, width=4)
        l = c.layer(("s7c", lab), lambda: text_layer(lab, c.f(500, 30), TEXT))
        paste(base, l, (cx + 100, y + 4), ia)
    if t > 3.4:
        ga = ease((t - 3.4) / 0.6); y = cy + 96 + 4 * 74 + 14
        d.rounded_rectangle((cx + 36, y, cx + 78, y + 42), radius=6, fill=(254, 242, 242), outline=(252, 165, 165), width=2)
        gl = c.layer("s7f", lambda: text_layer("Regenerate — do not ship", c.f(500, 30), (200, 120, 120)))
        paste(base, gl, (cx + 100, y + 4), ga * 0.75)
    if t > 4.3:
        sa = ease((t - 4.3) / 0.45)
        st = c.layer("s7p", lambda: text_layer("PASS", c.f(800, 64), (22, 101, 52), tracking=4))
        pw2, ph2 = st.width + 64, st.height + 36
        stamp = Image.new("RGBA", (pw2, ph2), (0, 0, 0, 0)); sd = ImageDraw.Draw(stamp)
        sd.rounded_rectangle((2, 2, pw2 - 3, ph2 - 3), radius=10, outline=(22, 101, 52), width=5)
        stamp.alpha_composite(st, (32, 18))
        stamp = stamp.rotate(-7, resample=Image.BICUBIC, expand=True)
        sc = 1.06 - 0.06 * sa
        if sa > 0:
            stamp = stamp.resize((int(stamp.width * sc), int(stamp.height * sc)), Image.LANCZOS)
            paste(base, stamp, (cx + cw - 300, cy + ch - 190), min(1.0, sa * 1.4))
    rail(base, 6, t)
    return base

def scene8(c, t):
    p = sample(c.plate("img-08-closing.jpg", 1.12), W, H, 1.0 + 0.035 * ease(t / 5.5))
    base = Image.new("RGBA", (W, H), (0, 0, 0, 0)); base.paste(p, (0, 0)); base = base.convert("RGBA")
    scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(scrim)
    for i in range(H):
        sd.line((0, i, W, i), fill=(8, 10, 16, int(120 * (1 - i / H) ** 1.15) + int(70 * (i / H) ** 2.2)))
    base.alpha_composite(scrim)
    l1 = c.layer("s8a", lambda: text_layer("That's not generation.", c.f(800, 74), (255, 255, 255), tracking=0.0))
    l2 = c.layer("s8b", lambda: text_layer("That's production.", c.f(800, 74), (255, 255, 255), tracking=0.0))
    a1 = ease((t - 0.15) / 0.6); a2 = ease((t - 1.35) / 0.6)
    y = H // 2 - l1.height - 30
    paste(base, l1, ((W - l1.width) // 2, y), a1)
    paste(base, l2, ((W - l2.width) // 2, y + l1.height + 26), a2)
    if t > 2.3:
        a3 = ease((t - 2.3) / 0.7)
        wm = c.layer("s8w", lambda: text_layer("OPENMONTAGE", c.f(700, 30), (255, 255, 255), tracking=6.0))
        sb = c.layer("s8s", lambda: text_layer("12 pipelines  ·  one agent", c.f(500, 24), (226, 232, 240)))
        d = ImageDraw.Draw(base); wd = int(180 * min(1.0, a3))
        d.line((W // 2 - wd // 2, y + l1.height * 2 + 120, W // 2 + wd // 2, y + l1.height * 2 + 120),
               fill=(255, 255, 255, 120), width=2)
        paste(base, wm, ((W - wm.width) // 2, y + l1.height * 2 + 150), a3)
        paste(base, sb, ((W - sb.width) // 2, y + l1.height * 2 + 196), a3)
    return base

SCENES = [scene1, scene2, scene3, scene4, scene5, scene6, scene7, scene8]
