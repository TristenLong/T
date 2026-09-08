import sys
import json
from PIL import Image

path = r"C:\Users\trist\AppData\Local\Temp\opencode\view_play.png"
if len(sys.argv) > 1:
    path = sys.argv[1]

im = Image.open(path).convert("RGB")
w, h = im.size
px = im.load()

# NES Dig Dug renders 256x224 inside a 960x480 canvas (scale 3.75).
# The playfield tiles are 8x8 NES px -> 30x30 css px. HUD ~ top 32 nx.
cols, rows = 28, 21
sx, sy = w / 256.0, h / 224.0

def classify(r, g, b):
    if r > 190 and g > 120 and b < 90 and (r - g) > 70:
        return "P"                # player orange
    if b > 120 and b > r + 30 and g < 110:
        return "E"                # Pooka purple
    if g > 130 and r < 120 and b < 110 and (g - r) > 25:
        return "E"                # Fygar green
    if 150 < r < 230 and 90 < g < 160 and 40 < b < 110 and r > g > b:
        return "D"                # dirt (tan/brown)
    if r > 185 and g > 170 and b > 130:
        return "D"                # light dirt
    if r > 150 and abs(r-g) < 20 and abs(g-b) < 25 and g < 120:
        return "R"                # rock (grey)
    if r < 30 and g < 30 and b < 35:
        return "."                # empty/tunnel
    return "?"

# Build tile grid: classify at each input node, majority vote.
tiles = [["?" for _ in range(cols)] for _ in range(rows)]
for ty in range(rows):
    for tx in range(cols):
        votes = {}
        # center of tile in css px, sample a small patch
        cx = int((tx * 8 + 4) * sx)
        cy = int((ty * 8 + 4) * sy)
        for dy in (-6, 0, 6):
            for dx in (-6, 0, 6):
                X = min(w - 1, max(0, cx + dx))
                Y = min(h - 1, max(0, cy + dy))
                k = classify(*px[X, Y])
                votes[k] = votes.get(k, 0) + 1
        top = max(votes, key=votes.get)
        # prefer D when mixed E/P present - entity sprites are small; count only if dominant
        tiles[ty][tx] = top

for row in tiles:
    print("".join(row))

out = {
    "w": w, "h": h, "cols": cols, "rows": rows,
    "grid": tiles,
}
print(json.dumps(out))