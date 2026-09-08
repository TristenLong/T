import sys, json
from PIL import Image
import math

path = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\trist\AppData\Local\Temp\opencode\view_ev.png"
im = Image.open(path).convert("RGB")
w, h = im.size
px = im.load()

def classify(r, g, b):
    if r > 150 and g < 110 and b < 70 and (r - g) > 100:
        return "player"
    if b > 120 and b > r + 30 and g < 110:
        return "enemy"
    if g > 130 and r < 120 and b < 110 and (g - r) > 25:
        return "enemy"
    return "other"

# playfield band: NES playfield occupies roughly y 30%..78% of the 480px canvas
Y0, Y1 = int(h * 0.30), int(h * 0.78)
pts = {"player": [], "enemy": []}
for y in range(Y0, Y1, 2):
    for x in range(0, w, 2):
        k = classify(*px[x, y])
        if k in pts:
            pts[k].append((x, y))

def clusters(ps, gap=45, min_n=25):
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

players = clusters(pts["player"], gap=35, min_n=60)
enemies = clusters(pts["enemy"], gap=40, min_n=15)
print(json.dumps({
    "player": [{"x": round(c[0] * 100 / w, 1), "y": round(c[1] * 100 / h, 1), "n": int(c[2])} for c in players],
    "enemy": [{"x": round(c[0] * 100 / w, 1), "y": round(c[1] * 100 / h, 1), "n": int(c[2])} for c in enemies],
    "buckets": {"player": len(pts["player"]), "enemy": len(pts["enemy"])},
}))