#!/bin/bash
# m22_docfix.sh - apply Themis r2b DOC D3-D6 wording to the claims log + author source-search proof (A9/C2)
set -e
cd ~/work/killemall
{
echo
echo "== Themis r2b (00:24Z 29 Oct): SIGN-OFF conditional on DOC D3-D6 wording; no BLOCK / FIX-BEFORE-USE; R1 retained =="
echo "D3 (sprite scale): Both paths use s = hv - floor(hv/4) + floor(hv/16); width uses NCTAB[s], height rounds s down to even."
echo "    Quantisation can add one 2-pixel ray column versus NCTAB[even(s)] (e.g. hv 88: s 71, hd 70, nc 24 vs 23). Cosmetic rounding."
echo "D4 (dashboard vs r1 mockup): numeric values use the normal ROM glyphs, not the mockup bold digits. This edition is pistol-only,"
echo "    so PISTOL and pointed white/yellow cartridges replace the r1 SHOTGUN/red-shell state. Bars, pills, rails, labels match."
echo "D5 (stack): the sampled Python-core call paths used 18 B below 0xFDF0, leaving 70 B above hi_end; this is NOT an exhaustive"
echo "    interrupt/menu/ROM-load stack maximum."
echo "D6 (HUD test coverage): the regression samples fill widths and selected pip rows; it does not assert every fill value/row or the"
echo "    entire pip write-set with neighbouring-cell sentinels. Themis's independent r2b probes cover fill boundaries and ammo 0..99."
echo "Residual R1 retained: full-tape ROM-loader/interrupt stack, whole-game palette lifetime, 128K TAP emulation, target-TV readability."
echo "Author source-search proof (opt_fps|FPS, executable scope):"
grep -n -i "opt_fps\|fps" src/common/*.asm src/48k/kea48.asm tools/fe_test_main.asm tools/gen48.py | sed 's/^/    /'
echo "    -> comments only (frontend.asm header, fe_test_main.asm comment); no executable reference."
} >> build/m22_status.txt
tail -16 build/m22_status.txt
