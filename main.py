#!/usr/bin/env python3
"""news-image-20261126 — one-image summary of Thursday 26 November 2026.

Visual revision (from scratch): richer, more detailed silhouette
illustrations, vertical panel gradients, soft panel shadows, layered
foreground/background, waves, smoke, stars and clouds, and a stronger
type hierarchy. All facts, numbers, headlines and stories are UNCHANGED.

Python 3.12+/3.13, standard library only, no network at runtime.
Writes entry.png (1024x1024, <= 1 MiB) to MAKEFUN_OUTPUT_DIR, falling
back to /output. Deterministic: two runs write byte-identical files.
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- font -----
# 5x7 bitmap font ('#' = on, '.' = off). Covers every character used by
# the fixed text below: A-Z, 0-9, space, . , - ' / %
FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "#####"),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    '-': (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    "'": ("..#..", "..#..", "..#..", ".....", ".....", ".....", "....."),
    '/': ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    '%': ("#...#", "#..#.", "...#.", "..#..", ".#...", "#..#.", "#...#"),
}


def text_width(s, scale):
    """Advance width of s at scale (6*scale per glyph, minus trailing gap)."""
    if not s:
        return 0
    return len(s) * 6 * scale - scale


def wrap_text(s, max_w, scale):
    """Greedy word wrap; returns list of lines, never wider than max_w."""
    words = s.split(" ")
    lines, cur = [], ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# -------------------------------------------------------------- canvas -----
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.clip = None
        self.buf = bytearray(w * h * 3)
        self.rect(0, 0, w, h, bg)

    def set_clip(self, x0, y0, x1, y1):
        """Restrict all later drawing to [x0, x1) x [y0, y1)."""
        self.clip = (x0, y0, x1, y1)

    def reset_clip(self):
        self.clip = None

    # -- primitives ---------------------------------------------------------
    def span(self, x, y, length, c):
        """Fill length pixels of row y starting at x (clipped)."""
        if y < 0 or y >= self.h or length <= 0:
            return
        x0 = max(0, x)
        x1 = min(self.w, x + length)
        if self.clip is not None:
            cx0, cy0, cx1, cy1 = self.clip
            if y < cy0 or y >= cy1:
                return
            x0 = max(x0, cx0)
            x1 = min(x1, cx1)
        if x1 <= x0:
            return
        r, g, b = c
        i = (y * self.w + x0) * 3
        n = (x1 - x0) * 3
        row = bytes((r, g, b)) * (x1 - x0)
        self.buf[i:i + n] = row

    def rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            self.span(x, yy, w, c)

    def blend_span(self, x, y, length, c, alpha):
        """Alpha-blend a row span (alpha 0..255) over what is there."""
        if y < 0 or y >= self.h or length <= 0:
            return
        x0 = max(0, x)
        x1 = min(self.w, x + length)
        if self.clip is not None:
            cx0, cy0, cx1, cy1 = self.clip
            if y < cy0 or y >= cy1:
                return
            x0 = max(x0, cx0)
            x1 = min(x1, cx1)
        if x1 <= x0:
            return
        r, g, b = c
        inv = 255 - alpha
        for xx in range(x0, x1):
            i = (y * self.w + xx) * 3
            self.buf[i] = (r * alpha + self.buf[i] * inv) // 255
            self.buf[i + 1] = (g * alpha + self.buf[i + 1] * inv) // 255
            self.buf[i + 2] = (b * alpha + self.buf[i + 2] * inv) // 255

    def blend_rect(self, x, y, w, h, c, alpha):
        for yy in range(max(0, y), min(self.h, y + h)):
            self.blend_span(x, yy, w, c, alpha)

    def blend_circle(self, cx, cy, r, c, alpha):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.blend_span(cx - dx, cy + dy, 2 * dx + 1, c, alpha)

    def blend_ellipse(self, cx, cy, rx, ry, c, alpha):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * math.sqrt(max(0.0, t)))
            self.blend_span(cx - dx, cy + dy, 2 * dx + 1, c, alpha)

    def vgrad(self, x, y, w, h, c1, c2):
        """Vertical gradient rect, top colour c1 to bottom colour c2."""
        for yy in range(max(0, y), min(self.h, y + h)):
            t = (yy - y) / float(max(1, h - 1))
            c = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            self.span(x, yy, w, c)

    def circle(self, cx, cy, r, c):
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(max(0, r * r - dy * dy)))
            self.span(cx - dx, cy + dy, 2 * dx + 1, c)

    def ellipse(self, cx, cy, rx, ry, c):
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            dx = int(rx * math.sqrt(max(0.0, t)))
            self.span(cx - dx, cy + dy, 2 * dx + 1, c)

    def poly(self, pts, c):
        """Scanline polygon fill."""
        ys = [p[1] for p in pts]
        ymin = max(0, int(min(ys)))
        ymax = min(self.h - 1, int(max(ys)))
        n = len(pts)
        for y in range(ymin, ymax + 1):
            xs = []
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / float(y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                x0 = max(0, int(xs[i]))
                x1 = min(self.w - 1, int(xs[i + 1]))
                if x1 >= x0:
                    self.span(x0, y, x1 - x0 + 1, c)

    def line(self, x0, y0, x1, y1, c, w=1):
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L * w / 2.0, dx / L * w / 2.0
        self.poly([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                   (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)], c)

    def outline(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    # -- text ---------------------------------------------------------------
    def text(self, s, x, y, scale, c, bold=False):
        """Draw text; bold double-strikes with a 1px horizontal offset."""
        cx = x
        passes = (0, 1) if bold else (0,)
        for off in passes:
            cx = x + off
            for ch in s:
                glyph = FONT.get(ch, FONT[' '])
                for gy, row in enumerate(glyph):
                    for gx, bit in enumerate(row):
                        if bit == '#':
                            self.rect(cx + gx * scale, y + gy * scale,
                                      scale, scale, c)
                cx += 6 * scale
        return cx - scale

    def block(self, lines, x, y, scale, c, lh=None, bold=False):
        if lh is None:
            lh = 7 * scale + max(2, scale)
        for ln in lines:
            self.text(ln, x, y, scale, c, bold=bold)
            y += lh
        return y


# ------------------------------------------------------- shared drawing -----
INK = (245, 241, 232)
BODY = (216, 210, 196)
MUTED = (150, 158, 172)
GOLD = (212, 175, 55)
RED = (206, 48, 58)
PAGE_BG = (13, 20, 32)
HEADER_BG = (10, 16, 28)


def lcg(seed):
    """Deterministic pseudo-random generator (fixed sequence)."""
    state = seed
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state


def stars(cv, x, y, w, h, n, seed, c, rmax=1):
    gen = lcg(seed)
    for _ in range(n):
        sx = x + next(gen) % w
        sy = y + next(gen) % h
        r = 1 + (next(gen) % rmax)
        cv.circle(sx, sy, r, c)


def flame(cv, x, base_y, w, h):
    """Layered teardrop flame, base centred at (x, base_y)."""
    layers = [((255, 122, 26), 1.00, 0),
              ((255, 176, 66), 0.68, 3),
              ((255, 226, 130), 0.38, 6)]
    for col, s, lift in layers:
        fw, fh = w * s, h * s
        by = base_y - lift
        cv.poly([(x - fw * 0.50, by), (x - fw * 0.44, by - fh * 0.30),
                 (x - fw * 0.20, by - fh * 0.62), (x, by - fh),
                 (x + fw * 0.20, by - fh * 0.62),
                 (x + fw * 0.44, by - fh * 0.30),
                 (x + fw * 0.50, by)], col)


def smoke(cv, x, y, n, seed):
    """Rising grey smoke puffs, drifting right."""
    gen = lcg(seed)
    for i in range(n):
        px = x + i * 9 + (next(gen) % 7) - 3
        py = y - i * 8
        r = 4 + (next(gen) % 4)
        cv.blend_ellipse(px, py, r + 3, r, (150, 146, 140), 64)


def wave_band(cv, x, y_base, w, amp, phase, c, depth):
    """One layered wave band: sine crest, solid down to y_base+depth."""
    pts = [(x, y_base + depth), (x + w, y_base + depth)]
    step = 14
    n = w // step + 1
    for i in range(n + 1):
        px = x + i * step
        py = y_base + int(amp * math.sin(px * 0.028 + phase))
        pts.append((px, py))
    cv.poly(pts, c)


def panel(cv, x, y, w, h, c1, c2, border):
    """Panel with soft drop shadow, vertical gradient and top highlight."""
    cv.blend_rect(x + 4, y + 5, w, h, (0, 0, 0), 110)
    cv.vgrad(x, y, w, h, c1, c2)
    cv.outline(x, y, w, h, border, 1)
    cv.blend_rect(x + 1, y + 1, w - 2, 1, (255, 255, 255), 26)


def kicker(cv, x, y, label, region, accent):
    cv.text(label, x, y, 2, accent, bold=True)
    rx = x + text_width(label, 2) + 14
    cv.text(region, rx, y, 2, MUTED)


def panel_text(cv, x, y, w, headline, body):
    """Headline (2 lines, scale 3, bold) + body (scale 2) inside a panel."""
    maxw = w - 36
    hl = wrap_text(headline, maxw, 3)
    y = cv.block(hl, x + 18, y + 36, 3, INK, lh=24, bold=True)
    bl = wrap_text(body, maxw, 2)
    cv.block(bl, x + 18, y + 6, 2, BODY, lh=16)
    return y


# ------------------------------------------------------------ illustrations --
def draw_ship(cv, x, y, w, h):
    """Panel 1: container ship at sea with cranes, sun and waves."""
    base = y + h - 6                      # waterline area
    # pale sun + glow, top right
    cv.blend_circle(x + w - 46, y + 30, 40, (255, 232, 170), 26)
    cv.circle(x + w - 46, y + 30, 22, (255, 240, 200))
    # soft clouds
    for cx, cy, rx in ((x + 60, y + 26, 34), (x + 150, y + 44, 26)):
        cv.blend_ellipse(cx, cy, rx, 9, (190, 200, 215), 42)
        cv.blend_ellipse(cx + 16, cy + 3, rx // 2, 6, (190, 200, 215), 42)
    # gantry cranes behind the ship (dark silhouette, slightly lifted)
    for crx in (x + 30, x + w - 130):
        cv.rect(crx, y + 62, 6, 96, (44, 60, 78))
        cv.rect(crx + 52, y + 62, 6, 96, (44, 60, 78))
        cv.rect(crx - 14, y + 62, 96, 6, (44, 60, 78))
        cv.line(crx + 3, y + 68, crx + 55, y + 128, (44, 60, 78), 3)
        cv.line(crx + 40, y + 68, crx + 40, y + 96, (44, 60, 78), 2)
        cv.rect(crx + 36, y + 96, 9, 7, (44, 60, 78))
    # stacked containers (taller stacks so the ship fills the panel)
    cont = [(150, 60, 45), (60, 110, 120), (170, 130, 60),
            (90, 95, 110), (120, 80, 90), (60, 90, 110)]
    stacks = [(x + 58, 4, 3), (x + 176, 3, 3), (x + 292, 3, 2)]
    ci = 0
    for sx, rows, cols in stacks:
        for r in range(rows):
            for cc in range(cols):
                col = cont[ci % len(cont)]
                ci += 1
                rx, ry = sx + cc * 38, base - 40 - r * 17
                cv.rect(rx - 1, ry - 1, 38, 17, (8, 14, 24))
                cv.rect(rx, ry, 36, 15, col)
                cv.rect(rx, ry, 36, 2, tuple(min(255, v + 26) for v in col))
                cv.rect(rx, ry + 7, 36, 1, (8, 14, 24))
    # funnel with gold band
    cv.rect(x + 268, base - 88, 22, 48, (140, 50, 40))
    cv.rect(x + 268, base - 88, 22, 6, GOLD)
    cv.rect(x + 268, base - 46, 22, 3, (20, 20, 26))
    # bridge tower with lit windows
    cv.rect(x + 296, base - 112, 30, 72, (15, 25, 40))
    for wy in range(base - 106, base - 46, 12):
        for wx in range(x + 300, x + 322, 9):
            cv.rect(wx, wy, 5, 6, (150, 178, 205))
    cv.rect(x + 296, base - 112, 30, 4, (30, 48, 68))
    # hull + waterline stripe + bow
    cv.poly([(x + 20, base - 40), (x + w - 16, base - 40),
             (x + w - 44, base - 4), (x + 44, base - 4)], (12, 20, 32))
    cv.rect(x + 22, base - 40, w - 46, 4, (150, 62, 44))
    cv.rect(x + 60, base - 28, 14, 8, (40, 60, 80))
    cv.rect(x + 90, base - 28, 14, 8, (40, 60, 80))
    # layered waves + crest highlight + reflections
    wave_band(cv, x, base + 2, w, 5, 0.0, (18, 55, 85), 22)
    wave_band(cv, x, base + 10, w, 5, 2.1, (25, 75, 110), 16)
    for i in range(0, w, 26):
        px = x + i
        py = base + 12 + int(4 * math.sin(px * 0.028 + 2.1))
        cv.rect(px, py, 14, 2, (70, 140, 185))
    for i, ry in enumerate((base + 6, base + 12, base + 18)):
        cv.blend_rect(x + 70 + i * 40, ry, 60 - i * 12, 2,
                      (160, 200, 230), 50)
    # birds
    for bx, by in ((x + w - 150, y + 58), (x + w - 120, y + 44),
                   (x + w - 96, y + 62)):
        cv.line(bx - 7, by, bx, by - 4, (210, 215, 225), 2)
        cv.line(bx, by - 4, bx + 7, by, (210, 215, 225), 2)


def draw_refinery(cv, bx, by, bw, bh):
    """Panel 2: refinery towers, tanks, flare stack, flames and smoke."""
    base = by + bh - 4
    cv.blend_ellipse(bx + 300, base - 22, 170, 26, (255, 140, 40), 44)
    cv.rect(bx, base, bw, 4, (16, 10, 8))
    # storage tanks (cylinders)
    for tx, tw, th in ((bx + 8, 46, 24), (bx + 388, 44, 22)):
        cv.rect(tx, base - th, tw, th, (74, 60, 52))
        cv.ellipse(tx + tw // 2, base - th, tw // 2, 5, (104, 88, 76))
        cv.rect(tx, base - th + 6, tw, 2, (52, 42, 36))
    # distillation towers with caps and bands
    towers = [(bx + 66, 30, 46), (bx + 104, 24, 36), (bx + 136, 36, 48),
              (bx + 182, 28, 40), (bx + 300, 30, 48), (bx + 338, 24, 38)]
    for tx, tw, th in towers:
        cv.rect(tx, base - th, tw, th, (48, 34, 28))
        cv.poly([(tx, base - th), (tx + tw // 2, base - th - 9),
                 (tx + tw, base - th)], (48, 34, 28))
        for band_y in range(base - th + 8, base - 4, 10):
            cv.rect(tx, band_y, tw, 2, (28, 20, 16))
        cv.rect(tx + tw // 2 - 1, base - th - 12, 2, 4, (48, 34, 28))
    # connecting pipes
    cv.rect(bx + 96, base - 26, 46, 4, (60, 44, 36))
    cv.rect(bx + 214, base - 30, 92, 4, (60, 44, 36))
    cv.rect(bx + 330, base - 24, 58, 4, (60, 44, 36))
    # flare stack + flame
    cv.rect(bx + 442, base - 50, 6, 50, (60, 44, 36))
    flame(cv, bx + 445, base - 50, 18, 26)
    cv.blend_circle(bx + 445, base - 56, 18, (255, 160, 60), 44)
    # fires at the foot of two towers + smoke
    flame(cv, bx + 152, base - 2, 28, 34)
    flame(cv, bx + 316, base - 2, 24, 30)
    smoke(cv, bx + 152, base - 66, 3, 77)
    smoke(cv, bx + 316, base - 62, 3, 913)
    smoke(cv, bx + 445, base - 74, 2, 41)


def draw_tanker(cv, bx, by, bw, bh):
    """Panel 3: fuel tanker truck on a highway, fire and smoke."""
    base = by + bh - 4
    road_y = base - 12
    # distant skyline
    for sx, sw, sh in ((bx + 6, 26, 14), (bx + 40, 18, 22), (bx + 66, 30, 10),
                       (bx + 330, 22, 18), (bx + 360, 34, 12),
                       (bx + 402, 20, 24)):
        cv.rect(sx, road_y - sh, sw, sh, (30, 26, 30))
    # road + dashed centre line
    cv.rect(bx, road_y, bw, 12, (26, 26, 30))
    for dx in range(bx + 4, bx + bw - 12, 26):
        cv.rect(dx, road_y + 5, 14, 2, (190, 180, 140))
    # roadside posts
    for px in range(bx + 12, bx + bw - 8, 44):
        cv.rect(px, road_y - 8, 3, 8, (70, 66, 60))
    # tanker truck: cab, tank, chassis, wheels
    truck_y = road_y
    cv.rect(bx + 120, truck_y - 30, 34, 30, (18, 20, 24))
    cv.poly([(bx + 120, truck_y - 30), (bx + 154, truck_y - 30),
             (bx + 154, truck_y - 12), (bx + 138, truck_y - 12)],
            (150, 170, 195))
    cv.rect(bx + 124, truck_y - 10, 26, 3, (90, 90, 96))
    cv.rect(bx + 158, truck_y - 26, 118, 24, (96, 100, 110))
    cv.ellipse(bx + 158, truck_y - 14, 7, 12, (120, 126, 138))
    cv.ellipse(bx + 276, truck_y - 14, 7, 12, (120, 126, 138))
    cv.rect(bx + 158, truck_y - 17, 118, 3, (196, 110, 40))
    cv.rect(bx + 206, truck_y - 32, 16, 6, (70, 74, 84))
    cv.rect(bx + 158, truck_y - 4, 118, 4, (40, 42, 48))
    for wx in (bx + 138, bx + 196, bx + 258):
        cv.circle(wx, truck_y + 1, 7, (10, 10, 12))
        cv.circle(wx, truck_y + 1, 3, (120, 124, 132))
    # fire engulfing the rear of the tank + smoke
    flame(cv, bx + 292, truck_y - 24, 36, 42)
    flame(cv, bx + 318, truck_y - 24, 26, 30)
    cv.blend_circle(bx + 300, truck_y - 30, 22, (255, 160, 60), 48)
    smoke(cv, bx + 300, truck_y - 62, 3, 555)
    # small flames licking the road ahead of the truck
    flame(cv, bx + 96, road_y, 14, 14)


def draw_jets(cv, bx, by, bw, bh):
    """Panel 4: fighter jets with afterburners, contrails, clouds."""
    base = by + bh - 4
    # clouds
    for cx, cy, rx in ((bx + 60, by + 12, 40), (bx + 300, by + 8, 34),
                       (bx + 400, by + 22, 26)):
        cv.ellipse(cx, cy, rx, 8, (96, 108, 128))
        cv.ellipse(cx + 18, cy + 3, rx // 2, 6, (96, 108, 128))
    # runway strip at the bottom with lights
    cv.rect(bx, base - 6, bw, 6, (22, 24, 30))
    for lx in range(bx + 10, bx + bw - 10, 34):
        cv.rect(lx, base - 8, 4, 2, (220, 200, 120))
    # damaged jet silhouette on the runway + smoke column
    jx, jy = bx + 396, base - 12
    cv.poly([(jx - 34, jy), (jx + 22, jy - 3), (jx + 30, jy),
             (jx + 22, jy + 3), (jx - 34, jy + 3)], (34, 38, 44))
    cv.poly([(jx - 6, jy), (jx + 6, jy - 12), (jx + 12, jy)], (34, 38, 44))
    smoke(cv, jx - 10, jy - 8, 3, 2024)
    flame(cv, jx - 30, jy - 2, 14, 14)

    def jet(jx, jy, s, col):
        # fuselage, swept wing, tail fin, cockpit, afterburner
        cv.poly([(jx - 52 * s, jy), (jx + 38 * s, jy - 7 * s),
                 (jx + 56 * s, jy), (jx + 38 * s, jy + 7 * s),
                 (jx - 52 * s, jy + 6 * s)], col)
        cv.poly([(jx - 8 * s, jy + 2 * s), (jx + 18 * s, jy + 28 * s),
                 (jx + 2 * s, jy + 2 * s)], col)
        cv.poly([(jx - 44 * s, jy - 2 * s), (jx - 30 * s, jy - 22 * s),
                 (jx - 24 * s, jy - 2 * s)], col)
        cv.poly([(jx + 18 * s, jy - 5 * s), (jx + 30 * s, jy - 8 * s),
                 (jx + 32 * s, jy - 3 * s)], (160, 178, 200))
        flame(cv, jx - 56 * s, jy, 14 * s, 20 * s)
        cv.blend_circle(int(jx - 58 * s), jy, int(14 * s),
                        (255, 160, 60), 48)
        # contrail
        cv.line(int(jx - 72 * s), jy - 2, int(jx - 122 * s), jy - 6,
                (150, 160, 175), 2)
        cv.line(int(jx - 72 * s), jy + 3, int(jx - 116 * s), jy + 8,
                (150, 160, 175), 2)

    jet(bx + 155, by + 20, 1.25, (92, 106, 128))
    jet(bx + 330, by + 38, 0.9, (64, 78, 96))
    # burst flash near the lead jet
    fx, fy = bx + 240, by + 14
    cv.blend_circle(fx, fy, 14, (255, 190, 90), 50)
    cv.poly([(fx, fy - 10), (fx + 3, fy - 3), (fx + 10, fy), (fx + 3, fy + 3),
             (fx, fy + 10), (fx - 3, fy + 3), (fx - 10, fy), (fx - 3, fy - 3)],
            (255, 220, 140))


def draw_summit(cv, bx, by, bw, bh):
    """Panel 5: summit building with dome, columns and a row of flags."""
    base = by + bh - 4
    cx = bx + bw // 2
    # stars arc above the dome
    for i in range(7):
        ang = math.pi * (0.15 + 0.70 * i / 6.0)
        sx = int(cx + 92 * math.cos(ang))
        sy = int(by + 30 - 26 * math.sin(ang))
        cv.circle(sx, sy, 2, GOLD)
    # dome behind the pediment
    cv.ellipse(cx, by + 22, 48, 20, (36, 52, 78))
    cv.rect(cx - 2, by + 2, 4, 8, (36, 52, 78))
    # pediment + columns + steps
    cv.poly([(cx - 98, by + 28), (cx + 98, by + 28), (cx, by + 12)],
            (52, 62, 84))
    cv.rect(cx - 98, by + 28, 196, 4, (52, 62, 84))
    for i in range(5):
        colx = cx - 80 + i * 40
        cv.rect(colx, by + 32, 9, 20, (66, 76, 98))
        cv.rect(colx - 2, by + 30, 13, 3, (66, 76, 98))
        cv.rect(colx - 2, by + 50, 13, 3, (66, 76, 98))
    cv.rect(cx - 104, by + 52, 208, 3, (52, 62, 84))
    cv.rect(cx - 96, by + 55, 192, 3, (44, 52, 70))
    # EU flag on the left, small flag row in front
    cv.rect(bx + 14, by + 8, 34, 22, (0, 51, 153))
    for i in range(12):
        ang = 2 * math.pi * i / 12.0
        sx = int(bx + 31 + 9 * math.cos(ang))
        sy = int(by + 19 + 7 * math.sin(ang))
        cv.circle(sx, sy, 1, (255, 214, 23))
    flag_cols = [(0, 51, 153), (200, 40, 40), (230, 230, 230),
                 (40, 120, 60), (220, 180, 40), (60, 90, 170)]
    for i, col in enumerate(flag_cols):
        fx = cx - 108 + i * 15
        cv.rect(fx, by + 32, 2, 22, (120, 118, 110))
        cv.rect(fx + 2, by + 32, 13, 9, col)
        if col == (0, 51, 153):
            cv.circle(fx + 8, by + 36, 1, (255, 214, 23))
    # long summit table silhouette, right side
    cv.rect(bx + bw - 118, base - 14, 104, 4, (44, 52, 70))
    cv.rect(bx + bw - 110, base - 10, 4, 10, (44, 52, 70))
    cv.rect(bx + bw - 22, base - 10, 4, 10, (44, 52, 70))
    for mx in range(bx + bw - 104, bx + bw - 24, 16):
        cv.rect(mx, base - 20, 2, 6, (120, 118, 110))
        cv.circle(mx + 1, base - 21, 2, (150, 150, 145))


def draw_station(cv, x, y, w, h):
    """Panel 6: space station, solar wings, Earth arc and starfield."""
    # starfield (deterministic)
    stars(cv, x, y, w, h - 30, 46, 90210, (200, 205, 220), 1)
    stars(cv, x, y, w, h - 30, 12, 777, (255, 240, 190), 2)
    # Earth arc, bottom right (disc clipped by the panel edge)
    ecx, ecy, er = x + w - 8, y + h + 58, 132
    cv.blend_circle(ecx, ecy, er + 12, (70, 130, 220), 30)
    cv.circle(ecx, ecy, er, (40, 90, 180))
    cv.circle(ecx - 18, ecy - 14, er - 8, (90, 140, 220))
    cv.blend_ellipse(ecx - 60, ecy - 96, 44, 8, (235, 242, 250), 70)
    cv.blend_ellipse(ecx - 110, ecy - 70, 30, 6, (235, 242, 250), 55)
    cv.blend_ellipse(ecx - 30, ecy - 118, 26, 5, (235, 242, 250), 45)
    # station truss
    ty = y + 52
    cv.rect(x + 8, ty, w - 16, 5, (150, 158, 172))
    cv.rect(x + 8, ty, w - 16, 1, (200, 208, 220))
    # solar wings with grid lines
    for wx in (x + 12, x + w - 82):
        cv.rect(wx, ty - 14, 66, 28, (28, 68, 138))
        cv.rect(wx, ty - 14, 66, 2, (90, 130, 200))
        for gx in range(wx + 11, wx + 66, 11):
            cv.rect(gx, ty - 14, 1, 28, (16, 44, 96))
        cv.rect(wx, ty - 1, 66, 1, (16, 44, 96))
    # central module + docking capsule + antenna
    cv.rect(x + 92, ty - 8, 74, 16, (168, 176, 190))
    cv.ellipse(x + 92, ty, 7, 8, (196, 202, 212))
    cv.ellipse(x + 166, ty, 7, 8, (196, 202, 212))
    cv.rect(x + 104, ty - 8, 3, 16, (120, 128, 140))
    cv.rect(x + 150, ty - 8, 3, 16, (120, 128, 140))
    cv.poly([(x + 166, ty - 8), (x + 186, ty - 4), (x + 186, ty + 4),
             (x + 166, ty + 8)], (150, 158, 172))
    cv.rect(x + 186, ty - 3, 12, 6, (120, 128, 140))
    cv.line(x + 128, ty - 8, x + 128, ty - 26, (150, 158, 172), 2)
    cv.circle(x + 128, ty - 28, 2, (255, 240, 190))
    # small sun glow, top left
    cv.blend_circle(x + 18, y + 12, 12, (255, 240, 190), 40)
    cv.circle(x + 18, y + 12, 5, (255, 244, 205))


# ------------------------------------------------------------------ main -----
def main():
    cv = Canvas(W, H, PAGE_BG)

    # ---- header ----------------------------------------------------------
    cv.rect(0, 0, W, 92, HEADER_BG)
    cv.rect(0, 92, W, 2, GOLD)
    cv.text("THURSDAY 26 NOVEMBER 2026", 32, 14, 5, INK, bold=True)
    cv.text("THE WORLD IN ONE IMAGE - SIX STORIES THAT DEFINED THE DAY",
            32, 62, 2, BODY)

    # ---- panel 1: hero, trade -------------------------------------------
    px, py, pw, ph = 16, 104, 992, 240
    panel(cv, px, py, pw, ph, (22, 48, 74), (12, 28, 48), (52, 78, 104))
    # "biggest story" ribbon
    cv.rect(34, 118, 282, 22, RED)
    cv.text("THE DAY'S BIGGEST STORY", 44, 122, 2, (255, 255, 255),
            bold=True)
    kicker(cv, 34, 148, "TRADE", "WASHINGTON", GOLD)
    hl = wrap_text("US SLAPS NEW TARIFFS ON 14 TRADING PARTNERS", 566, 3)
    y = cv.block(hl, 34, 170, 3, INK, lh=24, bold=True)
    bl = wrap_text("CHINA FACES THE HIGHEST RATES IN A DRIVE AGAINST "
                   "FACTORY OVERCAPACITY. INDIA UP TO 25%. MARKETS SLIDE.",
                   566, 2)
    cv.block(bl, 34, y + 8, 2, BODY, lh=16)
    # stat chip: 14 PARTNERS
    cv.rect(34, 284, 192, 48, (12, 22, 38))
    cv.outline(34, 284, 192, 48, GOLD, 2)
    cv.text("14", 48, 290, 5, GOLD, bold=True)
    cv.text("PARTNERS", 120, 302, 2, INK, bold=True)
    # ship illustration, right side
    draw_ship(cv, 606, 118, 384, 214)

    # ---- panels 2-3 ------------------------------------------------------
    panels = [
        # (x, y, top, bottom, accent, label, region, headline, body, draw)
        (16, 356, (58, 32, 20), (28, 15, 10), (255, 140, 40),
         "MIDDLE EAST", "YEMEN",
         "HOUTHIS STRIKE SAUDI REFINERY",
         "DRONES HIT RAS TANURA REFINERY. OIL JUMPS AS IRAN SAYS "
         "TANKERS HIT MINES NEAR HORMUZ.",
         draw_refinery),
        (518, 356, (52, 24, 26), (24, 11, 13), (255, 122, 26),
         "DISASTER", "EGYPT",
         "CAIRO TANKER FIRE KILLS 31",
         "A FUEL TANKER CRASH SETS THE RING ROAD ABLAZE IN WARRAQ. "
         "21 HURT, AND THE TOLL MAY STILL RISE.",
         draw_tanker),
        (16, 576, (30, 42, 58), (15, 21, 32), (140, 170, 205),
         "WAR", "UKRAINE",
         "UKRAINE HITS RUSSIAN AIRBASE",
         "FIVE JETS DAMAGED AT SAVASLEYKA. RUSSIA HITS TWO GRAIN "
         "SHIPS OFF ODESA.",
         draw_jets),
        (518, 576, (24, 40, 68), (12, 20, 38), GOLD,
         "EUROPE", "BRUSSELS",
         "EU SUMMIT FIGHTS OVER 45BN EURO UKRAINE LOAN",
         "LEADERS IN BRUSSELS WRANGLE OVER A 1.6 TRILLION EURO "
         "BUDGET FOR 2028-2034 AND AID FOR KYIV.",
         draw_summit),
    ]
    for (x, y, c1, c2, accent, label, region, headline, body, draw) in panels:
        panel(cv, x, y, 490, 208, c1, c2, (70, 78, 92))
        kicker(cv, x + 18, y + 14, label, region, accent)
        panel_text(cv, x, y, 490, headline, body)
        cv.blend_rect(x + 18, y + 146, 490 - 36, 1, (255, 255, 255), 30)
        draw(cv, x + 12, y + 150, 490 - 24, 52)

    # ---- panel 6: space --------------------------------------------------
    px, py, pw, ph = 16, 796, 992, 128
    panel(cv, px, py, pw, ph, (12, 16, 34), (5, 7, 15), (52, 62, 84))
    kicker(cv, 34, 808, "SPACE", "CHINA", (140, 200, 255))
    hl = wrap_text("FIRST FOREIGN ASTRONAUT ABOARD TIANGONG", 656, 3)
    y = cv.block(hl, 34, 828, 3, INK, lh=24, bold=True)
    bl = wrap_text("PAKISTAN'S MUHAMMAD ZEESHAN ALI DOCKS ON SHENZHOU-24, "
                   "THE FIRST NON-CHINESE VISITOR TO CHINA'S STATION.",
                   656, 2)
    cv.block(bl, 34, y + 4, 2, BODY, lh=16)
    # clip the Earth arc to this panel so it cannot bleed into the ticker
    cv.set_clip(16, 796, 1008, 924)
    draw_station(cv, 700, 806, 290, 110)
    cv.reset_clip()

    # ---- ticker ----------------------------------------------------------
    tx, ty, tw, th = 16, 936, 992, 72
    panel(cv, tx, ty, tw, th, (10, 14, 24), (8, 12, 22), (48, 56, 70))
    cv.rect(tx, ty, tw, 2, GOLD)
    cv.rect(28, 948, 138, 20, RED)
    cv.text("ALSO TODAY", 38, 952, 2, (255, 255, 255), bold=True)
    cv.text("KIM URGES WIDER DEPLOYMENT OF TACTICAL NUCLEAR WEAPONS",
            178, 950, 2, INK)
    fx, fy = 28, 978
    cv.poly([(fx, fy - 5), (fx + 5, fy), (fx, fy + 5), (fx - 5, fy)], GOLD)
    cv.text("AI STOCKS SLIDE AS NASDAQ NEARS BEAR MARKET - THANKSGIVING "
            "DAY IN THE US", 44, 972, 2, BODY)

    # ---- write PNG -------------------------------------------------------
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    raw = bytearray()
    stride = W * 3
    for yy in range(H):
        raw.append(0)
        raw += cv.buf[yy * stride:(yy + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        out = struct.pack(">I", len(data)) + tag + data
        out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    print("wrote %s (%d bytes)" % (path, len(png)))


if __name__ == "__main__":
    main()
