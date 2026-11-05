import sys, os
sys.path.insert(0, 'tools'); os.environ['NOTHINGS']='1'
from test48 import load_code, run_until, SYM
import z80, chk48
start, code = load_code()
cells=chk48.load_level('src/48k/gen/level48.bin')
TRAP=0x5EF0
tot_bad=0
for v in ["3.5 7.5 0","3.5 7.5 64","3.5 7.5 128","3.5 7.5 192","9.0 10.0 150","25.5 3.5 40","12.2 14.7 230","1.3 1.3 32","20.5 20.5 96"]:
    px,py,ang=[float(x) for x in v.split()]; ang=int(ang)
    m = z80.Z80Machine(); m.set_memory_block(start, code)
    m.set_memory_block(TRAP, bytes([0xC3,0xF0,0x5E]))
    m.set_memory_block(0x5EC0, bytes([0xCD])+SYM["init_game"].to_bytes(2,"little")+bytes([0xC3,0xF0,0x5E])); m.pc=0x5EC0; m.sp=65008; run_until(m,TRAP)
    ix,fx=int(px),int((px-int(px))*256); iy,fy=int(py),int((py-int(py))*256)
    m.set_memory_block(SYM["posx"], bytes([fx,ix])); m.set_memory_block(SYM["posy"], bytes([fy,iy])); m.set_memory_block(SYM["angle"], bytes([ang]))
    m.set_memory_block(SYM["things"], bytes(128)); m.set_memory_block(SYM["draw_weapon"], bytes([0xC9]))
    m.set_memory_block(0x5EC0, bytes([0xCD])+SYM["render"].to_bytes(2,"little")+bytes([0xC3,0xF0,0x5E])); m.pc=0x5EC0; m.sp=65008; run_until(m,TRAP)
    zb=[min(m.memory[SYM["zbuf"]+c],96) for c in range(64)]
    ref=[h for h,_,_,_ in chk48.ref_heights(cells,px,py,ang)]
    d=[abs(a-b) for a,b in zip(zb,ref)]
    bad=sum(1 for x in d if x>2); tot_bad+=bad
    print("view %-14s zbuf vs float ref: max |diff| %d, >2: %d, hist %s" % (v, max(d), bad, {k:d.count(k) for k in sorted(set(d))}))
print("TOTAL rays >2 off:", tot_bad)
