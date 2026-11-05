#!/usr/bin/env python3
"""nx_test_game_b.py - lane N2 oracles for the edition B GAME (src/next/test_game_b.asm = main_b.asm driven by commands):
  A' engine + paging intact: the 4 N1 scenes rendered by game_frame with (1) g_draw_off = 1 (things present, nothing drawn) and
     (2) a sprite frame first, then g_draw_mask = 0 (banks paged and restored, nothing drawn): 0 differing bytes vs nx_ref_flat.
  B  sprite oracle: 6 placements of a zombie (type 2, idle) seen from the `start` camera, Python projection (the formulas of
     sprites_next.asm's header, written here from the brief) composited over the flat reference frame vs the emulator screen
     with g_draw_mask = 1 (sprites only): 0 differing bytes of 12288 per placement.
  C  game-step oracle: a scripted run of game ticks (positions + key bits per step, fire steps preceded by a full frame so the
     vis list exists) against a Python model of the same rules; health/ammo/kills/keys/level/things compared at checkpoints.
Outputs: build/night/N2_sprites.out (A'+B), build/night/N2_steps.out (C), PNGs build/night/N2_spr_<k>.png. Exit 0 = all green.
usage: timeout 580 .venv/bin/python tools/nx_test_game_b.py [--only ab|c|all]"""
import argparse, hashlib, pathlib, struct, subprocess, sys, time
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nx_nex import build_nex
from nx_run import NexRun
# lane N2: ZEsarUX 'write-memory' parses bare values as DECIMAL (bytes >= 10 land wrong with NexRun.wr's "%02X");
# values with an H suffix are hex (verified: build/night/N2_dbg3.py). nx_run.py is read-only for lane N2, so poke here.
def poke(r, addr, data):
    from nx_run import zrcp
    data = bytes(data)
    for i in range(0, len(data), 64):
        zrcp(r.s, "write-memory %d %s" % (addr + i, " ".join("%02XH" % b for b in data[i:i + 64])), 0.1)

from nx_tables import SIN, COS, RECIP
import nx_build, nx_ref
import nx_ref_flat as ref
ROOT = HERE.parent
SRC = ROOT / "src/next"
NIGHT = ROOT / "build/night"
BIN, SYM, NEX = ROOT / "build/next/test_game_b.bin", ROOT / "build/next/test_game_b.sym", ROOT / "build/next/test_game_b.nex"
CODE_BASE = 0x8000
THINGS, VIS = 0x5C00, 0x5D00
G = dict(health=0x5DB0, ammo=0x5DB1, keys=0x5DB2, kills=0x5DB3, level=0x5DB4, shield=0x5DB5, door_cool=0x5DB6, fire_cool=0x5DB7,
         wframe=0x5DB8, nvis=0x5DBB, draw_off=0x5DBC, msg=0x5DBD, freeze=0x5DC4, draw_mask=0x5DC9, keys_in=0x5A02)
KEY_FWD, KEY_FIRE, KEY_USE = 1, 16, 32
ETAB = {1: (3, 15, 10, 0, 0, 25, 10, 4), 2: (3, 15, 15, 0, 0, 25, 10, 4), 3: (3, 13, 0, 20, 6, 20, 10, 2),
        4: (6, 10, 0, 15, 8, 30, 10, 3), 5: (12, 18, 25, 0, 0, 20, 10, 4), 6: (40, 13, 35, 20, 8, 15, 10, 14)}
SPRBASE = [0, 0, 4, 18, 22, 26, 30]
ITSPR = [8, 9, 10, 11, 8, 12, 13]


def s16(v): return v - 65536 if v >= 32768 else v


def smul_shr8(a, b):
    """sign * ((|a| * |b|) >> 8) - the walker's smul_shr idiom"""
    s = -1 if (a < 0) != (b < 0) else 1
    return s * ((abs(a) * abs(b)) >> 8)


def project(tx, ty, px, py, ang):
    """the sprite projection of sprites_next.asm (brief section 3): None or (depth, c0, w, h, feet)"""
    dx, dy = tx - px, ty - py
    if not (-16 * 256 <= dx < 16 * 256) or not (-16 * 256 <= dy < 16 * 256):
        return None
    a = ang & 1023
    dirx, diry = COS[a], SIN[a]
    plx, ply = -SIN[a], COS[a]
    depth = smul_shr8(dx, dirx) + smul_shr8(dy, diry)
    if depth < 64 or depth > 4095:
        return None
    R = 2 * RECIP[depth]
    w = min(64, R >> 4)
    h = min(96, (3 * R) >> 5)
    feet = min(96, (12288 + 22 * R + 127) >> 8)
    lat = smul_shr8(dx, plx) + smul_shr8(dy, ply)
    mag = (abs(lat) * R) >> 11
    if mag > 255:
        return None
    cx = 64 + mag if lat >= 0 else 64 - mag
    c0 = cx - (w >> 1)
    if c0 >= 128 or c0 + w <= 0:
        return None
    return depth, c0, w, h, feet


def art_column_data(bank, sid):
    off = sid * 512 if sid < 18 else 8192 + 2048 + (sid - 18) * 512
    return bank[off:off + 512]


def composite(frame, zbuf, entries, bank):
    """draw vis entries (far -> near) into a copy of the frame with the asm's pixel rules"""
    out = bytearray(frame)
    for depth, c0, w, h, feet, sid in entries:
        art = art_column_data(bank, sid)
        ustep = RECIP[w]; vstep = (RECIP[h] * 24) >> 5
        top = feet - h
        rstart = max(top, 0)
        if feet - rstart <= 0:
            continue
        vacc0 = (rstart - top) * vstep
        cstart = max(c0, 0); cend = min(c0 + w, 128)
        uacc = (cstart - c0) * ustep
        for c in range(cstart, cend):
            if zbuf[c] > depth:
                u = (uacc >> 12) & 15
                vacc = vacc0
                for r in range(rstart, feet):
                    v = (vacc >> 11) & 31
                    p = art[u * 32 + v]
                    if p:
                        out[r * 128 + c] = p
                    vacc += vstep
            uacc += ustep
    return bytes(out)


def assemble():
    r = subprocess.run(["pasmo", "--bin", "test_game_b.asm", str(BIN), str(SYM)], cwd=SRC, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("pasmo failed:\n" + r.stdout + r.stderr)
    return BIN.read_bytes(), nx_build.read_syms(SYM)


class Game:
    """the harness: one emulator, commands through TGB_CMD"""
    def __init__(self, r, syms):
        self.r, self.s = r, syms
    def cmd(self, c, n=0, timeout=30):
        if n: poke(self.r, self.s["TGB_N"], [n])
        poke(self.r, self.s["TGB_DONE"], [0]); poke(self.r, self.s["TGB_CMD"], [c])
        ok = self.r.wait_byte(self.s["TGB_DONE"], 1, timeout=timeout)
        return ok, self.r.w16(self.s["TGB_RES"])
    def pose(self, px, py, ang):
        poke(self.r, 0x5802, struct.pack("<HHH", px & 0xFFFF, py & 0xFFFF, ang & 1023))
    def things(self, lst):
        b = bytearray(256)
        for i, (t, x, y, st, hp, tm) in enumerate(lst[:32]):
            struct.pack_into("<BHHBBB", b, i * 8, t, x & 0xFFFF, y & 0xFFFF, st, hp, tm)
        poke(self.r, THINGS, bytes(b))
    def read_things(self):
        b = self.r.rd(THINGS, 256)
        return [struct.unpack_from("<BHHBBB", b, i * 8) for i in range(32)]
    def vars(self):
        b = self.r.rd(0x5DB0, 0x1A)
        return dict(health=b[0], ammo=b[1], keys=b[2], kills=b[3], level=b[4], shield=b[5], door_cool=b[6], fire_cool=b[7], wframe=b[8], nvis=b[11], msg=b[13], freeze=b[0x14])
    def vis(self):
        n = self.r.byte(G["nvis"]); b = self.r.rd(VIS, 128)
        return [struct.unpack_from("<HhBBBB", b, i * 8) for i in range(n)]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="all")
    a = ap.parse_args(argv)
    assets = ROOT / "build/next/assets_b"
    walls = (assets / "walls.bin").read_bytes(); floors = (assets / "floors.bin").read_bytes(); bank = (assets / "sprites_b.bin").read_bytes()
    pal = nx_build.read_syms  # noqa (keep flake quiet)
    lv_img = nx_build.level_image(ROOT / "build/night/N1_level01.bin", 0)
    opts = nx_build.level_header_options(ROOT / "assets/levels/01_entry.txt"); hb = nx_build.header_bytes(opts, assets)
    code, syms = assemble()
    img = bytearray(code.ljust(16384, b"\0"))
    img[nx_build.PALETTE_ADDR - CODE_BASE:nx_build.PALETTE_ADDR - CODE_BASE + 512] = (assets / "palette.bin").read_bytes()
    img[nx_build.LEVEL_ADDR - CODE_BASE:nx_build.LEVEL_ADDR - CODE_BASE + 2048] = lv_img
    for key in ("ceil", "ftex", "ctex"):
        img[syms[nx_build.HEADER_SYMS[key]] - CODE_BASE] = hb[key]
    banks = {5: bytes(16384), 2: bytes(img), 4: nx_build.TABLES.read_bytes(), 12: floors.ljust(16384, b"\0"), 13: bank}
    for q in range(4):
        banks[8 + q] = walls[q * 16384:(q + 1) * 16384]
    build_nex(NEX, banks, pc=0x8000, sp=0x5F00)
    level_blob = bytes(lv_img[:8 + 1024 + 3 * lv_img[7]])
    pal_rgb = [(((b0 >> 5) & 7) * 255 // 7, ((b0 >> 2) & 7) * 255 // 7, ((((b0 & 3) << 1) | (b1 & 1)) * 255 // 7)) for b0, b1 in zip((assets / "palette.bin").read_bytes()[0::2], (assets / "palette.bin").read_bytes()[1::2])]
    ok_all = True
    log_ab, log_c = [], []
    def la(s): print(s, flush=True); log_ab.append(s)
    def lc(s): print(s, flush=True); log_c.append(s)
    la("nx_test_game_b %s: test_game_b.asm %d bytes (8000h..%04Xh), sprites bank md5 %s, level 01 things %d" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), len(code), CODE_BASE + len(code), hashlib.md5(bank).hexdigest()[:12], lv_img[7]))

    def render(px, py, ang):
        return ref.render_flat(level_blob, px, py, ang, nx_ref.WallTex(walls), nx_ref.FloorTex(floors), hb["ceil"], hb["ftex"], hb["ctex"], "flat")

    with NexRun(NEX) as r:
        g = Game(r, syms)
        if not r.wait_byte(syms["TGB_DONE"], 1, timeout=30):
            la("FAIL: test program did not start"); return 1
        if a.only in ("ab", "all"):
            # ---- A': engine intact with the game linked in
            for scene in ("start", "door", "corridor", "oblique"):
                px, py, ang = ref.SCENES[scene]
                exp, _, zb = render(px, py, ang)
                g.pose(px, py, ang); g.cmd(3)                     # things from the level (restart_level resets the pose: re-pose)
                g.pose(px, py, ang)
                poke(r, G["draw_off"], [1]); poke(r, G["draw_mask"], [7])
                ok, t1 = g.cmd(1); scr1 = r.screen()
                d1 = sum(1 for i in range(12288) if scr1[i] != exp[i])
                poke(r, G["draw_off"], [0]); poke(r, G["draw_mask"], [7])
                ok, t2 = g.cmd(1)                                 # a frame WITH sprites/weapon/HUD (pages banks 26/27)
                nv = r.byte(G["nvis"])
                poke(r, G["draw_mask"], [0])
                ok, t3 = g.cmd(1); scr3 = r.screen()              # paged + restored, nothing drawn -> must equal the reference
                d3 = sum(1 for i in range(12288) if scr3[i] != exp[i])
                la("A' %-8s draw_off=1: %d differing bytes (%d ticks) ; sprite frame nvis %d (%d ticks) ; draw_mask=0 after it: %d differing bytes (%d ticks) ; nextreg 56h=%s 57h=%s" % (
                    scene, d1, t1, nv, t2, d3, t3, r.nextreg(0x56).strip(), r.nextreg(0x57).strip()))
                ok_all &= (d1 == 0 and d3 == 0)
            # ---- B: six zombie placements from the start camera (3.5, 7.5, east)
            px, py, ang = ref.SCENES["start"]
            exp, _, zb = render(px, py, ang)
            places = [("ahead_1", px + 256, py), ("ahead_2", px + 512, py), ("ahead_4", px + 1024, py),
                      ("offcentre", px + 768, py - 384), ("halfhidden", 0x0880, 0x0580), ("behindwall", 0x0980, 0x0680)]
            for name, tx, ty in places:
                g.pose(px, py, ang)
                g.things([(2, tx, ty, 0, 3, 0)])
                poke(r, G["draw_off"], [0]); poke(r, G["draw_mask"], [1])
                ok, t = g.cmd(1); scr = r.screen(); vis = g.vis()
                pr = project(tx, ty, px, py, ang)
                entries = [pr + (SPRBASE[2],)] if pr else []
                want = composite(exp, zb, entries, bank)
                diffs = [i for i in range(12288) if scr[i] != want[i]]
                drawn = sum(1 for i in range(12288) if want[i] != exp[i])
                NexRun.png(scr, NIGHT / ("N2_spr_%s.png" % name), pal=pal_rgb)
                la("B %-10s zombie at (%.2f, %.2f): python %s ; asm vis %s ; sprite pixels %d ; %d differing bytes of 12288 (%d ticks)%s" % (
                    name, tx / 256, ty / 256, pr, vis, drawn, len(diffs), t, "" if not diffs else " first " + str([(i // 128, i % 128, scr[i], want[i]) for i in diffs[:4]])))
                ok_all &= not diffs
            (NIGHT / "N2_sprites.out").write_text("\n".join(log_ab) + "\nRESULT %s\n" % ("PASS" if ok_all else "FAIL"))
        if a.only in ("c", "all"):
            ok_c = run_steps(g, r, lc, render, bank)
            (NIGHT / "N2_steps.out").write_text("\n".join(log_c) + "\nRESULT %s\n" % ("PASS" if ok_c else "FAIL"))
            ok_all &= ok_c
    print("RESULT: %s" % ("ALL PASS" if ok_all else "FAILED"))
    return 0 if ok_all else 1


# ---------------------------------------------------------------- oracle C: Python model of game_b_next.asm
class Model:
    def __init__(self, level_blob):
        self.level_blob = level_blob
        self.cells = bytearray(level_blob[8:8 + 1024]); n = level_blob[7]
        self.things = [[0, 0, 0, 0, 0, 0] for _ in range(32)]
        for i in range(min(n, 32)):
            t, x, y = level_blob[1032 + 3 * i:1035 + 3 * i]
            self.things[i] = [t, x * 256 + 128, y * 256 + 128, 0, ETAB[t][0] if t < 7 else 3, 0]
        self.health, self.ammo, self.keys, self.kills, self.level, self.shield = 100, 50, 0, 0, 0, 0
        self.door_cool = self.fire_cool = self.wframe = self.freeze = self.msg = 0
        self.door_log = []; self.ticks = 0
        self.px, self.py, self.ang = 0, 0, 0
        self.vis = []; self.zbuf64 = 4095
    def cell(self, x, y):
        if not (0 <= x < 32 and 0 <= y < 32): return 1
        return self.cells[y * 32 + x]
    def ahead(self):
        a = self.ang & 1023
        def sc(v): return (v >> 1) + (v >> 3)          # arithmetic shifts as the asm (sra)
        ax = (self.px + sc(COS[a])) & 0xFFFF; ay = (self.py + sc(SIN[a])) & 0xFFFF
        return ax >> 8, ay >> 8
    def door_try(self, cx, cy, code):
        if code == 8 or code == 11:
            return self.door_open(cx, cy, code)
        need = code - 8
        if self.keys & need:
            return self.door_open(cx, cy, code)
        if self.door_cool == 0:
            self.door_cool = 25; self.msg = 1
    def door_open(self, cx, cy, code):
        if len(self.door_log) >= 16: return
        self.door_log.append((cx, cy, code)); self.cells[cy * 32 + cx] = 0
    def bump(self):
        cx, cy = self.ahead(); code = self.cell(cx, cy)
        if code < 8: return
        if code == 12:
            self.msg = 3; self.freeze = 20; return
        if code == 11: return
        self.door_try(cx, cy, code)
    def use(self):
        cx, cy = self.ahead(); code = self.cell(cx, cy)
        if code < 8 or code >= 12: return
        self.door_try(cx, cy, code)
    def hurt(self, dmg):
        if self.shield: self.shield = max(0, self.shield - dmg)
        else: self.health = max(0, self.health - dmg)
    def los(self, dx, dy):
        lx, ly = self.px, self.py
        sx, sy = dx >> 3, dy >> 3
        for _ in range(8):
            lx = (lx + sx) & 0xFFFF; ly = (ly + sy) & 0xFFFF
            if self.cell(lx >> 8, ly >> 8): return False
        return True
    def think(self, th):
        t, x, y, st, hp, tm = th; row = ETAB[t]
        dx = s16((x - self.px) & 0xFFFF); dy = s16((y - self.py) & 0xFFFF)
        # Chebyshev distance from the signed high bytes, as the asm (abs of the high byte of the 16-bit delta)
        hx = ((dx & 0xFFFF) >> 8); hy = ((dy & 0xFFFF) >> 8)
        hx = hx - 256 if hx >= 128 else hx; hy = hy - 256 if hy >= 128 else hy
        dist = max(abs(hx), abs(hy))
        if dist >= row[6]:
            th[3] = 0; return
        if dist == 0 and abs(dx) < 180 and abs(dy) < 180:
            th[3] = 2; th[5] += 1
            if th[5] >= row[5]:
                th[5] = 0; self.hurt(row[2])
            return
        if (row[7] & 2) and dist <= row[4] and self.los(dx, dy):
            th[5] += 1
            if th[5] < row[5]: th[3] = 1; return
            if th[5] == row[5]:
                th[3] = 2
                if dist <= 3 or (self.ticks & 1) == 0: self.hurt(row[3])
                return
            if th[5] - row[5] < 5: return
            th[5] = 0; th[3] = 1; return
        if th[3] != 1:
            if not self.los(dx, dy): th[3] = 0; return
            th[3] = 1
        th[5] = 0
        def step_axis(d):
            if d < 0: return row[1]
            if d < row[1]: return 0
            return -row[1]
        nx = (x + step_axis(dx)) & 0xFFFF
        if self.cell(nx >> 8, y >> 8) == 0: th[1] = nx
        ny = (y + step_axis(dy)) & 0xFFFF
        if self.cell(th[1] >> 8, ny >> 8) == 0: th[2] = ny
    def fire(self):
        if self.fire_cool or self.ammo == 0: return
        self.ammo -= 1; self.fire_cool = 12; self.wframe = 1
        for depth, c0, w, h, feet, idx in reversed(self.vis):
            if c0 <= 65 and c0 + w >= 63 and self.zbuf64 > depth:
                th = self.things[idx]
                if th[0] >= 7 or th[3] == 3: continue
                th[4] -= 1
                if th[4] == 0: th[3] = 3; self.kills += 1
                else: th[3] = 1
                return
    def tick(self, keys):
        if self.freeze:
            self.freeze -= 1
            if self.freeze == 0:
                if self.msg == 3:
                    self.level = 0
                else:
                    self.health, self.ammo, self.keys, self.shield = 100, 50, 0, 0
                self.restart()
            return
        if keys & KEY_FWD: self.bump()
        if self.freeze: return
        if keys & KEY_USE: self.use()
        if keys & KEY_FIRE: self.fire()
        for th in self.things:
            if 0 < th[0] < 7 and th[3] != 3: self.think(th)
        for th in self.things:
            if 16 <= th[0] < 21:
                if (((th[1] - self.px + 128) & 0xFFFF) >> 8) == 0 and (((th[2] - self.py + 128) & 0xFFFF) >> 8) == 0:
                    t = th[0]; th[0] = 0
                    if t == 16: self.health = min(100, self.health + 25)
                    elif t == 17: self.ammo = min(99, self.ammo + 20)
                    elif t == 20: self.shield = min(100, self.shield + 50)
                    else: self.keys |= (t - 17)
        if self.door_cool: self.door_cool -= 1
        if self.fire_cool:
            self.fire_cool -= 1
            if self.fire_cool == 7: self.wframe = 0
        if self.health == 0:
            self.msg = 2; self.freeze = 20
    def restart(self):
        for cx, cy, code in self.door_log: self.cells[cy * 32 + cx] = code
        self.door_log = []
        blob = self.level_blob; n = blob[7]
        self.things = [[0, 0, 0, 0, 0, 0] for _ in range(32)]
        for i in range(min(n, 32)):
            t, x, y = blob[1032 + 3 * i:1035 + 3 * i]
            self.things[i] = [t, x * 256 + 128, y * 256 + 128, 0, ETAB[t][0] if t < 7 else 3, 0]
        self.door_cool = self.fire_cool = self.wframe = self.freeze = self.msg = 0
        self.vis = []
    def build_vis(self):
        ent = []
        for i, th in enumerate(self.things):
            if th[0] == 0: continue
            pr = project(th[1], th[2], self.px, self.py, self.ang)
            if pr: ent.append(pr + (i,))
        ent.sort(key=lambda e: -e[0])     # far -> near; the asm inserts before the first entry with depth <= new (stable for ties)
        self.vis = ent[:16]


def run_steps(g, r, lc, render, bank):
    """oracle C: scripted run. Each step = (px, py, ang, keys). The player walks (teleports along a path) from the start to the
    imp at (3, 2), shoots it (3 shots, 12-step cooldown), walks to the door at x=15 (row 3), opens it, picks up the ammo at
    (22, 2), walks back west, down the corridor to the health at (8, 29)... (level 01) and touches the exit at (23, 29)."""
    lv = bytes(nx_build.level_image(ROOT / "build/night/N1_level01.bin", 0))
    blob = lv[:8 + 1024 + 3 * lv[7]]
    m = Model(blob); m.level_blob = blob
    # path way-points (cells) and keys; linear interpolation 0.15 cell/step like the 48K movement
    def walk(path, keys=KEY_FWD):
        out = []
        for (x0, y0), (x1, y1) in zip(path, path[1:]):
            n = max(1, int(round(max(abs(x1 - x0), abs(y1 - y0)) / 0.15)))
            for k in range(1, n + 1):
                out.append((x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n, keys))
        return out
    import math
    steps = []
    def ang_to(x0, y0, x1, y1):
        return int(round(math.atan2(y1 - y0, x1 - x0) / (2 * math.pi) * 1024)) & 1023
    # 1: from (3.5, 7.5) north to (3.5, 4.0): the imp at (3.5, 2.5) ahead; 2: fire 3 times with 12 steps between shots
    seg = walk([(3.5, 7.5), (3.5, 4.5)])
    for x, y, k in seg: steps.append((x, y, 768, k))
    for i in range(40):
        steps.append((3.5, 4.5, 768, KEY_FIRE if i % 13 == 0 else 0))
    # 3: east along row 3 to the door at x=15 (door cell (15,3)); bump opens it; through to the ammo at (22, 2)
    seg = walk([(3.5, 4.5), (3.5, 3.5), (14.2, 3.5)])
    for x, y, k in seg: steps.append((x, y, 0, k))
    for i in range(3): steps.append((14.4, 3.5, 0, KEY_FWD))
    seg = walk([(14.4, 3.5), (16.5, 3.5), (22.5, 2.5)])
    for x, y, k in seg: steps.append((x, y, 0, k))
    # 4: back west, down to the corridor row 13, to the health at (8, 29) via (8,13)... (walls: row 12 is C..C up to x=15)
    seg = walk([(22.5, 2.5), (16.5, 3.5), (16.5, 13.5), (3.5, 13.5), (3.5, 22.5), (8.5, 22.5), (8.5, 29.5)])
    for x, y, k in seg: steps.append((x, y, 0, k))
    # 5: east to (17, 29), the exit at (23, 29) is inside the H room: door R at (23,27) needs the red key (not collected) -> NEED A KEY
    seg = walk([(8.5, 29.5), (17.5, 29.5), (17.5, 26.5), (23.5, 26.5)])
    for x, y, k in seg: steps.append((x, y, 0, k))
    for i in range(5): steps.append((23.5, 26.3, 256, KEY_FWD))
    while len(steps) < 300: steps.append((23.5, 26.3, 256, 0))
    steps = steps[:300]
    lc("oracle C: %d scripted steps (teleport path + key bits), checkpoints at 50/100/150/200/250/300" % len(steps))
    g.cmd(3)                              # fresh level in the emulator
    poke(r, G["draw_off"], [0]); poke(r, G["draw_mask"], [1])
    ok = True
    for n, (x, y, ang, keys) in enumerate(steps, 1):
        px, py = int(round(x * 256)), int(round(y * 256))
        m.px, m.py, m.ang = px, py, ang
        g.pose(px, py, ang)
        if keys & KEY_FIRE:
            # a rendered frame first: the vis list and ZBUF the pistol uses
            g.cmd(1)
            exp, _, zb = render(px, py, ang)
            m.build_vis(); m.zbuf64 = zb[64]
            av = g.vis(); mv = [(e[0], e[1], e[2], e[3], e[4], e[5]) for e in m.vis]
            if av != mv:
                lc("step %d: vis list differs: asm %s model %s" % (n, av, mv)); ok = False
        poke(r, G["keys_in"], [keys])
        m.ticks = r.w16(0x5808)           # the ranged miss rule reads bit 0 of ticks (no ranged enemy in level 01)
        g.cmd(2, 1)
        m.tick(keys)
        if n % 50 == 0 or n == len(steps):
            av = g.vars(); at = g.read_things()
            mt = [tuple(t) for t in m.things]
            same_vars = all(av[k] == getattr(m, k) for k in ("health", "ammo", "keys", "kills", "level", "shield"))
            same_things = [tuple(t) for t in at] == mt
            lc("step %3d pose (%.2f, %.2f, %d) keys %02X | asm health %d ammo %d keys %d kills %d level %d shield %d msg %d | model health %d ammo %d keys %d kills %d level %d shield %d msg %d | vars %s things %s" % (
                n, x, y, ang, keys, av["health"], av["ammo"], av["keys"], av["kills"], av["level"], av["shield"], av["msg"],
                m.health, m.ammo, m.keys, m.kills, m.level, m.shield, m.msg, "SAME" if same_vars else "DIFF", "SAME" if same_things else "DIFF"))
            if not same_things:
                for i, (ta, tm) in enumerate(zip(at, mt)):
                    if tuple(ta) != tm: lc("   thing %d asm %s model %s" % (i, ta, tm))
            ok &= same_vars and same_things
    return ok


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
