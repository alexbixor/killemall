#!/usr/bin/env python3
"""test_sprite_scale.py (M2.1) - numeric sprite projection invariants on the Python Z80 core (build/kea48.tap).

Scene: player at (3.5, 7.5) facing east (angle 0) in level 1; the level wall at x = 7 is removed from the runtime map so a
thing can be placed straight ahead at distance d (1.0, 1.5, 2.0, 3.0, 4.5, 6.0 cells) with a wall put back directly behind
it (at cell x = floor(3.5 + d + 1)). Checked per distance and per asset (imp 24 rows, barrel 12 rows, health 12 rows):
 (a) vis.hv == engine wall height at the same depth (HTABN/HTABF through perp_h) within 1
 (b) bottom row == wall base row at that depth (48 + hv/2); top = bottom - hv; half-height assets: top row = horizon +-1
 (c) on-screen width (3 * nc px, M2.5C) == hd * 16/24 within 2 px and centred on column 32 (c0 + nc/2 == 32 +-1)
     M2.2: enemies (types < 16) are drawn hd = 0.8125 hv high (hv - hv/4 + hv/16) with their feet on the wall base;
     items keep hd = hv. The vis entry / depth test still carries the true hv.
 (d) hv saturates at the 128 cap (= the tallest wall band) at d = 0.4 with no wrap, pixels never below row 95 (HUD untouched)
 (e) nothing drawn for a thing behind a wall
 (f) attribute cells: sprite ink only in cells with sprite pixels; the wall attribute is kept where the sprite has no ink
 (g) enemies attacking after 3 s of AI at the start view are in the vis table when inside the FOV and <= 6 cells
usage: test_sprite_scale.py  (exit 0 on success)"""
import sys, math, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import z80
from test48 import SYM, ROOT
from test_game_sprites import machine, call, set_player, clear_things, set_thing, buf, changed_columns, BUF0, BUFCOLS, BUFSTR
from test_game_doors import fake_input
from p2e_oracle import engine_expectation, diff, clear_marks        # M2.6 P2E

ATTRWIN = 22564          # M2.5C: window cols 4..27
TYPEINK = {1: 3, 2: 4, 16: 7, 21: 5}          # M2.2 non-bright palette (sprites_e.asm TYPEINK)

def wall_height_engine(m, dist):
    """engine's own table: perp_h(HL = dist 8.8) -> A"""
    hl = int(round(dist * 256))
    m.set_memory_block(0x5EC0, bytes([0x21, hl & 255, hl >> 8, 0xCD, SYM["perp_h"] & 255, SYM["perp_h"] >> 8, 0x32, 0xE8, 0x5E, 0xC3, 0xF0, 0x5E]))
    m.pc = 0x5EC0; m.sp = 65008
    from test48 import run_until
    run_until(m, 0x5EF0)
    return m.memory[0x5EE8]

def map_set(m, x, y, code):
    m.set_memory_block(SYM["level_data"] + 1 + 8 + y * 32 + x, bytes([code]))

def vis_entries(m):
    n = m.memory[SYM["nvis"]]
    out = []
    for i in range(n):
        e = bytes(m.memory[SYM["vis"] + 6 * i: SYM["vis"] + 6 * i + 6])
        out.append(dict(hv=e[0], c0=e[1] - 256 if e[1] > 127 else e[1], nc=e[2], thing=e[5]))
    return out

def sprite_rows(ref, out):
    cols, pix = changed_columns(ref, out)
    rows = [r for c, r in pix]
    return (min(rows), max(rows), cols) if rows else (None, None, cols)

def silhouette(m):
    """rows/columns of the sprite drawn alone: white runs show over a zeroed BUF, black runs over an all-ones BUF (the
    M2.2 solid far walls make 'pixels changed vs the walls-only frame' blind to white-on-white). zbuf stays from render."""
    N = BUFCOLS * BUFSTR
    m.set_memory_block(BUF0, bytes(N)); call(m, "draw_things"); white = buf(m)
    m.set_memory_block(BUF0, bytes([0xFF]) * N); call(m, "draw_things"); black = buf(m)
    clear_marks(m)                                     # M2.6 P2E: draw_things outside render leaves CMIN marks; attr_write would paint them next frame
    c1, p1 = changed_columns(bytes(N), white)
    c2, p2 = changed_columns(bytes([0xFF]) * N, black)
    rows = [r for c, r in p1 + p2]        # M2.5: white runs + black runs (halo) = the figure
    return (min(rows), max(rows), c1 | c2) if rows else (None, None, c1 | c2)

def attrs(m):
    return [[m.memory[ATTRWIN + 32 * r + c] for c in range(24)] for r in range(12)]

def main():
    fails = 0
    m = machine()
    call(m, "init_game", "render")
    fake_input(m, 0)
    m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))        # no weapon graphic: BUF rows 72..95 hold only walls/sprites
    # open the corridor: cells x = 7..11 at y = 7 become floor; walls restored per distance below
    for x in range(7, 12): map_set(m, x, 7, 0)
    print("dist  asset   wall_h  hv  top  bot  wall_base  width_px exp_w  c0  nc  | result   (enemies: hd = 0.8125 hv)")
    cases = [(1, "imp", 24), (21, "barrel", 12), (16, "health", 12)]
    # M2.4: first ink row of each asset (art is bottom-aligned in the 24-row box; blank top rows = hunched heads / items)
    first_ink = {}
    for typ, name, asset_h in cases:
        f = {1: "00_imp_walk_a.txt", 21: "12_barrel.txt", 16: "08_health.txt"}[typ]
        art = [r for r in (ROOT / "assets/sprites" / f).read_text().splitlines() if r and not r.startswith(";")]
        assert len(art) == asset_h, (f, len(art), asset_h)
        first_ink[typ] = next(i for i, r in enumerate(art) if "#" in r)
        if typ < 16: first_ink[typ] = max(0, first_ink[typ] - 1)      # M2.5: enemies carry a 1-px black halo above the head
    for d in (1.0, 1.5, 2.0, 3.0, 4.5, 6.0):
        wx = int(3.5 + d + 1.0)
        for x in range(7, 12): map_set(m, x, 7, 1 if x == wx else 0)
        wh = wall_height_engine(m, d)
        for typ, name, asset_h in cases:
            set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m); a0 = attrs(m)
            set_thing(m, 0, typ, 3.5 + d, 7.5); call(m, "render"); out = buf(m)
            v = vis_entries(m)
            if len(v) != 1:
                print("%4.1f  %-7s FAIL: nvis %d" % (d, name, len(v))); fails += 1; continue
            hv, c0, nc = v[0]["hv"], v[0]["c0"], v[0]["nc"]
            top, bot, cols = silhouette(m)
            base = 48 + hv // 2
            hd = ((hv - hv // 4) + (hv // 4) // 4) & 254 if typ < 16 else hv    # M2.2 enemy_h: hv - hv/4 + hv/16, even
            exp_w = hd * 16 / 24
            width = 3 * nc                                                      # M2.5C: 3 px per ray column
            ok = True
            if abs(hv - wh) > 1: ok = False
            if bot is None or abs((bot + 1) - base) > 1: ok = False
            exp_top = base - hd + hd * (24 - asset_h + first_ink[typ]) // 24     # ROWTAB[v_first], v_first = box row of the first ink
            if top is None or abs(top - exp_top) > 1: ok = False
            if asset_h == 12 and (top is None or abs(top - (48 + hd * first_ink[typ] // 24)) > 1): ok = False
            if abs(width - exp_w) > 2: ok = False
            if abs((c0 + nc / 2) - 32) > 1: ok = False
            if cols and (min(cols) < max(c0, 0) or max(cols) >= min(c0 + nc, 64)): ok = False   # M2.5: ray-column span
            print("%4.1f  %-7s %5d  %3d  %3s  %3s   %4d      %5d  %5.1f  %3d %3d  | %s" % (d, name, wh, hv, top, bot, base, width, exp_w, c0, nc, "ok" if ok else "FAIL"))
            if not ok: fails += 1
            # (f) attributes: ink in every cell with sprite pixels; the wall attribute is kept in every cell outside the ink
            # row span of each byte column (the engine tints the span rmin/8..rmax/8 of each byte column: cells inside the
            # silhouette's span without ink - between the legs - are tinted too, which only recolours black/background
            # pixels inside the figure). Oracle = the sprite drawn alone over a zeroed BUF (draw_weapon stubbed).
            # M2.5 one-ink rule: the sprite changes no window attribute cell (the value itself, 0x07 after cls, is checked by
            # test_one_ink.py; the oracle machine never ran cls)
            at = attrs(m)
            bad = diff(at, engine_expectation(m))             # M2.6 P2E: cells = tint / near-wall BRIGHT / sprite ink
            if bad:
                print("      attr FAIL: window cells != P2E expectation %s" % bad[:6]); fails += 1
    # (d) saturation: imp at 0.4 cell with the wall right behind at x = 4 -> hv 128, drawn rows within 0..95
    for x in range(7, 12): map_set(m, x, 7, 0)
    map_set(m, 4, 7, 1)
    wh = wall_height_engine(m, 0.4)
    set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m)
    set_thing(m, 0, 1, 3.9, 7.5); call(m, "render"); out = buf(m); v = vis_entries(m)
    top, bot, cols = silhouette(m)
    hud = bytes(m.memory[0x4000 + 0x0800 + 0x0300: 0x4000 + 0x0800 + 0x0300 + 32])         # pixel row 104 (HUD area) untouched by BUF
    print("saturation d=0.4: wall_h %d hv %d rows %s..%s cols %s..%s nvis %d" % (wh, v[0]["hv"] if v else -1, top, bot, min(cols) if cols else None, max(cols) if cols else None, len(v)))
    if not (v and v[0]["hv"] == 128 and wh == 128 and top is not None and top >= 0 and bot <= 95 and len(cols) > 20): print("FAIL saturation"); fails += 1
    map_set(m, 4, 7, 0)
    # (e) occlusion: barrel behind the wall at x = 7 (restored) draws nothing
    map_set(m, 7, 7, 1)
    set_player(m, 3.5, 7.5, 0); clear_things(m); call(m, "render"); ref = buf(m); a0 = attrs(m)
    set_thing(m, 0, 21, 8.5, 7.5); call(m, "render"); cols, pix = changed_columns(ref, buf(m))
    print("occluded barrel: changed pixels %d attr changed %s" % (len(pix), attrs(m) != a0))
    if pix or attrs(m) != a0: print("FAIL occlusion"); fails += 1
    # (g) start view after 3 s of AI (~27 frames at 9 fps): every alive enemy within the FOV (|bearing| <= 33 deg) and <= 6 cells is in vis
    m2 = machine(); call(m2, "init_game"); fake_input(m2, 0)
    for _ in range(27): call(m2, "render"); call(m2, "game_tick")
    p = bytes(m2.memory[SYM["posx"]:SYM["posx"] + 5]); px, py, ang = p[1] + p[0] / 256, p[3] + p[2] / 256, p[4]
    call(m2, "render"); v = vis_entries(m2); seen = {e["thing"] for e in v}
    missing = []
    for i in range(16):
        r = bytes(m2.memory[SYM["things"] + 8 * i: SYM["things"] + 8 * i + 8])
        if r[0] in (1, 2) and r[5] != 3:
            dx, dy = r[2] + r[1] / 256 - px, r[4] + r[3] / 256 - py
            dist = math.hypot(dx, dy); bearing = (math.degrees(math.atan2(dy, dx)) - ang * 360 / 256 + 180) % 360 - 180
            infov = abs(bearing) <= 30 and dist <= 6 and dist >= 0.3
            print("  enemy %d type %d state %d at %.2f,%.2f dist %.2f bearing %.0f deg -> %s" % (i, r[0], r[5], dx + px, dy + py, dist, bearing, "in vis" if i in seen else "not in vis"))
            if infov and i not in seen: missing.append(i)
    print("after 27 ticks: player %.2f %.2f angle %d health %d; vis %s; FOV enemies missing: %s" % (px, py, ang, m2.memory[SYM["health"]], v, missing))
    if missing: print("FAIL enemies in FOV not visible"); fails += 1
    print("RESULT", "PASS" if not fails else "FAIL %d" % fails)
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
