#!/bin/bash
# m25_mocks.sh - render the M2.5 option stills (window size x sprite colour mode) + a side-by-side sheet
cd ~/work/killemall || exit 1
P=.venv/bin/python
$P tools/m25_mock.py build/m25_opt_card_128.png 64 2 0.66 card   3.5 7.5 0 5.0 7.7
$P tools/m25_mock.py build/m25_opt_mono_128.png 64 2 0.66 mono   3.5 7.5 0 5.0 7.7
$P tools/m25_mock.py build/m25_opt_core_128.png 64 2 0.66 core   3.5 7.5 0 5.0 7.7
$P tools/m25_mock.py build/m25_opt_mono_192.png 64 3 0.99 mono   3.5 7.5 0 5.0 7.7
$P tools/m25_mock.py build/m25_opt_core_192.png 64 3 0.99 core   3.5 7.5 0 5.0 7.7
$P tools/m25_mock.py build/m25_opt_mono_192_near.png 64 3 0.99 mono   3.5 7.5 0 4.4 7.6
$P tools/m25_mock.py build/m25_opt_core_192_near.png 64 3 0.99 core   3.5 7.5 0 4.4 7.6
$P - <<'EOF'
from PIL import Image, ImageDraw
import pathlib
B = pathlib.Path("build")
def sheet(names, labels, out):
    ims = [Image.open(B / n) for n in names]
    w, h = ims[0].size
    S = Image.new("RGB", (w * len(ims) + 12 * (len(ims) - 1), h + 40), (40, 40, 40))
    d = ImageDraw.Draw(S)
    for i, (im, lab) in enumerate(zip(ims, labels)):
        x = i * (w + 12); S.paste(im, (x, 40)); d.text((x + 10, 10), lab, fill=(255, 255, 255))
    S.save(B / out); print(out, S.size)
sheet(["m25_opt_card_128.png", "m25_opt_mono_128.png", "m25_opt_core_128.png"],
      ["A  M2.4 card (black boxes) 128 px", "B  mono halo, no boxes 128 px", "C  core tint + halo 128 px"], "m25_sheet_sprite.png")
sheet(["m25_opt_mono_128.png", "m25_opt_mono_192.png"], ["128 px window (now)", "192 px window (M2.5)"], "m25_sheet_window.png")
EOF
