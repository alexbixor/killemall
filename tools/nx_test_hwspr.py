#!/usr/bin/env python3
"""nx_test_hwspr.py - lane N6 (8 Nov 2026) oracles for the HWSPR_B build (HUD band + weapon as Next hardware sprites):
  static  (B) grep of the assembled main_b_n6.bin for the start-up nextreg writes (15h/19h/4Bh/43h) + a Python Z80 core run of
          game_frame x 10 with a write watch on LoRes rows 88..95 (6000h + 40*128 .. + 48*128): 0 writes in the HWSPR_B build,
          > 0 in the OFF build. Nextreg/port writes of the per-frame path counted too.             -> build/night/N6_static.out
  emu     (C) ZEsarUX headless: killemall_b_n6.nex after >= 30 frames at the start pose: sprite attributes (tbblue-get-sprite)
          vs the computed table, fire flip (M key through set-ui-io-ports), band sprites, pattern RAM vs tools/nx_hwspr_assets.py,
          LoRes rows 88..95 = view pixels, rows 0..87 identical to the OFF build's rows 0..87 with the weapon masked, nextreg 15h
          bit 0; the composed save-screen BMP (LoRes + sprites) is grabbed and the weapon/band pixels checked in it.
                                                                                                    -> N6_emu.out, N6_frame_*.png
  timing  (E) frozen start pose: ticks/frame OFF vs ON (the _fps builds, 20 frames via frames/ticks) + T-states of the per-frame
          HWSPR_B path (Z80 core, gf_hw_key..gf_hw_done with nothing changed).                       -> N6_timing.out
  clip    (F) build/night/N6_hwspr.mp4 from composed save-screen frames: start pose, walk, fire twice, take damage.
usage: .venv/bin/python tools/nx_test_hwspr.py static|emu|timing|clip|all"""
import os, re, sys, time, pathlib, subprocess
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nx_build
import nx_hwspr_assets as hw
from nx_run import NexRun, zrcp
ROOT = HERE.parent; NIGHT = ROOT / "build/night"
ON_NEX, ON_SYM, ON_BIN = ROOT / "build/next/killemall_b_n6.nex", ROOT / "build/next/main_b_n6.sym", ROOT / "build/next/main_b_n6.bin"
OFF_NEX, OFF_SYM, OFF_BIN = ROOT / "build/next/killemall_b_n6_off.nex", ROOT / "build/next/main_b_n6_off.sym", ROOT / "build/next/main_b_n6_off.bin"
ONF_NEX, OFFF_NEX = ROOT / "build/next/killemall_b_n6_fps.nex", ROOT / "build/next/killemall_b_fps.nex"
BAND0, BAND1 = 0x6000 + 40 * 128, 0x6000 + 48 * 128
ART = (ROOT / "build/next/assets_b/sprites_b.bin").read_bytes()
PAL = (ROOT / "build/next/assets_b/palette.bin").read_bytes()
PAL_RGB = [(((b0 >> 5) & 7) * 255 // 7, ((b0 >> 2) & 7) * 255 // 7, ((((b0 & 3) << 1) | (b1 & 1)) * 255 // 7)) for b0, b1 in zip(PAL[0::2], PAL[1::2])]

def hexbytes(s): return bytes.fromhex("".join(c for c in s if c in "0123456789abcdefABCDEF"))
def poke(r, addr, data): zrcp(r.s, "write-memory %d %s" % (addr, " ".join("%02XH" % b for b in data)), 0.1)
def keys(r, ks): zrcp(r.s, "set-ui-io-ports " + __import__("fe_shot").ports(ks), 0.05)

# ---------------------------------------------------------------- oracle B: static
def oracle_static(log):
    import z80
    fails = []
    code_on = ON_BIN.read_bytes(); code_off = OFF_BIN.read_bytes()
    S_on = nx_build.read_syms(ON_SYM); S_off = nx_build.read_syms(OFF_SYM)
    log("N6_static.out - oracle B %s: main_b_n6.bin %d B (code_end %04Xh, hud_end %04Xh), main_b_n6_off.bin %d B" % (
        time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), len(code_on), S_on["code_end"], S_on["hud_end"], len(code_off)))
    # B1: nextreg writes present in start / hwspr_init
    def find_nextreg(code, reg, val=None):
        hits = []
        for i in range(len(code) - 3):
            if code[i] == 0xED and code[i + 1] == 0x91 and code[i + 2] == reg and (val is None or code[i + 3] == val):
                hits.append(0x8000 + i)
        return hits
    for reg, val, what in ((0x15, 0x81, "sprites on + LoRes, S L U"), (0x19, None, "sprite clip window"), (0x4B, 0x00, "sprite transparency 0"), (0x43, 0x20, "sprite palette select"), (0x1C, 0x02, "clip index reset")):
        h_on = find_nextreg(code_on, reg, val); h_off = find_nextreg(code_off, reg, val)
        ok = bool(h_on) and (reg == 0x19 and len(h_on) >= 4 or reg != 0x19)
        hi = S_on["hwspr_init"]; he = S_on["hwspr_update"]
        inside = all(hi <= a < he for a in h_on)
        log("B1 nextreg %02Xh%s (%s): ON build %d write(s) at %s%s ; OFF build %d" % (reg, "" if val is None else ",%02Xh" % val, what, len(h_on), ",".join("%04Xh" % a for a in h_on), " (all inside hwspr_init)" if inside else "", len(h_off)))
        if not ok or not inside: fails.append("nextreg %02Xh" % reg)
    # B2: the Z80 core runs game_frame x 10 on each build; LoRes band writes watched
    def run_frames(code, S, label, n=10):
        m = z80.Z80Machine(); m.set_memory_block(0x8000, code)
        # tables bank 4 at 0000h..3FFFh (RECIP etc), level + palette as the build does
        m.set_memory_block(0x0000, nx_build.TABLES.read_bytes())
        img = bytearray(code.ljust(16384, b"\0"))
        lv = nx_build.level_image(ROOT / "build/night/N1_level01.bin", 0)
        img[0x1E00:0x2000] = PAL; img[0x3800:0x4000] = lv
        m.set_memory_block(0x8000, bytes(img))
        walls = (ROOT / "build/next/assets_b/walls.bin").read_bytes(); floors = (ROOT / "build/next/assets_b/floors.bin").read_bytes()
        paging = {6: 16, 7: 24}
        def page():            # slot 6 (C000h) = 8K bank paging[6], slot 7 (E000h) = paging[7]: walls 16..23, floors 24/25, sprites 26/27, boss 30
            for slot, bank in paging.items():
                if 16 <= bank < 24: data = walls[(bank - 16) * 8192:(bank - 15) * 8192]
                elif bank in (24, 25): data = floors.ljust(16384, b"\0")[(bank - 24) * 8192:(bank - 23) * 8192]
                elif bank in (26, 27): data = ART[(bank - 26) * 8192:(bank - 25) * 8192]
                else: data = bytes(8192)
                m.set_memory_block(0xC000 + (slot - 6) * 8192, data)
        page()
        stats = {"band": 0, "band_hud": 0, "band_eng": 0, "nextreg": [], "ports": [], "scr": 0}
        hud_lo, hud_hi = S["hud_draw"], S["hud_end"]; dw_lo, dw_hi = S["draw_weapon"], S["wclip_idle_top"]
        pend = [None]
        def on_out(p, v):
            stats["ports"].append((p, v))
            if (p & 0xFF) == 0x3B and (p >> 8) == 0x30: pass
        m.set_output_callback(on_out)
        def on_write(a, v):
            if BAND0 <= a < BAND1:
                stats["band"] += 1
                pc = m.pc
                if hud_lo <= pc < hud_hi or dw_lo <= pc < dw_hi: stats["band_hud"] += 1      # the HUD / weapon painters
                else: stats["band_eng"] += 1                                                 # the engine (view rows)
            if 0x4000 <= a < 0x5800 or 0x6000 <= a < 0x7800: stats["scr"] += 1
            m.memory[a] = v                                      # marked addresses are not written by the core itself
        m.set_write_callback(on_write)
        m.mark_addrs(0x4000, 0x3800, m.WRITE_MARK)               # kosarev z80: the write callback fires only for marked addresses
        # pose + state as start does (level 01 header: start (3,7) angle 0)
        def w8(name, v): m.set_memory_block(S[name], bytes([v & 255]))
        def w16(name, v): m.set_memory_block(S[name], bytes([v & 255, (v >> 8) & 255]))
        w16("px", lv[4] * 256 + 128); w16("py", lv[5] * 256 + 128); w16("ang", lv[6] * 4)
        m.set_memory_block(0x5B00, bytes([32, 0, 1]))                    # wb_ceil, wb_ftex, wb_ctex (N1 level 01: 32, flag 0, plaster 1)
        w8("g_draw_mask", 7); w8("g_draw_off", 0); w8("horizon_row", 48); m.set_memory_block(S["horizon_row"] - 1, b"\0")
        w8("eye", 22)
        TRAP = 0x5EF8
        m.set_memory_block(TRAP, bytes([0xC3, TRAP & 255, TRAP >> 8]))
        # the MMU writes of game_frame (nextreg 56h/57h) must page the sprite banks for build_vis/draw_vis: emulate by
        # intercepting the ED 91 56/57 opcodes: run with breakpoints at every such site
        # the kosarev core runs ED 91 / ED 92 as a 2-byte NOP and then executes the operand bytes as opcodes (N6_z80n_probe2.py):
        # trap EVERY nextreg site (ED 91 r,v = 4 bytes, 20 T ; ED 92 r = 3 bytes, 17 T), skip it, add the Z80N cost, page on 56h/57h
        sites = nextreg_sites(code)
        for a in sites: m.set_breakpoint(a)
        nreg_count = [0]
        def call(label):
            SCR = 0x5EE8
            m.set_memory_block(SCR, bytes([0xCD, S[label] & 255, S[label] >> 8, 0xC3, TRAP & 255, TRAP >> 8]))
            m.pc = SCR; m.sp = 0x5F00; used = 0
            m.set_breakpoint(TRAP)
            while m.pc != TRAP and used < 50_000_000:
                m.ticks_to_stop = 100000; m.run(); used += 100000 - m.ticks_to_stop
                if m.pc in sites:
                    reg, val, ln, tt = sites[m.pc]; nreg_count[0] += 1; used += tt
                    if reg in (0x56, 0x57): paging[6 if reg == 0x56 else 7] = (m.a if val is None else val); page()   # ED 92: value in A
                    m.pc += ln
            m.clear_breakpoint(TRAP)
            assert m.pc == TRAP, "%s did not return (pc=%04X)" % (label, m.pc)
            return used
        call("setup_camera_b")
        t = [call("game_frame") for _ in range(n)]
        scr = bytes(m.memory[0x4000:0x5800]) + bytes(m.memory[0x6000:0x7800])   # rows 0..47 at SCR_TOP, 48..95 at SCR_BOT
        return stats, t, scr, m
    st_on, t_on, scr_on, m_on = run_frames(code_on, S_on, "ON")
    st_off, t_off, scr_off, m_off = run_frames(code_off, S_off, "OFF")
    log("B2 Z80 core, 10 x game_frame at the level 01 start pose (draw_mask 7): writes to LoRes rows 88..95 (SCR_BOT 6000h + 40*128 .. + 48*128; the brief's '6000h+88*128' is the same band, rows 48..95 live at 6000h):")
    log("   by the HUD painters / draw_weapon (PC in hud_draw..hud_end or draw_weapon..wclip tables): ON %d (must be 0: the band is a sprite pattern buffer now) ; OFF %d (> 0: the LoRes band)" % (st_on["band_hud"], st_off["band_hud"]))
    log("   by the engine (walk_frame_b: view rows): ON %d (wb_rmax 96: 8 rows x 128 x 10 frames = 10240 view pixels) ; OFF %d (wb_rmax 88: the engine never touches the band)" % (st_on["band_eng"], st_off["band_eng"]))
    log("   screen writes total ON %d OFF %d" % (st_on["scr"], st_off["scr"]))
    if st_on["band_hud"] != 0 or st_off["band_hud"] == 0 or st_off["band_eng"] != 0 or st_on["band_eng"] != 10240:
        fails.append("band writes ON hud %d eng %d / OFF hud %d eng %d" % (st_on["band_hud"], st_on["band_eng"], st_off["band_hud"], st_off["band_eng"]))
    log("B2 ON build: port writes %d (303Bh/5Bh pattern uploads of the first HUD paint: %d, others %d) ; ON ticks/frame (core T) %s" % (
        len(st_on["ports"]), sum(1 for p, v in st_on["ports"] if (p & 0xFF) in (0x3B, 0x5B)), sum(1 for p, v in st_on["ports"] if (p & 0xFF) not in (0x3B, 0x5B)), [round(x / 1000) for x in t_on[:4]]))
    log("B2 OFF build: port writes %d ; OFF frames (core T, k) %s" % (len(st_off["ports"]), [round(x / 1000) for x in t_off[:4]]))
    # band of the ON screen must be view pixels (planes/walls), i.e. not the band colour 226 everywhere, and rows 0..87 equal OFF w/o weapon
    on_band = scr_on[88 * 128:96 * 128]; off_band = scr_off[88 * 128:96 * 128]
    log("B2 ON LoRes rows 88..95 (core): %d distinct colours, 226 (band colour) occurrences %d of 1024 ; OFF rows 88..95: %d distinct, 226 x %d" % (
        len(set(on_band)), on_band.count(226), len(set(off_band)), off_band.count(226)))
    d = sum(1 for i in range(88 * 128) if scr_on[i] != scr_off[i])
    log("B2 ON rows 0..87 vs OFF rows 0..87 (core frames, weapon drawn in both: the OFF pistol is software, the ON one a sprite): %d differing bytes (expected: the pistol pixels + its clipped columns)" % d)
    # hw_dirty / pattern uploads: the first frame uploads all 8 band patterns (2 x 128 x 8 = 2048 outs + 8 index outs), later frames 0
    log("B2 HW_PBUF (7C00h..7FFFh) after 10 frames: %d bytes = band colour, %d non-zero ; hw_dirty %d hw_key %d" % (
        bytes(m_on.memory[0x7C00:0x8000]).count(226), sum(1 for b in m_on.memory[0x7C00:0x8000] if b), m_on.memory[S_on["hw_dirty"]], m_on.memory[S_on["hw_key"]]))
    (NIGHT / "N6_static_scr_on.bin").write_bytes(scr_on); (NIGHT / "N6_static_scr_off.bin").write_bytes(scr_off)
    log("RESULT %s" % ("PASS" if not fails else "FAIL: " + "; ".join(fails)))
    return not fails

# ---------------------------------------------------------------- oracle E (T-state part): Z80 core on gf_hw_key..gf_hw_done
def nextreg_sites(code, base=0x8000):
    """every Z80N nextreg site in the binary: addr -> (reg, value or None, length, T-states). ED 91 r,v (4 B, 20 T), ED 92 r (3 B, 17 T)"""
    sites = {}
    i = 0
    while i < len(code) - 2:
        if code[i] == 0xED and code[i + 1] == 0x91 and i + 3 < len(code): sites[base + i] = (code[i + 2], code[i + 3], 4, 20); i += 4
        elif code[i] == 0xED and code[i + 1] == 0x92: sites[base + i] = (code[i + 2], None, 3, 17); i += 3
        else: i += 1
    return sites

def tstates_hw_path(log):
    import z80
    code = ON_BIN.read_bytes(); S = nx_build.read_syms(ON_SYM)
    m = z80.Z80Machine(); m.set_memory_block(0x8000, code)
    S_hw = S["gf_hw_key"]
    sites = nextreg_sites(code)
    # the key path: gf_hw_key .. the `call nz,hwspr_update` .. 2 MMU nextregs (skipped) .. build_vis .. hud_draw .. hw_dirty test
    # measure only the HWSPR_B-specific instructions: run from gf_hw_key to the first nextreg 56h (ED 91 56) with the key unchanged,
    # then from the `ld a,(hw_dirty)` test to gf_hw_done with hw_dirty = 0. nextreg sites are trapped (the core has no Z80N) and
    # charged 20 T (ED 91) / 17 T (ED 92).
    def run(a0, a1, setup):
        setup(); m.pc = a0; m.sp = 0x5F00; used = 0
        for a in sites:
            if a != a1: m.set_breakpoint(a)
        m.set_breakpoint(a1)
        while m.pc != a1 and used < 1_000_000:
            m.ticks_to_stop = 100000; m.run(); used += 100000 - m.ticks_to_stop
            if m.pc in sites and m.pc != a1:
                reg, val, ln, tt = sites[m.pc]; used += tt; m.pc += ln
        for a in sites: m.clear_breakpoint(a)
        m.clear_breakpoint(a1)
        assert m.pc == a1, "pc %04X" % m.pc
        return used
    i = code.index(bytes([0xED, 0x91, 0x56]), S_hw - 0x8000)
    first_mmu = 0x8000 + i
    def s1():
        m.set_memory_block(S["g_wframe"], b"\0"); m.set_memory_block(S["g_draw_mask"], b"\x07"); m.set_memory_block(S["hw_key"], b"\x06")
    t1 = run(S_hw, first_mmu, s1)
    # hw_dirty test: find `ld a,(hw_dirty)` (3A lo hi) after the call nz,hud_draw
    j = code.index(bytes([0x3A, S["hw_dirty"] & 255, S["hw_dirty"] >> 8]), S_hw - 0x8000)
    def s2(): m.set_memory_block(S["hw_dirty"], b"\0")
    t2 = run(0x8000 + j, S["gf_hw_done"], s2)
    # changed key: hwspr_update cost
    def s3(): s1(); m.set_memory_block(S["hw_key"], b"\x00")
    t3 = run(S_hw, first_mmu, s3)
    log("E T-states of the per-frame HWSPR_B path (Z80 core, nothing changed): key compare %d T + hw_dirty test %d T = %d T ; key changed (hwspr_update, 24 nextreg writes) %d T" % (t1, t2, t1 + t2, t3))
    return t1 + t2

# ---------------------------------------------------------------- oracle C: emulator
def oracle_emu(log):
    fails = []
    S = nx_build.read_syms(ON_SYM)
    def check(ok, msg):
        log(("ok   " if ok else "FAIL ") + msg)
        if not ok: fails.append(msg)
    log("N6_emu.out - oracle C %s: %s (ZEsarUX headless, ZRCP tbblue-get-sprite/pattern/palette, save-screen BMP)" % (time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()), ON_NEX.relative_to(ROOT)))
    exp_attr = []
    for (x, y), p in hw.WEAPON_SPRITES + hw.BAND_SPRITES:
        exp_attr.append([x & 255, y & 255, (x >> 8) & 1, 0xC0 | p, hw.ATTR4])
    def sprites(r):
        rows = [l_ for l_ in r.q("tbblue-get-sprite 0 12", 0.6).splitlines() if l_.strip()]
        return [list(hexbytes(l_)) for l_ in rows]
    def comp_shot(r, path):
        bmp = "/tmp/n6_shot.bmp"
        if os.path.exists(bmp): os.remove(bmp)
        r.q("save-screen " + bmp, 0.6)
        if not os.path.exists(bmp): return None
        from PIL import Image
        im = Image.open(bmp).convert("RGB")
        if path: im.save(str(path))
        return im
    def comp_px(im, col, row):
        """composed BMP (704x608: paper 512x384 at (96,112), 4 px per LoRes pixel) -> RGB at LoRes (col, row)"""
        return im.getpixel((96 + 4 * col + 1, 112 + 4 * row + 1))
    def same(a_, b_):
        """ZEsarUX expands 3-bit channels as 0,36,73,109,146,182,219,255 (x*36.5); nx_run uses x*255//7: allow 1 unit"""
        return all(abs(x - y) <= 2 for x, y in zip(a_, b_))
    with NexRun(str(ON_NEX)) as r:
        r.wait_pc_in(0x8000, 0xC000)
        poke(r, S["THINGS_B"], [0] * (S["NTHINGS_B"] * 8))   # no enemies: a stable pose for the comparisons
        t0 = time.time()
        while r.w16(0x5800) < 30 and time.time() - t0 < 20: time.sleep(0.2)
        frames = r.w16(0x5800)
        log("frames %d after %.1f s, pose px %04X py %04X ang %d" % (frames, time.time() - t0, r.w16(0x5802), r.w16(0x5804), r.w16(0x5806)))
        check(frames >= 30, "game running: %d frames" % frames)
        # C5 nextreg 15h
        v15 = r.nextreg(0x15).strip(); v4b = r.nextreg(0x4B).strip(); v43 = r.nextreg(0x43).strip()
        check(v15.upper().startswith("81"), "C5 nextreg 15h = %s (expect 81H: LoRes + sprites on, S L U, bit 0 = 1) ; 4Bh = %s (transparency 0) ; 43h = %s ; sprite clip %s" % (v15, v4b, v43, r.q("tbblue-get-clipwindow sprite").strip()))
        # C1 sprite attributes
        got = sprites(r)
        check(got == exp_attr, "C1 12 sprite attribute sets == computed table (x = 32 + 2*col, y = 32 + 2*row, attr3 = C0h|pattern, attr4 = 0Ah 2x/2x): got %s" % got)
        log("     weapon sprites 0..3 at %s patterns 0..3 ; band sprites 4..11 at %s patterns 8..15" % ([xy for xy, p in hw.WEAPON_SPRITES], [xy for xy, p in hw.BAND_SPRITES]))
        # sprite palette == LoRes palette (sample 32 entries)
        sp = r.q("tbblue-get-palette sprite first 0 256", 1.0).split(); up = r.q("tbblue-get-palette ula first 0 256", 1.0).split()
        check(len(sp) == 256 and sp == up, "sprite palette (256 x 9-bit) == ULA/LoRes palette: %d entries, %d differ" % (len(sp), sum(1 for a_, b_ in zip(sp, up) if a_ != b_)))
        # C3 pattern RAM vs the packer
        nd = []
        for e in range(8):
            got_p = hexbytes(r.q("tbblue-get-pattern %d 8 1" % e, 0.6)); nd.append(sum(1 for a_, b_ in zip(got_p, hw.weapon_pattern(ART, e))) if len(got_p) != 256 else sum(1 for a_, b_ in zip(got_p, hw.weapon_pattern(ART, e)) if a_ != b_))
        check(all(d == 0 for d in nd), "C3 pattern RAM 0..7 vs tools/nx_hwspr_assets.py weapon_pattern: diffs %s (pattern 0 = first 256 B of the idle pistol quadrant)" % nd)
        pbuf = r.rd(S["HW_PBUF"], 1024)
        nb = []
        for i in range(8):
            got_p = hexbytes(r.q("tbblue-get-pattern %d 8 1" % (8 + i), 0.6)); nb.append(sum(1 for a_, b_ in zip(got_p, hw.band_pattern(pbuf, i)) if a_ != b_) if len(got_p) == 256 else 256)
        check(all(d == 0 for d in nb), "C2 band patterns 8..15 vs HW_PBUF (7C00h) re-packed: diffs %s ; band colour 226 in HW_PBUF %d of 1024, digits %d" % (nb, pbuf.count(226), sum(1 for b in pbuf if b not in (226, 0))))
        check(all(g[1] == 32 + 2 * 88 for g in got[4:12]) and all(g[3] & 0x80 for g in got[4:12]), "C2 the 8 band sprites visible at y = %d (LoRes row 88), x = %s" % (32 + 2 * 88, [g[0] + 256 * (g[2] & 1) for g in got[4:12]]))
        # C4 LoRes frame: rows 88..95 are view pixels
        scr_on = r.screen()
        band = scr_on[88 * 128:96 * 128]
        # the reference frame of the pose (nx_ref_flat, 96 rows, flat tier) must equal the whole ON LoRes frame once the
        # weapon sprite is out of the picture (it is a sprite: the LoRes layer never holds it) and no thing is visible
        import nx_ref, nx_ref_flat as ref
        lv = nx_build.level_image(ROOT / "build/night/N1_level01.bin", 0); blob = bytes(lv[:8 + 1024 + 3 * lv[7]])
        hb = nx_build.header_bytes(nx_build.level_header_options(ROOT / "assets/levels/01_entry.txt"), ROOT / "build/next/assets_b")
        exp, _, _ = ref.render_flat(blob, r.w16(0x5802), r.w16(0x5804), r.w16(0x5806), nx_ref.WallTex((ROOT / "build/next/assets_b/walls.bin").read_bytes()), nx_ref.FloorTex((ROOT / "build/next/assets_b/floors.bin").read_bytes()), hb["ceil"], hb["ftex"], hb["ctex"], "flat")
        dref = [i for i in range(12288) if scr_on[i] != exp[i]]
        check(not dref, "C4 ON LoRes frame (128x96, things cleared) vs nx_ref_flat reference of the pose (96 rows, horizon 48): %d differing bytes -> rows 88..95 are VIEW pixels (floor colour %s), no band in the LoRes layer (226 x %d)%s" % (
            len(dref), sorted(set(band)), band.count(226), "" if not dref else " first " + str([(i // 128, i % 128, scr_on[i], exp[i]) for i in dref[:4]])))
        NexRun.png(scr_on, NIGHT / "N6_frame_on_lores.png", pal=PAL_RGB)
        (NIGHT / "N6_frame_on_lores.bin").write_bytes(scr_on)
        # composed shot
        im = comp_shot(r, NIGHT / "N6_frame_on_composed.png")
        if im is None:
            check(False, "composed save-screen BMP not produced (headless): LoRes only")
        else:
            idle = ART[8192:8192 + 1024]
            okp = badp = 0
            for x in range(32):
                for y in range(24):
                    p = idle[x * 32 + y]
                    if p:
                        if same(comp_px(im, 48 + x, 64 + y), PAL_RGB[p]): okp += 1
                        else: badp += 1
            check(badp == 0, "C1 composed BMP %dx%d: all %d opaque idle-pistol pixels show at LoRes (48..79, 64..87) in the pistol's colours (%d wrong) -> the sprite covers the LoRes grid exactly (x = 32 + 2*col, y = 32 + 2*row at 2x)" % (im.size[0], im.size[1], okp, badp))
            okb = badb = 0
            for row in range(88, 96):
                for col in range(0, 128, 3):
                    want = PAL_RGB[pbuf[(row - 88) * 128 + col]]
                    if same(comp_px(im, col, row), want): okb += 1
                    else: badb += 1
            check(badb == 0, "C2 composed BMP rows 88..95: %d sampled pixels equal the HW_PBUF band (colour + digits), %d wrong -> band sprites cover LoRes rows 88..95" % (okb, badb))
            # a view pixel under the band? the LoRes row 88..95 must be hidden: compare composed vs LoRes at a band-colour pixel
            hidden = sum(1 for col in range(0, 128, 8) if not same(comp_px(im, col, 95), PAL_RGB[scr_on[95 * 128 + col]]) or pbuf[7 * 128 + col] == scr_on[95 * 128 + col])
            log("     composed row 95: %d of 16 sampled columns differ from the LoRes layer (sprites on top) or coincide in colour" % hidden)
        # fire: M key held ~0.3 s -> g_wframe 1 for 5 steps; sprite 0..3 attr3 must show C4..C7 then back to C0..C3
        seen = set(); am0 = r.byte(S["g_ammo"])
        keys(r, ["M"]); t = time.time()
        while time.time() - t < 0.8:
            seen.add((r.byte(S["g_wframe"]), tuple(g[3] for g in sprites(r)[:4])))
        keys(r, []); time.sleep(1.2)
        after = tuple(g[3] for g in sprites(r)[:4])
        fire_seen = any(a3 == (0xC4, 0xC5, 0xC6, 0xC7) for wf, a3 in seen)      # (g_wframe and the attributes are read in two ZRCP calls, a frame may pass between them)
        check(fire_seen and after == (0xC0, 0xC1, 0xC2, 0xC3) and r.byte(S["g_ammo"]) == am0 - 1, "C1 fire: M key -> g_wframe 1 with weapon attr3 C4..C7 (fire patterns) seen %s ; after 1.2 s attr3 %s (idle) ; ammo %d -> %d" % (fire_seen, ["%02X" % v for v in after], am0, r.byte(S["g_ammo"])))
        log("     states seen during the fire: %s" % sorted(seen))
        comp_shot(r, NIGHT / "N6_frame_on_after_fire.png")
        # band digits changed (ammo) -> pattern 10 (columns 32..47 hold AMMO at 44..51? no: 44..51 spans sprites 2 and 3) uploaded
        pbuf2 = r.rd(S["HW_PBUF"], 1024)
        got_p = hexbytes(r.q("tbblue-get-pattern 10 8 1", 0.6)); got_q = hexbytes(r.q("tbblue-get-pattern 11 8 1", 0.6))
        check(pbuf2 != pbuf and got_p == hw.band_pattern(pbuf2, 2) and got_q == hw.band_pattern(pbuf2, 3), "C2 after the shot the AMMO field (columns 44..51 -> band sprites 2 and 3) changed in HW_PBUF and patterns 10/11 were re-uploaded (match %s %s)" % (got_p == hw.band_pattern(pbuf2, 2), got_q == hw.band_pattern(pbuf2, 3)))
        # frame with the weapon masked (g_draw_mask bit 1 clear) for the comparison with the OFF build
        poke(r, S["g_draw_mask"], [5]); time.sleep(0.5)
        got2 = sprites(r)
        check(all((g[3] & 0x80) == 0 for g in got2[:4]) and all(g[3] & 0x80 for g in got2[4:]), "C1 g_draw_mask bit 1 clear -> weapon sprites invisible (attr3 %s), band sprites still visible" % ["%02X" % g[3] for g in got2[:4]])
        poke(r, S["g_draw_mask"], [7]); time.sleep(0.3)
        poke(r, S["g_draw_mask"], [0]); time.sleep(0.5)
        got3 = sprites(r)
        check(all((g[3] & 0x80) == 0 for g in got3), "C1 g_draw_mask 0 -> all 12 sprites invisible")
        poke(r, S["g_draw_mask"], [7]); time.sleep(0.3)
        scr_on2 = r.screen()
    subprocess.run(["pkill", "-x", "zesarux"], capture_output=True); time.sleep(0.5)
    # OFF build, same pose, weapon masked: rows 0..87 must be identical
    S_off = nx_build.read_syms(OFF_SYM)
    with NexRun(str(OFF_NEX)) as r:
        r.wait_pc_in(0x8000, 0xC000)
        poke(r, S_off["THINGS_B"], [0] * (S_off["NTHINGS_B"] * 8))
        poke(r, S_off["g_draw_mask"], [5])
        t0 = time.time()
        while r.w16(0x5800) < 30 and time.time() - t0 < 20: time.sleep(0.2)
        time.sleep(0.5)
        scr_off = r.screen()
        NexRun.png(scr_off, NIGHT / "N6_frame_off_lores.png", pal=PAL_RGB)
        (NIGHT / "N6_frame_off_lores.bin").write_bytes(scr_off)
        comp_shot(r, NIGHT / "N6_frame_off_composed.png")
    d = [i for i in range(88 * 128) if scr_on2[i] != scr_off[i]]
    check(not d, "C4 ON rows 0..87 vs OFF build (weapon masked) rows 0..87: %d differing bytes of %d%s" % (len(d), 88 * 128, "" if not d else " first " + str([(i // 128, i % 128, scr_on2[i], scr_off[i]) for i in d[:5]])))
    off_band = scr_off[88 * 128:96 * 128]
    log("     OFF build rows 88..95: band colour 226 x %d of 1024 (the LoRes band) ; ON rows 88..95: 226 x %d" % (off_band.count(226), scr_on2[88 * 128:].count(226)))
    log("RESULT %s" % ("PASS %d checks" % 13 if not fails else "FAIL %d: %s" % (len(fails), " | ".join(fails))))
    return not fails

# ---------------------------------------------------------------- oracle E: fps
def oracle_timing(log):
    def fps_of(nex, label):
        S = nx_build.read_syms(ON_SYM)
        with NexRun(str(nex)) as r:
            r.wait_pc_in(0x8000, 0xC000)
            poke(r, S["THINGS_B"], [0] * (S["NTHINGS_B"] * 8))
            time.sleep(1.5)
            res = []
            for _ in range(3):
                f0, t0 = r.w16(0x5800), r.w16(0x5808)
                while (r.w16(0x5800) - f0) & 0xFFFF < 20: time.sleep(0.05)
                f1, t1 = r.w16(0x5800), r.w16(0x5808)
                res.append(((t1 - t0) & 0xFFFF) / float((f1 - f0) & 0xFFFF))
            v15 = r.nextreg(0x15).strip()
        subprocess.run(["pkill", "-x", "zesarux"], capture_output=True); time.sleep(0.5)
        best = min(res)
        log("E %s: %s ticks/frame over 3 x >= 20 frames (best %.2f = %.1f fps) nextreg 15h %s" % (label, ["%.2f" % v for v in res], best, 50.0 / best, v15))
        return best
    log("N6_timing.out - oracle E %s: frozen start pose (things cleared), 20-frame windows, ticks = 50 Hz" % time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()))
    t = tstates_hw_path(log)
    off = fps_of(OFFF_NEX, "OFF killemall_b_fps.nex (N5, LoRes HUD + software pistol, view 88 rows)")
    on = fps_of(ONF_NEX, "ON  killemall_b_n6_fps.nex (hardware sprites, view 96 rows)")
    off2 = fps_of(OFF_NEX, "OFF killemall_b_n6_off.nex (identity build)")
    on2 = fps_of(ON_NEX, "ON  killemall_b_n6.nex")
    log("E summary: fps OFF %.1f -> ON %.1f (%+.1f) [fps builds] ; OFF %.1f -> ON %.1f [plain builds] ; per-frame HWSPR_B path %d T when nothing changed (< 100 T %s)" % (
        50 / off, 50 / on, 50 / on - 50 / off, 50 / off2, 50 / on2, t, "ok" if t < 100 else "MISSED"))
    log("RESULT %s" % ("PASS" if t < 100 else "FAIL T-states"))
    return t < 100

# ---------------------------------------------------------------- oracle F: clip
def oracle_clip(log):
    S = nx_build.read_syms(ON_SYM)
    frames_dir = NIGHT / "N6_video_frames"; frames_dir.mkdir(exist_ok=True)
    for f in frames_dir.glob("*.png"): f.unlink()
    n = [0]
    from PIL import Image, ImageDraw
    def shot(r, caption=None):
        bmp = "/tmp/n6_clip.bmp"
        if os.path.exists(bmp): os.remove(bmp)
        r.q("save-screen " + bmp, 0.4)
        if os.path.exists(bmp):
            im = Image.open(bmp).convert("RGB").crop((96, 112, 96 + 512, 112 + 384))
            if caption:
                ImageDraw.Draw(im).text((4, 4), caption, fill=(255, 255, 255))
            im.save(str(frames_dir / ("f%04d.png" % n[0]))); n[0] += 1
    with NexRun(str(ON_NEX)) as r:
        r.wait_pc_in(0x8000, 0xC000); time.sleep(1.0)
        for _ in range(4): shot(r, "N6 HWSPR_B: ZEsarUX composed output (LoRes + hardware sprites), save-screen"); time.sleep(0.2)
        keys(r, ["Q"])
        for _ in range(8): time.sleep(0.15); shot(r)
        keys(r, []); time.sleep(0.2); shot(r)
        for k in range(2):
            keys(r, ["M"]); time.sleep(0.05)
            for _ in range(4): shot(r); time.sleep(0.05)
            keys(r, []); time.sleep(0.4); shot(r); time.sleep(0.4); shot(r)
        keys(r, ["P"])
        for _ in range(6): time.sleep(0.12); shot(r)
        keys(r, [])
        # damage: poke health (the HUD digits change -> band sprite 0 re-uploaded)
        for hp in (85, 70, 55):
            poke(r, S["g_health"], [hp]); time.sleep(0.3); shot(r)
        poke(r, S["g_msg"], [1]); time.sleep(0.3); shot(r); time.sleep(0.3); shot(r)   # NEED A KEY band colour
        poke(r, S["g_msg"], [0]); time.sleep(0.3); shot(r)
    subprocess.run(["pkill", "-x", "zesarux"], capture_output=True)
    fr = max(1, round(n[0] / 10.0))
    mp4 = NIGHT / "N6_hwspr.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fr), "-i", str(frames_dir / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", str(mp4)], check=False)
    log("F clip: %d composed frames at %d fps = %.1f s -> %s (%d bytes); frames in %s" % (n[0], fr, n[0] / float(fr), mp4.relative_to(ROOT), mp4.stat().st_size if mp4.exists() else 0, frames_dir.relative_to(ROOT)))
    return mp4.exists()

def main(argv):
    which = argv[0] if argv else "all"
    results = {}
    for name, fn, out in (("static", oracle_static, "N6_static.out"), ("emu", oracle_emu, "N6_emu.out"), ("timing", oracle_timing, "N6_timing.out"), ("clip", oracle_clip, "N6_clip.out")):
        if which not in (name, "all"): continue
        lines = []
        def log(s, lines=lines): print(s, flush=True); lines.append(s)
        subprocess.run(["pkill", "-x", "zesarux"], capture_output=True)
        try:
            results[name] = fn(log)
        except Exception as e:
            import traceback; log("EXCEPTION %r\n%s" % (e, traceback.format_exc())); results[name] = False
        (NIGHT / out).write_text("\n".join(lines) + "\n")
        subprocess.run(["pkill", "-x", "zesarux"], capture_output=True)
    print("RESULTS", results)
    return 0 if all(results.values()) else 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
