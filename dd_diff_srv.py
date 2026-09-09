import sys, json, math
from io import BytesIO
from PIL import Image

# dd_diff_srv.py - persistent single-frame entity analysis for Dig Dug.
# Reads length-prefixed PNG bytes on stdin; writes one JSON line per request.
# Same detection rules as dd_diff.py (static base pass).

def is_player(r, g, b):
    return r > 150 and g < 90 and b < 90 and (r - g) > 140

def is_purple(r, g, b):
    return b > 100 and r > 60 and g < 120 and abs(r - b) < 90

def is_green(r, g, b):
    return g > 120 and r < 120 and b < 100 and (g - r) > 25

def is_enemy(r, g, b):
    return is_purple(r, g, b) or is_green(r, g, b)

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

def clusters(ps, gap=40, min_n=6):
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

def analyze(img):
    w, h = img.size
    px = img.load()
    cw, ch = w / 100.0, h / 100.0
    # cave/playfield only: the top 8-22% holds the score HUD in live play and
    # the huge name/character table on attract screens (which pollutes enemy
    # reads). Enemies cannot exist above ~y22% in round 1.
    Y0, Y1 = int(h * 0.22), int(h * 0.88)
    pp, ee = collect(px, Y0, Y1, w)
    bp = clusters(pp, gap=35, min_n=40)      # player = biggest strict-orange blob
    be = clusters(ee, gap=40, min_n=15)      # purple/green enemies
    best = max(bp, key=lambda c: c[2]) if bp else None
    # attract/name-table indicator: enemy+player clutter ABOVE the cave.
    # Live play has ~0-1 stray blobs there; the name-entry demo has 7+.
    tt, te = [], []
    for y in range(int(h * 0.08), Y0, 2):
        for x in range(0, w, 2):
            c = px[x, y]
            if is_player(*c):
                tt.append((x, y))
            elif is_enemy(*c):
                te.append((x, y))
    topEnemies = clusters(te, gap=40, min_n=15)
    topPlayers = clusters(tt, gap=35, min_n=40)
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