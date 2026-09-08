import sys
import json
from PIL import Image

path = r"C:\Users\trist\AppData\Local\Temp\opencode\view_play.png"
if len(sys.argv) > 1:
    path = sys.argv[1]

im = Image.open(path).convert("RGB")
w, h = im.size
px = im.load()

def classify(r, g, b):
    # NES Dig Dug palette families
    if r > 190 and g > 120 and b < 90 and (r - g) > 70:
        return "player"            # orange hard hat man
    if b > 120 and b > r + 30 and g < 110:
        return "enemy"             # purple Pooka
    if g > 130 and r < 120 and b < 110 and (g - r) > 25:
        return "enemy"             # green Fygar
    if r > 185 and g > 170 and b > 130:
        return "dirt"              # light dirt
    if r < 30 and g < 30 and b < 35:
        return "black"
    return "other"

# Sample every 2px, collect clusters
import math
pts = {k: [] for k in ("player", "enemy", "dirt")}
for y in range(0, h, 2):
    for x in range(0, w, 2):
        k = classify(*px[x, y])
        if k in pts:
            pts[k].append((x, y))

def centroid(ps):
    if not ps:
        return None
    return {"x": sum(p[0] for p in ps) / len(ps), "y": sum(p[1] for p in ps) / len(ps), "n": len(ps)}

def clusters(ps, gap=50, min_n=6):
    out = []
    for p in ps:
        done = False
        for c in out:
            if math.hypot(p[0] - c["x"], p[1] - c["y"]) < gap:
                c["n"] += 1
                c["x"] = (c["x"] * (c["n"] - 1) + p[0]) / c["n"]
                c["y"] = (c["y"] * (c["n"] - 1) + p[1]) / c["n"]
                done = True
                break
        if not done:
            out.append({"x": float(p[0]), "y": float(p[1]), "n": 1})
    return [c for c in out if c["n"] >= min_n]

player = clusters(pts["player"], gap=30, min_n=8)
enemies = clusters(pts["enemy"], gap=40, min_n=5)
dirt = len(pts["dirt"])

# scale so coordinates are relative to canvas (w corresponds to 256 NES units -> normalize to 100 range)
def norm(c):
    return {"x": round(c["x"] * 100.0 / w, 1), "y": round(c["y"] * 100.0 / h, 1), "n": c["n"]}

out = {
    "w": w, "h": h,
    "dirtPct": round(100.0 * 4 * dirt / (w * h), 1),
    "player": [norm(c) for c in player],
    "enemy": [norm(c) for c in enemies],
    "buckets": {k: len(v) for k, v in pts.items()},
}
print(json.dumps(out))