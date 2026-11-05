#!/usr/bin/env python3
"""tapdump.py - list the blocks of a .tap: flag, type, name, length, start/param, checksum ok?
usage: tapdump.py file.tap [--basic]   (--basic also detokenises the BASIC program block)"""
import sys, struct, pathlib

TOKLIST = ("RND INKEY$ PI FN POINT SCREEN$ ATTR AT TAB VAL$ CODE VAL LEN SIN COS TAN ASN ACS ATN LN EXP INT SQR SGN ABS "
           "PEEK IN USR STR$ CHR$ NOT BIN OR AND <= >= <> LINE THEN TO STEP DEF_FN CAT FORMAT MOVE ERASE OPEN_# CLOSE_# "
           "MERGE VERIFY BEEP CIRCLE INK PAPER FLASH BRIGHT INVERSE OVER OUT LPRINT LLIST STOP READ DATA RESTORE NEW "
           "BORDER CONTINUE DIM REM FOR GO_TO GO_SUB INPUT LOAD LIST LET PAUSE NEXT POKE PRINT PLOT RUN SAVE RANDOMIZE "
           "IF CLS DRAW CLEAR RETURN COPY").split()
TOKENS = {0xA5 + i: t.replace("_", " ") for i, t in enumerate(TOKLIST)}   # 0xA5..0xFF

def blocks(data):
    i = 0; out = []
    while i + 2 <= len(data):
        n = struct.unpack_from("<H", data, i)[0]; i += 2
        blk = data[i:i + n]; i += n
        out.append(blk)
    return out

def detok(prog):
    """decode a tokenised ZX BASIC program -> list of 'line text'"""
    lines = []; i = 0
    while i + 4 <= len(prog):
        ln = (prog[i] << 8) | prog[i + 1]; ll = prog[i + 2] | (prog[i + 3] << 8); i += 4
        body = prog[i:i + ll]; i += ll
        s = ""; j = 0
        while j < len(body):
            c = body[j]
            if c == 0x0E: j += 6; continue          # hidden 5-byte number
            if c == 0x0D: j += 1; continue
            if c >= 0xA5: s += " " + TOKENS.get(c, "<%02X>" % c) + " "
            elif 32 <= c < 127: s += chr(c)
            else: s += "<%02X>" % c
            j += 1
        lines.append("%d %s" % (ln, " ".join(s.split())))
    return lines

def main():
    data = pathlib.Path(sys.argv[1]).read_bytes(); want_basic = "--basic" in sys.argv
    blks = blocks(data); pending = None
    for k, b in enumerate(blks):
        flag = b[0]; chk = 0
        for x in b[:-1]: chk ^= x
        ok = "ok" if chk == b[-1] else "BAD"
        if flag == 0 and len(b) == 19:
            t = b[1]; name = b[2:12].decode("latin1"); ln = struct.unpack_from("<H", b, 12)[0]
            p1 = struct.unpack_from("<H", b, 14)[0]; p2 = struct.unpack_from("<H", b, 16)[0]
            tn = {0: "Program", 1: "NumArr", 2: "ChrArr", 3: "Code"}.get(t, "?%d" % t)
            print("%2d header %-7s name=%r len=%5d p1=%5d p2=%5d chk=%s" % (k, tn, name, ln, p1, p2, ok))
            pending = (t, ln, p1)
        else:
            print("%2d data   flag=%02X len=%5d chk=%s" % (k, flag, len(b) - 2, ok))
            if pending and pending[0] == 0 and want_basic:
                for l in detok(b[1:1 + pending[1]]): print("     BASIC:", l)
            pending = None

if __name__ == "__main__":
    main()
