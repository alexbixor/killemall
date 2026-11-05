#!/usr/bin/env python3
"""m27_nex_tg.py - Telegram picture for the Next proof: 2x2 of the rendered Next frames (browser with killemall.nex highlighted,
title, game after walking, game after firing), each 704x608 -> 512x442, labels. Output build/m27_nex_tg.png"""
from PIL import Image, ImageDraw
import pathlib
B = pathlib.Path("build")
tiles = [("NextZXOS Browser: killemall.nex selected", "nexplay3_browser_sel.png"), ("killemall.nex launched: title + menu", "nexplay3_title.png"),
         ("in game, walked forward (Q)", "nexplay3_game_fwd.png"), ("after firing (SPACE x3)", "nexplay3_game_fire.png")]
W, H = 512, 442
out = Image.new("RGB", (2 * W + 12, 2 * (H + 22) + 12), (20, 20, 20)); d = ImageDraw.Draw(out)
for i, (label, f) in enumerate(tiles):
    im = Image.open(B / f).convert("RGB").resize((W, H), Image.NEAREST)
    x = 4 + (i % 2) * (W + 4); y = 4 + (i // 2) * (H + 22)
    d.text((x + 2, y + 2), label, fill=(255, 255, 255)); out.paste(im, (x, y + 18))
out.save(B / "m27_nex_tg.png"); print("wrote", B / "m27_nex_tg.png", out.size)
