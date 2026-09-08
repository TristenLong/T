from PIL import Image

base = "C:/Users/trist/AppData/Local/Temp/opencode/"
aw = Image.open(base + "dd_sl_before.png").convert("RGB").load()
mw = Image.open(base + "dd_sl_after_move.png").convert("RGB").load()
lw = Image.open(base + "dd_sl_after_load.png").convert("RGB").load()
print("before-vs-move", sum(1 for y in range(0, 480, 3) for x in range(0, 960, 3) if aw[x, y] != mw[x, y]))
print("before-vs-load", sum(1 for y in range(0, 480, 3) for x in range(0, 960, 3) if aw[x, y] != lw[x, y]))
print("move-vs-load", sum(1 for y in range(0, 480, 3) for x in range(0, 960, 3) if mw[x, y] != lw[x, y]))