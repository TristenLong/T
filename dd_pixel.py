import sys
import json
from PIL import Image
from collections import Counter

path = r"C:\Users\trist\AppData\Local\Temp\opencode\dd_wide.png"
if len(sys.argv) > 1:
    path = sys.argv[1]

im = Image.open(path).convert("RGB")
w, h = im.size
px = im.load()

# NES palette-ish buckets (allowing tolerance)
def bucket(r, g, b):
    if r > 200 and g > 140 and b < 90 and (r-g) > 70:
        return "orange(digdug)"
    if r < 120 and g < 100 and b > 140 and b > r + 40:
        return "purple(pooka)"
    if g > 140 and r < 110 and b < 110 and g > r + 40:
        return "green(fygar)"
    if r > 190 and g > 175 and b > 140:
        return "tan(dirt/light)"
    if r < 30 and g < 30 and b < 30:
        return "black"
    if r < 110 and g < 90 and b < 75 and r > 40:
        return "brown(dirt)"
    if r > 150 and g < 90 and b < 90 and 40 < r - g < 120:
        return "red-ish"
    if abs(r - g) < 12 and abs(g - b) < 12 and r > 90:
        return "grey(rock)"
    return "other(%d,%d,%d)" % (r, g, b)

counts = Counter()
for y in range(0, h, 4):
    for x in range(0, w, 4):
        counts[bucket(*px[x, y])] += 1
print("IMG", w, h)
for k, v in counts.most_common(20):
    print("%-24s %4d %6.1f%%" % (k, v, 100.0 * v / ((w // 4) * (h // 4))))

# Locate player (orange) centroid and enemy clusters
oo = [(x, y) for y in range(0, h, 2) for x in range(0, w, 2) if bucket(*px[x, y]) == "orange(digdug)"]
pp = [(x, y) for y in range(0, h, 2) for x in range(0, w, 2) if bucket(*px[x, y]) == "purple(pooka)"]
gg = [(x, y) for y in range(0, h, 2) for x in range(0, w, 2) if bucket(*px[x, y]) == "green(fygar)"]


def centroid(pts):
    if not pts:
        return None
    x = sum(p[0] for p in pts) // len(pts)
    y = sum(p[1] for p in pts) // len(pts)
    return (x, y, len(pts))


def clusters(pts, gap=40):
    out = []
    for p in pts:
        placed = False
        for c in out:
            if abs(p[0] - c[0]) < gap and abs(p[1] - c[1]) < gap:
                c[0] = (c[0] * c[2] + p[0]) // (c[2] + 1)
                c[1] = (c[1] * c[2] + p[1]) // (c[2] + 1)
                c[2] += 1
                placed = True
                break
        if not placed:
            out.append([p[0], p[1], 1])
    return [(round(c[0]), round(c[1]), c[2]) for c in out if c[2] >= 3]


print("PLAYER(orange):", centroid(oo))
print("POOKAS:", clusters(pp))
print("FYGARS:", clusters(gg))