#!/usr/bin/env python3
"""Genera docs/assets/flow.gif: el flow agéntico de principio a fin, en pixel art.

Uso: python3 docs/assets/make_flow_gif.py   (requiere Pillow)
Todo se dibuja a 192x108 píxeles lógicos y se escala sin suavizado.
"""
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

W, H, SCALE = 192, 108, 4
FRAME_MS = 90
OUT = Path(__file__).with_name("flow.gif")

PAL = {
    "bg": (22, 22, 40), "star": (70, 70, 110), "floor": (52, 52, 84), "bar": (14, 14, 26),
    "text": (236, 236, 244), "dim": (140, 140, 170), "white": (250, 250, 250), "black": (10, 10, 16),
    "skin": (240, 196, 150), "hair": (110, 70, 40), "shirt": (70, 120, 220), "pants": (40, 46, 80),
    "opus": (170, 110, 240), "opus_d": (110, 60, 180),
    "son": (60, 200, 200), "son_d": (30, 130, 140),
    "gold": (250, 200, 60), "red": (235, 70, 70), "green": (90, 220, 110),
    "paper": (238, 232, 214), "ink": (120, 120, 140),
    "wp1": (250, 140, 60), "wp2": (90, 170, 255), "wp3": (240, 90, 170), "wp4": (160, 220, 80),
}
WP_COLORS = ["wp1", "wp2", "wp3", "wp4"]

FONT = {
    "A": [".#.", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": [".##", "#..", "#..", "#..", ".##"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"], "F": ["###", "#..", "##.", "#..", "#.."],
    "G": [".##", "#..", "#.#", "#.#", ".##"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", ".#."],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": [".#.", "#.#", "#.#", "#.#", ".#."], "P": ["##.", "#.#", "##.", "#..", "#.."],
    "Q": [".#.", "#.#", "#.#", "##.", ".##"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": [".##", "#..", ".#.", "..#", "##."], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"], "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"], "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "##."],
    " ": ["...", "...", "...", "...", "..."], "-": ["...", "...", "###", "...", "..."],
    ".": ["...", "...", "...", "...", ".#."], ":": ["...", ".#.", "...", ".#.", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."], "?": ["##.", "..#", ".#.", "...", ".#."],
    "!": [".#.", ".#.", ".#.", "...", ".#."], ">": ["#..", ".#.", "..#", ".#.", "#.."],
    "+": ["...", ".#.", "###", ".#.", "..."], "=": ["...", "###", "...", "###", "..."],
    ",": ["...", "...", "...", ".#.", "#.."], "(": [".#.", "#..", "#..", "#..", ".#."],
    ")": [".#.", "..#", "..#", "..#", ".#."],
}

ROBOT = [
    "....y....",
    "...ccc...",
    ".ccccccc.",
    ".cwkcwkc.",
    ".ccccccc.",
    "..cmmmc..",
    "...ccc...",
    ".ddddddd.",
    "d.ddddd.d",
]
ROBOT_LEGS = [["..d...d..", "..d...d.."], [".d.....d.", "..d...d.."]]
HUMAN = [
    "..hhh..",
    ".hhhhh.",
    ".hsssh.",
    "..sss..",
    "...s...",
    ".bbbbb.",
    "b.bbb.b",
    "s.bbb.s",
    "..bbb..",
]
HUMAN_LEGS = [["..d.d..", "..d.d.."], [".d...d.", "..d.d.."]]
CHECK = ["....#", "...##", "#.##.", "###..", ".#..."]
CROSS = ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"]
BUG = [".#.#.", "#####", ".###.", "#####", "#.#.#"]
SHIELD = ["#######", "#rrrrr#", "#rwwwr#", "#rrwrr#", "#rrwrr#", ".#rrr#.", "..#r#..", "...#..."]
GLASS = [".ggg.", "g...g", "g...g", "g...g", ".ggg.", "....h", ".....h"]

random.seed(7)
STARS = [(random.randrange(W), random.randrange(84)) for _ in range(40)]


class Frame:
    def __init__(self):
        self.img = Image.new("RGB", (W, H), PAL["bg"])
        self.d = ImageDraw.Draw(self.img)

    def px(self, x, y, color):
        if 0 <= x < W and 0 <= y < H:
            self.img.putpixel((int(x), int(y)), PAL[color] if isinstance(color, str) else color)

    def rect(self, x0, y0, x1, y1, color, fill=True):
        c = PAL[color]
        if fill:
            self.d.rectangle([x0, y0, x1, y1], fill=c)
        else:
            self.d.rectangle([x0, y0, x1, y1], outline=c)

    def text(self, x, y, s, color="text", scale=1):
        for ch in s.upper():
            glyph = FONT.get(ch, FONT["?"])
            for gy, row in enumerate(glyph):
                for gx, v in enumerate(row):
                    if v == "#":
                        for sy in range(scale):
                            for sx in range(scale):
                                self.px(x + gx * scale + sx, y + gy * scale + sy, color)
            x += 4 * scale
        return x

    def ctext(self, cx, y, s, color="text", scale=1):
        self.text(cx - (len(s) * 4 * scale - scale) // 2, y, s, color, scale)

    def sprite(self, x, y, rows, colors):
        for sy, row in enumerate(rows):
            for sx, v in enumerate(row):
                if v != "." and v in colors:
                    self.px(x + sx, y + sy, colors[v])

    def bubble(self, x, y, w, h, tail_x, tail_up=False):
        self.rect(x + 1, y, x + w - 1, y + h, "white")
        self.rect(x, y + 1, x + w, y + h - 1, "white")
        for i in range(3):  # cola triangular que apunta al que habla
            ty = (y - 1 - i) if tail_up else (y + h + 1 + i)
            self.rect(tail_x - (2 - i), ty, tail_x + (2 - i), ty, "white")


def text_w(s, scale=1):
    return len(s) * 4 * scale - scale


def background(f, caption=None):
    for (x, y) in STARS:
        f.px(x, y, "star")
    f.rect(0, 88, W - 1, 88, "floor")
    f.rect(0, 96, W - 1, H - 1, "bar")
    if caption:
        f.ctext(W // 2, 100, caption, "gold")


def draw_human(f, x, y, step=0):
    f.sprite(x, y, HUMAN + HUMAN_LEGS[step % 2], {"h": "hair", "s": "skin", "b": "shirt", "d": "pants"})


def draw_robot(f, x, y, head, body, step=0, hat=None, label=None):
    f.sprite(x, y, ROBOT + ROBOT_LEGS[step % 2],
             {"y": "gold", "c": head, "w": "white", "k": "black", "m": "black", "d": body})
    if hat:
        f.rect(x + 2, y, x + 6, y + 1, hat)
        f.rect(x + 1, y + 1, x + 7, y + 1, hat)
    if label:
        f.ctext(x + 4, y + 13, label, "dim")


def opus(f, x, y, step=0, label="ARQUITECTO"):
    draw_robot(f, x, y, "opus", "opus_d", step, label=label)


def sonnet(f, x, y, step=0, hat=None, label=None):
    draw_robot(f, x, y, "son", "son_d", step, hat=hat, label=label)


def doc(f, x, y, lines=8, manifest=False, w=22, h=26):
    f.rect(x, y, x + w, y + h, "paper")
    f.rect(x + w - 4, y, x + w, y + 4, "bg")
    f.rect(x + w - 4, y + 4, x + w, y + 4, "ink")
    f.rect(x + w - 4, y, x + w - 4, y + 4, "ink")
    for i in range(min(lines, 7)):
        ly = y + 4 + i * 3
        lw = [16, 12, 14, 10, 15, 11, 13][i]
        color = WP_COLORS[i % 4] if (manifest and i >= 4) else "ink"
        f.rect(x + 3, ly, x + 3 + min(lw, w - 6), ly, color)


def file_block(f, x, y, color, label, fill=1.0):
    f.rect(x, y, x + 15, y + 11, "floor", fill=False)
    hh = int(10 * max(0.0, min(1.0, fill)))
    if hh:
        f.rect(x + 1, y + 11 - hh, x + 14, y + 10, color)
    f.ctext(x + 8, y + 14, label, "dim")


def progress(f, x, y, w, p, color):
    f.rect(x, y, x + w, y + 3, "floor", fill=False)
    fw = int((w - 2) * max(0.0, min(1.0, p)))
    if fw > 0:
        f.rect(x + 1, y + 1, x + fw, y + 2, color)


def icon(f, x, y, rows, color):
    f.sprite(x, y, rows, {"#": color})


def lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def typed(s, t):
    return s[: int(len(s) * max(0.0, min(1.0, t)))]


# ---------- escenas: cada una recibe (frame, t en [0,1], i = índice de fotograma) ----------

def s_title(f, t, i):
    background(f)
    f.ctext(W // 2, 18, "AGENTIC FLOW", "gold", 2)
    f.ctext(W // 2, 34, "DE LA IDEA AL CODIGO, CON AGENTES", "text")
    opus(f, 36, 52, i // 4, label=None)
    f.text(48, 54, "OPUS", "opus")
    f.text(48, 61, "DISENA", "dim")
    sonnet(f, 104, 52, i // 4)
    f.text(116, 54, "SONNET", "son")
    f.text(116, 61, "ORQUESTA,", "dim")
    f.text(116, 68, "CONSTRUYE Y PRUEBA", "dim")
    if t > 0.5:
        f.ctext(W // 2, 100, "SIEMPRE EL MODELO MAS RECIENTE", "dim")


def s_request(f, t, i):
    background(f, "1  TU DESCRIBES LO QUE QUIERES")
    walk = ease(t / 0.4)
    draw_human(f, int(lerp(-8, 30, walk)), 77, i // 2 if walk < 1 else 0)
    if t > 0.25:
        opus(f, 150, 77, 0)
    if t > 0.4:
        msg = typed("QUIERO UNA API DE RESERVAS", (t - 0.4) / 0.45)
        f.bubble(14, 48, 108, 12, 36)
        f.text(18, 52, msg, "black")


def s_interview(f, t, i):
    background(f, "2  EL ARQUITECTO PREGUNTA Y AFINA")
    draw_human(f, 30, 77)
    opus(f, 150, 77, i // 6)
    rounds = [("BASE DE DATOS?", "POSTGRES"), ("AUTENTICACION?", "JWT"), ("PARALELISMO?", "CONTRATOS")]
    r = min(int(t * 3), 2)
    lt = t * 3 - r
    q, a = rounds[r]
    f.bubble(104, 40, 80, 24, 154)
    f.text(108, 44, q, "black")
    opts = [a, "OTRA"]
    for k, o in enumerate(opts):
        sel = lt > 0.55 and k == 0
        f.rect(108, 51 + k * 7, 110, 53 + k * 7, "green" if sel else "ink")
        f.text(113, 51 + k * 7, o, "black" if not sel else "son_d")
    if lt > 0.55:
        f.bubble(14, 56, 50, 12, 34)
        f.text(18, 60, a, "black")
    for k in range(3):
        f.rect(84 + k * 6, 30, 87 + k * 6, 31, "gold" if k <= r and (k < r or lt > 0.55) else "floor")


def s_write(f, t, i):
    background(f, "3  ESCRIBE ARCHITECTURE.MD")
    opus(f, 40, 77, i // 3 % 2)
    lines = int(lerp(0, 7, t / 0.7))
    doc(f, 84, 46, lines, manifest=True, w=26, h=26)
    f.text(70, 38, "ARCHITECTURE.MD", "text")
    labels = [("6 CONTRATOS", 0.3), ("8 WORK PACKAGES", 0.5), ("WP-MANIFEST", 0.65)]
    for k, (lab, at) in enumerate(labels):
        if t > at:
            f.text(118, 50 + k * 7, lab, "dim" if k < 2 else "gold")
    if t > 0.8:
        icon(f, 118, 74, CHECK, "green")
        f.text(126, 74, "VALIDATE", "green")
    if t < 0.7 and i % 2 == 0:
        f.px(52, 80, "gold")


def s_approve(f, t, i):
    background(f, "4  TU REVISAS Y APRUEBAS")
    draw_human(f, 40, 77)
    doc(f, 84, 50, 7, manifest=True, w=26, h=26)
    if t > 0.3:
        f.bubble(14, 54, 40, 12, 44)
        f.text(18, 58, "OK", "black")
        icon(f, 30, 58, CHECK, "green")
    if t > 0.6:
        f.text(118, 60, "COMMIT", "gold")
        icon(f, 144, 60, CHECK, "green")


def s_plan(f, t, i):
    background(f, "5  EL ORQUESTADOR REPARTE EN OLAS")
    sonnet(f, 30, 77, i // 4 % 2, label="ORQUESTADOR")
    doc(f, 52, 58, 7, manifest=True, w=20, h=24)
    f.text(84, 44, "OLA 1", "text")
    for k in range(3):
        if t > 0.2 + k * 0.12:
            f.rect(108 + k * 26, 43, 130 + k * 26, 49, WP_COLORS[k])
            f.text(110 + k * 26, 44, f"WP-0{k + 1}", "black")
    f.text(84, 58, "OLA 2", "text")
    if t > 0.65:
        f.rect(108, 57, 130, 63, WP_COLORS[3])
        f.text(110, 58, "WP-04", "black")
        f.text(136, 58, "USA OLA 1", "dim")
    if t > 0.8:
        f.text(84, 72, "MISMA OLA = EN PARALELO", "gold")


FILES_X = [86, 120, 154]
FY = 52  # y de los bloques de fichero: sus etiquetas quedan por encima de los robots


def s_wave1(f, t, i):
    background(f, "6  OLA 1: IMPLEMENTERS EN PARALELO")
    sonnet(f, 14, 77, 0, label="ORQ")
    rates = [1.0, 0.8, 1.15]
    for k in range(3):
        sx = int(lerp(26, FILES_X[k] - 12, ease(t / 0.25)))
        moving = t < 0.25
        sonnet(f, sx, 77, (i // 2) if moving else 0, hat="gold")
        f.rect(sx + 3, 72, sx + 5, 73, WP_COLORS[k])
        p = (t - 0.25) / 0.7 * rates[k]
        file_block(f, FILES_X[k], FY, WP_COLORS[k], f"WP-0{k + 1}", p)
        progress(f, FILES_X[k], FY - 7, 15, p, WP_COLORS[k])
        if 0.25 < t and p < 1 and i % 3 == k:
            f.px(sx + 9, 80, "gold")
        if p >= 1:
            icon(f, FILES_X[k] + 5, FY - 8, CHECK, "green")


def s_hook(f, t, i):
    background(f, "7  EL HOOK BLOQUEA LO AJENO")
    for k in range(3):
        file_block(f, FILES_X[k], FY, WP_COLORS[k], f"WP-0{k + 1}", 1.0 if k != 1 else 0.7)
    sonnet(f, FILES_X[0] - 12, 77, 0, hat="gold")
    sonnet(f, FILES_X[2] - 12, 77, 0, hat="gold")
    if t < 0.4:
        x = lerp(FILES_X[1] - 12, FILES_X[2] - 2, ease(t / 0.4))
    elif t < 0.65:
        x = FILES_X[2] - 2
    else:
        x = lerp(FILES_X[2] - 2, FILES_X[1] - 12, ease((t - 0.65) / 0.3))
    sonnet(f, int(x), 77, i // 2 if t < 0.4 or t > 0.65 else 0, hat="gold")
    f.rect(int(x) + 3, 72, int(x) + 5, 73, WP_COLORS[1])
    if 0.35 < t < 0.8:
        f.sprite(FILES_X[2] - 4, FY + 2, SHIELD, {"#": "white", "r": "red", "w": "white"})
        icon(f, FILES_X[2] + 5, FY - 8, CROSS, "red")
        f.text(96, 26, "HOOK: WP-02 NO POSEE", "red")
        f.text(96, 33, "ESE FICHERO", "red")


def s_check(f, t, i):
    background(f, "8  CHECK-WAVE: CADA UNO LO SUYO")
    for k in range(3):
        file_block(f, FILES_X[k], FY, WP_COLORS[k], f"WP-0{k + 1}", 1.0)
    sx = int(lerp(80, 176, t / 0.7))
    if t < 0.75:
        f.rect(sx, FY - 4, sx, FY + 18, "gold")
    for k in range(3):
        if sx > FILES_X[k] + 15 or t >= 0.75:
            icon(f, FILES_X[k] + 5, FY - 8, CHECK, "green")
    sonnet(f, 20, 77, 0, label="ORQ")
    if t > 0.75:
        f.text(20, 50, "OLA 1 OK", "green")


def s_wave2(f, t, i):
    background(f, "9  OLA 2: SOBRE EL CODIGO REAL")
    for k in range(3):
        file_block(f, 14 + k * 24, FY, WP_COLORS[k], f"WP-0{k + 1}", 1.0)
    x = int(lerp(96, 124, ease(t / 0.25)))
    sonnet(f, x, 77, i // 2 if t < 0.25 else 0, hat="gold")
    f.rect(x + 3, 72, x + 5, 73, WP_COLORS[3])
    p = (t - 0.25) / 0.6
    file_block(f, 140, FY, WP_COLORS[3], "WP-04", p)
    progress(f, 140, FY - 7, 15, p, WP_COLORS[3])
    for k in range(3):
        if t > 0.3 and (i // 2) % 3 == k:
            for xx in range(30 + k * 24, 138, 4):
                f.px(xx, FY + 6, WP_COLORS[k])
    if p >= 1:
        icon(f, 145, FY - 8, CHECK, "green")


def s_integrate(f, t, i):
    background(f, "10  INTEGRACION: BUILD + TESTS")
    m = ease(t / 0.45)
    for k in range(4):
        x0 = [30, 66, 102, 138][k]
        x = int(lerp(x0, 76 + k * 4, m))
        file_block(f, x, FY + 6, WP_COLORS[k], "" if m > 0.6 else f"WP-0{k + 1}", 1.0)
    if t > 0.5:
        n = int(lerp(0, 44, (t - 0.5) / 0.35))
        f.ctext(W // 2, 40, f"TESTS {n}/44", "green" if n == 44 else "text")
        progress(f, 66, 48, 60, n / 44, "green")
    if t > 0.88:
        icon(f, 132, 39, CHECK, "green")


def s_qa(f, t, i):
    background(f, "11  QA DECIDE QUE PROBAR")
    for k in range(4):
        file_block(f, 64 + k * 24, FY, WP_COLORS[k], f"WP-0{k + 1}", 1.0)
    gx = int(lerp(60, 140, (t / 0.7)))
    sonnet(f, 24, 77, i // 4 % 2, label="QA")
    f.sprite(gx, FY + 1, GLASS, {"g": "green", "h": "dim"})
    cats = ["CONTRATOS", "INTEGRACION", "CASOS LIMITE"]
    for k, c in enumerate(cats):
        if t > 0.15 + k * 0.15:
            f.text(8, 30 + k * 7, "+ " + c, "dim")
    if t > 0.62:
        f.sprite(93, FY + 4, BUG, {"#": "red"})
        f.text(110, 34, "DEFECTO EN WP-02", "red")


def s_fix(f, t, i):
    background(f, "12  RUN-WAVE 1 WP-02 --FIX")
    for k in range(4):
        file_block(f, 64 + k * 24, FY, WP_COLORS[k], f"WP-0{k + 1}", 1.0)
    x = int(lerp(160, 82, ease(t / 0.3)))
    sonnet(f, x, 77, i // 2 if t < 0.3 else 0, hat="gold")
    f.rect(x + 3, 72, x + 5, 73, WP_COLORS[1])
    if t < 0.55:
        f.sprite(93, FY + 4, BUG, {"#": "red"})
    elif t < 0.65:
        for k in range(6):
            a = k * math.pi / 3
            f.px(95 + int(4 * math.cos(a)), FY + 6 + int(4 * math.sin(a)), "gold")
    if t > 0.65:
        sonnet(f, 24, 77, 0, label="QA")
        f.bubble(10, 44, 40, 12, 28)
        f.text(16, 48, "PASS", "son_d")
        icon(f, 36, 48, CHECK, "green")


def s_done(f, t, i):
    background(f, "13  LISTO PARA COMMIT")
    opus(f, 40, 70, 0, label=None)
    sonnet(f, 64, 70, 0)
    sonnet(f, 88, 70, 0, hat="gold")
    sonnet(f, 112, 70, 0, hat="gold")
    sonnet(f, 136, 70, 0)
    draw_human(f, 160, 70)
    if (i // 3) % 2 == 0:
        for (x, y) in [(36, 60), (80, 56), (124, 58), (168, 60), (100, 52)]:
            f.px(x, y, "gold")
    f.ctext(W // 2, 22, "PASS", "green", 2)
    f.ctext(W // 2, 40, "DISENO OPUS, CODIGO SONNET", "dim")
    f.ctext(W // 2, 48, "TU DECIDES Y HACES EL PUSH", "dim")


SCENES = [
    (s_title, 32), (s_request, 34), (s_interview, 54), (s_write, 36), (s_approve, 22),
    (s_plan, 34), (s_wave1, 48), (s_hook, 40), (s_check, 26), (s_wave2, 34),
    (s_integrate, 32), (s_qa, 38), (s_fix, 36), (s_done, 34),
]


def palette_image():
    colors = list(dict.fromkeys(PAL.values()))
    flat = [c for rgb in colors for c in rgb]
    flat += [0] * (768 - len(flat))
    p = Image.new("P", (1, 1))
    p.putpalette(flat)
    return p


def render():
    pal = palette_image()
    frames = []
    for scene, n in SCENES:
        for i in range(n):
            f = Frame()
            scene(f, i / (n - 1), i)
            big = f.img.resize((W * SCALE, H * SCALE), Image.NEAREST)
            frames.append(big.quantize(palette=pal, dither=Image.Dither.NONE))
    durations = [FRAME_MS] * len(frames)
    durations[-1] = 1800  # pausa al final antes de repetir
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0,
                   optimize=False, disposal=1)
    return frames


if __name__ == "__main__":
    fr = render()
    print(f"{OUT} · {len(fr)} fotogramas · {OUT.stat().st_size / 1024:.0f} KB")
