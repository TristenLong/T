import sys, json, math
from io import BytesIO
from PIL import Image

# dd_diff_srv.py - persistent single-frame entity analysis for Dig Dug.
# Reads length-prefixed PNG bytes on stdin; writes one JSON line per request.
# Same detection rules as dd_diff.py (static base pass).

def is_pooka(r, g, b):
    return r > 150 and g < 75 and b < 75

def is_fygar(r, g, b):
    return g > 110 and r < 75 and b < 75

def is_enemy(r, g, b):
    return is_pooka(r, g, b) or is_fygar(r, g, b)

def is_player(r, g, b):
    # Dig Dug: white suit (255,255,255) and cyan accessories (0,130,140)
    return (r > 240 and g > 240 and b > 240) or (b > 110 and g > 100 and r < 60)

def collect(px, Y0, Y1, w):
    pp, ee = [], []
    for y in range(Y0, Y1, 2):
        for x in range(0, w, 2):
            c = px[x, y]
            if is_player(*c):
                pp.append((x, y))
            elif is_enemy(*c):
                ee.append((x, y))
    return pp, ee

def clusters(ps, gap=35, min_n=6):
    out = []
    for p in ps:
        done = False
        for c in out:
            if math.hypot(p[0] - c[0], p[1] - c[1]) < gap:
                c[0] = (c[0] * c[2] + p[0]) / (c[2] + 1)
                c[1] = (c[1] * c[2] + p[1]) / (c[2] + 1)
                c[2] += 1
                done = True
                break
        if not done:
            out.append([p[0], p[1], 1])
    return [c for c in out if c[2] >= min_n]

last_player_xy = None

def analyze(img):
    global last_player_xy
    w, h = img.size
    px = img.load()
    cw, ch = w / 100.0, h / 100.0
    # cave/playfield only
    Y0, Y1 = int(h * 0.22), int(h * 0.88)
    pp, ee = collect(px, Y0, Y1, w)
    be = clusters(ee, gap=35, min_n=10)      # enemies (Pookas + Fygars)
    raw_p = clusters(pp, gap=35, min_n=10)   # player candidates + rocks

    # Filter out enemy goggles/eyes (white pixels near enemies)
    candidates = [p for p in raw_p if not any(math.hypot(p[0] - e[0], p[1] - e[1]) < 35 for e in be)]

    # Track player relative to last known position or screen center tunnel
    anchor = last_player_xy if last_player_xy is not None else (w * 0.45, h * 0.48)
    best = min(candidates, key=lambda c: math.hypot(c[0] - anchor[0], c[1] - anchor[1])) if candidates else None
    if best:
        last_player_xy = (best[0], best[1])

    # attract/name-table indicator
    tt, te = [], []
    for y in range(int(h * 0.04), int(h * 0.16), 2):
        for x in range(0, int(w * 0.60), 2):
            c = px[x, y]
            if is_player(*c):
                tt.append((x, y))
            elif is_enemy(*c):
                te.append((x, y))
    topEnemies = clusters(te, gap=40, min_n=20)
    topPlayers = clusters(tt, gap=35, min_n=50)
    n = lambda c: {"x": round(c[0] / cw, 1), "y": round(c[1] / ch, 1), "n": int(c[2])}
    return {
        "player": n(best) if best else None,
        "basePlayer": n(best) if best else None,
        "baseEnemies": [n(c) for c in be],
        "topEnemies": [n(c) for c in topEnemies],
        "attractTop": len(topEnemies) + len(topPlayers),
    }

while True:
    ln = sys.stdin.buffer.readline()
    if not ln:
        break
    try:
        n = int(ln)
        blob = sys.stdin.buffer.read(n)
        img = Image.open(BytesIO(blob)).convert("RGB")
        out = analyze(img)
        ok = True
    except Exception as e:
        out = {"error": str(e)}
        ok = False
    sys.stdout.write(("OK " if ok else "ERR ") + json.dumps(out) + "\n")
    sys.stdout.flush()