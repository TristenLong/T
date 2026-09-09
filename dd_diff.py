import sys, json, math
from PIL import Image

# dd_diff.py <pathA> <pathB> -> one-shot entity analysis for Dig Dug.
# Frame A = pre-branch (saved), Frame B = post-branch.
# Emits:
#   player   : moving orange-red blob in B {x,y,n}|null
#   enemies  : moving purple/green blobs in B
#   basePlayer: static orange-red blob in A (strict rule, dirt-proof)
#   baseEnemies: static purple/green blobs in A
#   moving   : total changed pixels
# Dirt is tan (g>120) and dark-brown (r-g~128); the player's hard hat is
# saturated red-orange (208,32,0): r-g~176 -> r-g>140 rule isolates it.

pathA, pathB = sys.argv[1], sys.argv[2]
a = Image.open(pathA).convert("RGB")
b = Image.open(pathB).convert("RGB")
w, h = a.size
pa, pb = a.load(), b.load()
cw, ch = w / 100.0, h / 100.0

# band: only the cave/playfield (y 22-88%). The top 8-22% holds the score HUD in
# live play and the character/name table on attract screens (which pollutes the
# enemy reads); enemies cannot exist above ~y22% in round 1.
Y0, Y1 = int(h * 0.22), int(h * 0.88)

def is_pooka(r, g, b):
    return r > 150 and g < 75 and b < 75

def is_fygar(r, g, b):
    return g > 110 and r < 75 and b < 75

def is_enemy(r, g, b):
    return is_pooka(r, g, b) or is_fygar(r, g, b)

def is_player(r, g, b):
    # Dig Dug: white suit (255,255,255) and cyan accessories (0,130,140)
    return (r > 240 and g > 240 and b > 240) or (b > 110 and g > 100 and r < 60)

def collect(px, preds):
    pts = {k: [] for k in preds}
    for y in range(Y0, Y1, 2):
        for x in range(0, w, 2):
            c = px[x, y]
            for k, fn in preds.items():
                if fn(*c):
                    pts[k].append((x, y))
                    break
    return pts

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

n = lambda c: {"x": round(c[0] / cw, 1), "y": round(c[1] / ch, 1), "n": int(c[2])}

# attract/name-table indicator: enemy+player clutter in the sky area (excluding score area on the right)
tt, te = [], []
for y in range(int(h * 0.04), int(h * 0.16), 2):
    for x in range(0, int(w * 0.60), 2):
        c = pa[x, y]
        if is_player(*c):
            tt.append((x, y))
        elif is_enemy(*c):
            te.append((x, y))
topEnemies = clusters(te, gap=40, min_n=20)
topPlayers = clusters(tt, gap=35, min_n=50)

base = collect(pa, {"p": is_player, "e": is_enemy})
post = collect(pb, {"p": is_player, "e": is_enemy})
be = clusters(base["e"], gap=35, min_n=10)
pe = clusters(post["e"], gap=35, min_n=10)

# Filter out white pixels belonging to enemy eyes/goggles
bp_raw = clusters(base["p"], gap=35, min_n=10)
pp_raw = clusters(post["p"], gap=35, min_n=10)
bp = [p for p in bp_raw if not any(math.hypot(p[0] - e[0], p[1] - e[1]) < 35 for e in be)]
pp = [p for p in pp_raw if not any(math.hypot(p[0] - e[0], p[1] - e[1]) < 35 for e in pe)]

# Center anchor for player selection among static rocks
cx, cy = w * 0.45, h * 0.48
best_bp = min(bp, key=lambda c: math.hypot(c[0] - cx, c[1] - cy)) if bp else None
best_pp = min(pp, key=lambda c: math.hypot(c[0] - cx, c[1] - cy)) if pp else None

# diff-based player (moving white/cyan) as the authoritative post position
player_diff, enemy_diff = [], []
for y in range(Y0, Y1, 2):
    for x in range(0, w, 2):
        c1, c2 = pa[x, y], pb[x, y]
        if abs(c1[0] - c2[0]) + abs(c1[1] - c2[1]) + abs(c1[2] - c2[2]) < 45:
            continue
        if is_player(*c2):
            player_diff.append((x, y))
        elif is_enemy(*c2):
            enemy_diff.append((x, y))

oec = clusters(enemy_diff, gap=35, min_n=8)
opc_raw = clusters(player_diff, gap=35, min_n=8)
opc = [p for p in opc_raw if not any(math.hypot(p[0] - e[0], p[1] - e[1]) < 35 for e in oec)]
best_diff_p = max(opc, key=lambda c: c[2]) if opc else None

chosen_player = best_diff_p or best_pp or best_bp

print(json.dumps({
    "player": n(chosen_player) if chosen_player else None,
    "basePlayer": n(best_bp) if best_bp else None,
    "baseEnemies": [n(c) for c in be],
    "enemies": [n(c) for c in pe],
    "movingEnemies": [n(c) for c in oec],
    "moving": len(player_diff) + len(enemy_diff),
    "topEnemies": [n(c) for c in topEnemies],
    "attractTop": len(topEnemies) + len(topPlayers),
}))