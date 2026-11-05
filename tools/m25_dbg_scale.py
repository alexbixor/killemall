import sys; sys.path.insert(0, "tools")
import importlib
tss = importlib.import_module("test_sprite_scale")
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns
ROOT = tss.ROOT
art = [r for r in (ROOT / "assets/sprites/00_imp_walk_a.txt").read_text().splitlines() if r and not r.startswith(";")]
first_ink = next(i for i, r in enumerate(art) if "#" in r)
m = machine()
for d in (1.0, 1.5, 2.0):
    for x in range(7, 12): tss.map_set(m, x, 7, 0)
    tss.map_set(m, 11, 7, 1)
    set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render")
    set_thing(m, 0, 1, 3.5 + d, 7.5); call(m, "render")
    v = tss.vis_entries(m)[0]; hv, c0, nc = v["hv"], v["c0"], v["nc"]
    top, bot, cols = tss.silhouette(m)
    hd = ((hv - hv // 4) + (hv // 4) // 4) & 254
    base = 48 + hv // 2
    exp_top = base - hd + hd * first_ink // 24
    print(d, "hv", hv, "c0", c0, "nc", nc, "top", top, "exp_top", exp_top, "bot", bot, "base", base, "hd", hd,
          "cols", min(cols), max(cols), "span", max(c0, 0), min(c0 + nc, 64) - 1, "first_ink", first_ink)
