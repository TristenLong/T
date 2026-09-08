from PIL import Image

base = "C:/Users/trist/AppData/Local/Temp/opencode/"
a = Image.open(base + "dd_rt_saveframe.png").convert("RGB").load()
b = Image.open(base + "dd_rt_moved.png").convert("RGB").load()
c = Image.open(base + "dd_rt_restored.png").convert("RGB").load()
Wa = Image.open(base + "dd_rt_saveframe.png").convert("RGB").size

def d(i, j):
    n = 0
    for y in range(0, Wa[1], 3):
        for x in range(0, Wa[0], 3):
            if i[x, y] != j[x, y]:
                n += 1
    return n

print("saveframe-vs-moved", d(a, b))
print("saveframe-vs-restored", d(a, c))
print("moved-vs-restored", d(b, c))