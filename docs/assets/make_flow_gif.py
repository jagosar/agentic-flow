#!/usr/bin/env python3
"""Genera docs/assets/flow.gif: el flow agéntico de principio a fin, en pixel art.

Uso: python3 docs/assets/make_flow_gif.py   (requiere Pillow)

Sistema visual (menos, pero mejor):
- Tres actos fijos en la cabecera: ARQUITECTURA, CONSTRUCCIÓN, VERIFICACIÓN.
- Paleta cálida y sobria, con un único acento naranja; verde y rojo solo para resultados.
- Retícula de 8 px, texto alineado a la izquierda, una idea por escena.
- Lienzo de 192x108 px lógicos, escalado x4 sin suavizado.
"""
from pathlib import Path

from PIL import Image, ImageDraw

W, H, SCALE = 192, 108, 4
FRAME_MS = 100
FINAL_HOLD_MS = 3000
OUT = Path(__file__).with_name("flow.gif")
M = 8  # margen y módulo de la retícula

PAL = {
    "bg": (237, 234, 227),
    "panel": (226, 222, 213),
    "line": (200, 195, 184),
    "grey": (146, 142, 134),
    "ink": (38, 38, 38),
    "accent": (232, 98, 28),
    "ok": (62, 140, 78),
    "err": (196, 58, 48),
    "white": (250, 249, 245),
}

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
    "Ñ": ["###", "...", "##.", "#.#", "#.#"],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["##.", "..#", ".#.", "#..", "###"], "3": ["##.", "..#", ".#.", "..#", "##."],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "##.", "..#", "##."],
    "6": [".##", "#..", "###", "#.#", "###"], "7": ["###", "..#", ".#.", ".#.", ".#."],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "##."],
    " ": ["...", "...", "...", "...", "..."], "-": ["...", "...", "###", "...", "..."],
    ".": ["...", "...", "...", "...", ".#."], ":": ["...", ".#.", "...", ".#.", "..."],
    "/": ["..#", "..#", ".#.", "#..", "#.."], "?": ["##.", "..#", ".#.", "...", ".#."],
    "+": ["...", ".#.", "###", ".#.", "..."], ",": ["...", "...", "...", ".#.", "#.."], "%": ["#.#", "..#", ".#.", "#..", "#.#"],
    "·": ["...", "...", ".#.", "...", "..."], ">": ["#..", ".#.", "..#", ".#.", "#.."],
}
CHECK = ["....#", "...##", "#.##.", "###..", ".#..."]
CROSS = ["#...#", ".#.#.", "..#..", ".#.#.", "#...#"]
ACTS = ["ARQUITECTURA", "CONSTRUCCION", "VERIFICACION"]


class Frame:
    def __init__(self):
        self.img = Image.new("RGB", (W, H), PAL["bg"])
        self.d = ImageDraw.Draw(self.img)

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.img.putpixel((int(x), int(y)), PAL[c])

    def rect(self, x0, y0, x1, y1, c, fill=True):
        if x1 < x0 or y1 < y0:
            return
        self.d.rectangle([int(x0), int(y0), int(x1), int(y1)], **({"fill": PAL[c]} if fill else {"outline": PAL[c]}))

    def text(self, x, y, s, c="ink", scale=1):
        for ch in s.upper():
            for gy, row in enumerate(FONT.get(ch, FONT["?"])):
                for gx, v in enumerate(row):
                    if v == "#":
                        self.rect(x + gx * scale, y + gy * scale, x + gx * scale + scale - 1, y + gy * scale + scale - 1, c)
            x += 4 * scale
        return x

    def rtext(self, xr, y, s, c="ink", scale=1):
        self.text(xr - tw(s, scale), y, s, c, scale)

    def icon(self, x, y, rows, c):
        for sy, row in enumerate(rows):
            for sx, v in enumerate(row):
                if v == "#":
                    self.px(x + sx, y + sy, c)

    def tag(self, x, y, s, c="ink"):
        """Etiqueta de rol: rectángulo sólido con texto en negativo."""
        w = tw(s) + 4
        self.rect(x, y, x + w, y + 8, c)
        self.text(x + 2, y + 2, s, "white")
        return x + w


def tw(s, scale=1):
    return len(s) * 4 * scale - scale


def clamp(t):
    return max(0.0, min(1.0, t))


def ease(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def span(t, a, b):
    """Progreso de t dentro del intervalo [a, b], entre 0 y 1."""
    return clamp((t - a) / (b - a))


def typed(s, p):
    return s[: int(round(len(s) * clamp(p)))]


def chrome(f, act, step, caption):
    """Cabecera con los tres actos, pie con el texto de la escena y el contador."""
    seg = (W - 2 * M - 2 * 4) // 3
    for k, name in enumerate(ACTS):
        x = M + k * (seg + 4)
        state = "ink" if k < act else ("accent" if k == act else "line")
        f.text(x, 6, name, "ink" if k <= act else "grey")
        f.rect(x, 13, x + seg - 1, 13 + (1 if k == act else 0), state)
    f.rect(M, 89, W - M - 1, 89, "line")
    f.text(M, 94, caption, "ink")
    f.rtext(W - M, 94, f"{step:02d}/{TOTAL_STEPS:02d}", "grey")


# ---------------- escenas ----------------
# Cada escena recibe (f, t) con t entre 0 y 1. Los textos visibles son cortos y en mayúsculas.

def sc_title(f, t):
    f.text(M, 30, "AGENTIC FLOW", "ink", 2)
    f.rect(M, 44, M + 15, 45, "accent")
    if t > 0.25:
        f.text(M, 52, "DE UNA IDEA A CODIGO PROBADO,", "ink")
        f.text(M, 59, "CON UN EQUIPO DE AGENTES.", "ink")
    if t > 0.5:
        f.text(M, 72, "ARQUITECTURA · CONSTRUCCION · VERIFICACION", "grey")


def sc_request(f, t):
    chrome(f, 0, 1, "TU DESCRIBES EL OBJETIVO.")
    f.tag(M, 24, "TU")
    s = typed("UNA API DE RESERVAS", span(t, 0.1, 0.6))
    end = f.text(M, 42, s, "ink", 2)
    if (int(t * 20) % 2 == 0) or t < 0.6:
        f.rect(end + 1, 42, end + 2, 51, "accent")
    if t > 0.7:
        f.text(M, 62, "CON POSTGRES Y AUTENTICACION", "grey")


def sc_interview(f, t):
    chrome(f, 0, 2, "EL ARQUITECTO PREGUNTA. TU DECIDES.")
    x = f.tag(M, 24, "OPUS", "accent")
    f.text(x + 4, 26, "ARQUITECTO", "grey")
    rows = [("BASE DE DATOS", "POSTGRES 16"), ("AUTENTICACION", "JWT"), ("ESTRATEGIA DE OLAS", "CONTRATOS PRIMERO")]
    for k, (q, a) in enumerate(rows):
        y = 40 + k * 14
        a0 = 0.08 + k * 0.28
        if t < a0:
            continue
        f.text(M, y, q + "?", "grey")
        if t > a0 + 0.14:
            f.rect(96, y + 1, 98, y + 3, "accent")
            f.text(102, y, a, "ink")
        f.rect(M, y + 9, W - M - 1, y + 9, "line")


def sc_blueprint(f, t):
    chrome(f, 0, 3, "UN CONTRATO, REVISADO POR OTRO OPUS.")
    f.text(M, 24, "ARCHITECTURE.MD", "ink")
    secs = ["1  OBJETIVO", "6  CONTRATOS", "8  AC-001..AC-012", "8  WORK PACKAGES", "10 DECISIONES"]
    for k, s in enumerate(secs):
        if t > 0.05 + k * 0.07:
            f.text(M, 36 + k * 8, s, "ink" if k in (2, 3) else "grey")
    # manifiesto
    x0 = 100
    if t > 0.35:
        f.text(x0, 24, "WP", "grey")
        f.text(x0 + 24, 24, "OLA", "grey")
        f.text(x0 + 44, 24, "PROPIEDAD", "grey")
        f.rect(x0, 31, W - M - 1, 31, "line")
    for k, (wp, ola, w) in enumerate([("WP-01", "1", 26), ("WP-02", "1", 18), ("WP-03", "1", 22), ("WP-04", "2", 14)]):
        if t > 0.4 + k * 0.07:
            y = 36 + k * 8
            f.text(x0, y, wp, "ink")
            f.text(x0 + 28, y, ola, "ink")
            f.rect(x0 + 44, y + 1, x0 + 44 + w, y + 3, "ink" if ola == "1" else "grey")
    if t > 0.66:
        f.icon(x0, 68, CHECK, "ok")
        f.text(x0 + 8, 68, "VALIDATE OK", "ok")
    if t > 0.74:
        f.icon(x0, 76, CHECK, "ok")
        f.text(x0 + 8, 76, "REVISADO POR OPUS", "ok")
    if t > 0.84:
        f.icon(M, 80, CHECK, "accent")
        f.text(M + 8, 80, "APROBADO POR TI", "accent")


# Gantt compartido por las escenas de construcción
LANES = [("WP-01", 41, 1.00), ("WP-02", 51, 0.78), ("WP-03", 61, 0.90), ("WP-04", 74, 0.0)]
GX0, GW1, GX2, GX3 = 40, 64, 116, 176  # inicio ola 1, longitud máx. ola 1, inicio y fin ola 2


def gantt(f, p1, p2, checked=False, highlight=None):
    x = f.tag(M, 20, "SONNET", "ink")
    f.text(x + 4, 22, "ORQUESTADOR + IMPLEMENTERS", "grey")
    f.text(GX0, 32, "OLA 1", "grey")
    f.text(GX2, 32, "OLA 2", "grey")
    f.rect(GX2 - 3, 32, GX2 - 3, 80, "line")
    for name, y, speed in LANES[:3]:
        f.text(M, y, name, "accent" if highlight == name else "ink")
        f.rect(GX0, y + 1, GX0 + GW1, y + 3, "panel")
        done = clamp(p1 * (1.0 / speed if speed else 1))
        L = int(GW1 * done)
        if L:
            f.rect(GX0, y + 1, GX0 + L, y + 3, "ink")
        if 0 < done < 1:
            f.rect(GX0 + L - 1, y + 1, GX0 + L, y + 3, "accent")
        if checked and done >= 1:
            f.icon(GX0 + GW1 + 2, y - 1, CHECK, "ok")
    name, y, _ = LANES[3]
    f.text(M, y, name, "ink")
    f.rect(GX2, y + 1, GX3, y + 3, "panel")
    L = int((GX3 - GX2) * clamp(p2))
    if L:
        f.rect(GX2, y + 1, GX2 + L, y + 3, "ink")
        if p2 < 1:
            f.rect(GX2 + L - 1, y + 1, GX2 + L, y + 3, "accent")
    if p2 >= 1:
        f.icon(GX3 - 4, y - 7, CHECK, "ok")


def sc_wave1(f, t):
    chrome(f, 1, 5, "LA OLA 1 CORRE EN PARALELO.")
    gantt(f, 0.55 * ease(span(t, 0.05, 0.9)), 0)


def sc_guard(f, t):
    chrome(f, 1, 6, "CADA AGENTE SOLO ESCRIBE LO SUYO.")
    gantt(f, 0.55, 0, highlight="WP-02")
    y2, y3 = LANES[1][1], LANES[2][1]
    x = GX0 + int(GW1 * 0.55 / 0.78)
    if t > 0.15:
        reach = int(10 * ease(span(t, 0.15, 0.4)))
        for yy in range(y2 + 5, y2 + 5 + reach, 2):
            f.px(x, yy, "accent")
    if t > 0.4:
        f.icon(x - 2, y3 - 2, CROSS, "err")
        f.text(x + 8, y3 - 1, "BLOQUEADO POR EL HOOK", "err")
    if t > 0.6:
        f.text(M, 82, "NI LOS DE WP-03, NI LOS TESTS DE ACEPTACION", "grey")


def sc_wave2(f, t):
    chrome(f, 1, 7, "CHECK-WAVE. LA OLA 2 USA SU CODIGO.")
    p1 = 0.55 + 0.45 * ease(span(t, 0.0, 0.3))
    gantt(f, p1, ease(span(t, 0.45, 0.9)), checked=t > 0.32)
    if 0.3 < t < 0.45:
        f.text(GX2 + 4, 41, "CHECK-WAVE OK", "ok")


def sc_integrate(f, t):
    chrome(f, 1, 8, "LA ACEPTACION PASA A VERDE.")
    x = f.tag(M, 22, "SONNET", "ink")
    f.text(x + 4, 24, "ORQUESTADOR", "grey")
    m = ease(span(t, 0.0, 0.35))
    for k, (name, y, _) in enumerate(LANES):
        yy = int(y + (50 - y) * m)
        f.rect(GX0, yy + 1, GX3, yy + 3, "ink")
        if m < 0.5:
            f.text(M, y, name, "ink")
    if t > 0.4:
        n = int(12 * ease(span(t, 0.4, 0.8)))
        f.text(GX0, 58, f"AC {n:2d}/12", "ok" if n == 12 else "ink", 2)
        f.text(GX0, 74, "BUILD · TIPOS · LINT · TESTS · DIFF", "grey")
    if t > 0.82:
        f.icon(GX0 + tw("AC 12/12", 2) + 6, 62, CHECK, "ok")


def qa_rows(f, t, fixed=0.0):
    x = f.tag(M, 22, "SONNET", "ink")
    f.text(x + 4, 24, "QA", "grey")
    rows = [("CONTRATOS ENTRE WP", True), ("FLUJOS DE PUNTA A PUNTA", True), ("CASOS LIMITE", False)]
    for k, (name, ok) in enumerate(rows):
        a0 = 0.1 + k * 0.22
        if t < a0:
            continue
        y = 38 + k * 12
        f.text(M + 10, y, name, "ink")
        f.rect(M, y + 8, W - M - 1, y + 8, "line")
        if t > a0 + 0.12:
            good = ok or fixed >= 1
            f.icon(M, y, CHECK if good else CROSS, "ok" if good else "err")
            if not ok:
                f.text(120, y, "WP-02" if fixed < 1 else "CORREGIDO", "err" if fixed < 1 else "ok")


def sc_qa(f, t):
    chrome(f, 2, 10, "QA EXPLORA LO QUE NADIE PREVIO.")
    qa_rows(f, t)
    if t > 0.75:
        f.text(M, 76, "DEFECTO ATRIBUIDO A SU WP, CON SECCION", "grey")


def sc_fix(f, t):
    chrome(f, 2, 11, "EL DEFECTO VUELVE A SU WP. MAX 2 VECES.")
    qa_rows(f, 1.0, fixed=1.0 if t > 0.7 else 0.0)
    cmd = typed("RUN-WAVE 1 WP-02 --FIX   1/2", span(t, 0.1, 0.5))
    f.rect(M, 72, W - M - 1, 84, "panel")
    f.text(M + 4, 76, "> " + cmd, "ink")
    if 0.5 < t < 0.7:
        f.rect(M + 4 + tw("> " + cmd) + 2, 76, M + 4 + tw("> " + cmd) + 3, 80, "accent")


def sc_result(f, t):
    chrome(f, 2, 12, "OPUS PLANIFICA. SONNET CONSTRUYE.")
    f.text(M, 24, "PASS", "ok", 3)
    stats = [("12", "AC EN VERDE"), ("4", "WORK PACKAGES"), ("2", "OLAS"), ("0", "ESCRITURAS AJENAS")]
    for k, (n, lab) in enumerate(stats):
        if t > 0.1 + k * 0.1:
            y = 48 + k * 8
            f.rtext(M + 22, y, n, "ink")
            f.text(M + 28, y, lab, "grey")
    if t > 0.6:
        f.rect(112, 48, 112, 76, "line")
        f.text(120, 52, "SIGUIENTE PASO", "grey")
        f.text(120, 62, "TU HACES", "accent")
        f.text(120, 69, "EL COMMIT", "accent")


def sc_acceptance(f, t):
    chrome(f, 1, 4, "OLA 0: EL EXAMEN, ANTES QUE EL CODIGO.")
    x = f.tag(M, 20, "SONNET", "ink")
    f.text(x + 4, 22, "TEST-AUTHOR", "grey")
    acs = ["AC-001  ACORTA URL VALIDA", "AC-002  RECHAZA NO HTTP", "AC-003  RESUELVE CODIGO",
           "AC-004  CODIGO DESCONOCIDO"]
    for k, a in enumerate(acs):
        if t > 0.05 + k * 0.12:
            y = 34 + k * 9
            f.text(M + 10, y, a, "ink")
            if t > 0.55:
                f.icon(M, y, CROSS, "err")
    if t > 0.6:
        f.text(136, 34, "ROJO", "err", 2)
        f.text(136, 48, "AUN NO HAY", "grey")
        f.text(136, 55, "CODIGO", "grey")
    if t > 0.75:
        f.rect(M, 76, W - M - 1, 76, "line")
        f.text(M, 80, "BLOQUEADOS PARA LOS IMPLEMENTERS", "accent")


def sc_review(f, t):
    chrome(f, 2, 9, "REVISION: SOLO LO QUE TIENE PRUEBA.")
    x = f.tag(M, 22, "SONNET", "ink")
    f.text(x + 4, 24, "REVISOR · SOLO LECTURA", "grey")
    rows = [("SEGURIDAD", True), ("CORRECCION", True), ("CONTRATOS", True), ("MANTENIBILIDAD", None)]
    for k, (name, ok) in enumerate(rows):
        a0 = 0.08 + k * 0.16
        if t < a0:
            continue
        y = 38 + k * 10
        f.text(M + 10, y, name, "ink")
        f.rect(M, y + 7, W - M - 1, y + 7, "line")
        if t > a0 + 0.1:
            if ok:
                f.icon(M, y, CHECK, "ok")
            else:
                f.rect(M + 1, y + 2, M + 3, y + 3, "grey")
                f.text(100, y, "1 HALLAZGO MEDIO", "grey")
    if t > 0.8:
        f.text(M, 80, "CONFIANZA > 80 %. CERO HALLAZGOS ES VALIDO.", "grey")


SCENES = [
    (sc_title, 30), (sc_request, 30), (sc_interview, 44), (sc_blueprint, 52), (sc_acceptance, 42),
    (sc_wave1, 28), (sc_guard, 32), (sc_wave2, 38), (sc_integrate, 34), (sc_review, 38),
    (sc_qa, 36), (sc_fix, 34), (sc_result, 34),
]
TOTAL_STEPS = 12


def palette_image():
    flat = [c for rgb in PAL.values() for c in rgb]
    p = Image.new("P", (1, 1))
    p.putpalette(flat + [0] * (768 - len(flat)))
    return p


def render_frames():
    for scene, n in SCENES:
        for i in range(n):
            f = Frame()
            scene(f, i / (n - 1))
            yield f.img


def render():
    pal = palette_image()
    frames = [im.resize((W * SCALE, H * SCALE), Image.NEAREST).quantize(palette=pal, dither=Image.Dither.NONE)
              for im in render_frames()]
    durations = [FRAME_MS] * len(frames)
    durations[-1] = FINAL_HOLD_MS
    frames[0].save(OUT, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=1)
    return frames


if __name__ == "__main__":
    fr = render()
    print(f"{OUT} · {len(fr)} fotogramas · {OUT.stat().st_size / 1024:.0f} KB")
