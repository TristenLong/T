import sys
from PIL import Image
from collections import Counter

path = r"C:\Users\trist\AppData\Local\Temp\opencode\dd_cal_playfield.png"
if len(sys.argv) > 1:
    path = sys.argv[1]

im = Image.open(path).convert("RGB")
w, h = im.size
px = im.load()

def quant(r, g, b):
    return (r // 16 * 16, g // 16 * 16, b // 16 * 16)

counts = Counter()
for y in range(0, h, 3):
    for x in range(0, w, 3):
        counts[quant(*px[x, y])] += 1

total = sum(counts.values())
for (r, g, b), v in counts.most_common(16):
    print("(%3d,%3d,%3d) %5d %6.2f%%" % (r, g, b, v, 100.0 * v / total))