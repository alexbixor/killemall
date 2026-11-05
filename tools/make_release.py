#!/usr/bin/env python3
"""make_release.py - M2.7 (3 Nov 2026): ONE forwardable package for every machine (Alex: 'one distribution for all three systems,
48k, 128k, Next ... make it so it is easy for me to send him the game!').
Builds build/release/killemall-<version>.zip containing
  KILLEMALL/killemall.nex         Spectrum Next: open it in the NextZXOS Browser (one click). 128K edition inside until M3.
  KILLEMALL/killemall48.tap       48K edition  (any 48K/128K Spectrum with DivMMC/esxDOS, or an emulator): LOAD "" / Browser
  KILLEMALL/killemall128.tap      128K edition (AY music; 128K/+2/+3/Next in 128 mode, or an emulator)
  KILLEMALL/README.txt            what to copy where, keys, known limits, feedback line
  KILLEMALL/SHA256SUMS            checksums of the three game files
Inputs (must already be built and gate-green: tools/m25_gates.sh exit 0): build/killemall48_m25.tap, build/killemall128_m2.tap,
build/killemall128.nex (tools/mknex.py). The version string goes into the zip name and the README.
usage: make_release.py <version>      e.g. make_release.py 0.27.0"""
import sys, pathlib, hashlib, zipfile, time, subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
FILES = {"killemall.nex": ROOT / "build/killemall128.nex", "killemall48.tap": ROOT / "build/killemall48_m25.tap",
         "killemall128.tap": ROOT / "build/killemall128_m2.tap"}

README = """KILL'EM ALL  -  version {version}  ({date})
An original first-person raycaster for the ZX Spectrum 48K, 128K and Spectrum Next.
One package, three machines: same game, the graphics and sound follow the machine.

WHAT IS IN THE FOLDER
  killemall.nex      Spectrum Next (real machine or emulator). THIS IS THE ONE FOR THE NEXT.
  killemall48.tap    48K edition: any Spectrum 48K or later, or any emulator.
  killemall128.tap   128K edition with AY music: 128K / +2 / +3 / Next in 128 mode, or any emulator.

SPECTRUM NEXT (SD card)
  1. Unzip. Copy the whole KILLEMALL folder onto the Next's SD card (anywhere, e.g. /games/KILLEMALL).
  2. Put the card back, switch the Next on, open the Browser, go into KILLEMALL and press ENTER on killemall.nex.
  3. The title screen appears, then the menu. That is all.
  Tested in the ZEsarUX Next emulator with the standard NextZXOS SD image (boots, Browser launch, plays). This is the
  FIRST run on a real Next - that is exactly what we need you for.
  Note for this version: the Next runs the 128K edition (128K graphics + AY music) in 128 compatibility mode.
  The game speed is the same on every machine (10 game steps per second from the 50 Hz interrupt), so the Next runs
  at its full 28 MHz. Measured in the emulator: 10 frames per second on the Next, about 7 on a 128K, 9 on a 48K.
  The Next-native edition (hardware sprites, more colours) is the next milestone; it will be a drop-in file here.

48K / 128K WITH A DIVMMC OR OTHER SD INTERFACE (esxDOS)
  Copy the folder to the card, open the esxDOS browser (NMI button) and select killemall48.tap or killemall128.tap.
  Keep the whole folder together.

EMULATORS (ZEsarUX, Fuse, Speccy, Spectaculator ...)
  Open killemall48.tap (48K machine) or killemall128.tap (128K machine), or killemall.nex on a Next emulator (ZEsarUX "TBBlue").

KEYS (redefinable in the menu; Kempston joystick selectable in OPTIONS)
  Q forward    A back    O turn left    P turn right    SPACE fire    M use / open doors    Z strafe left    X strafe right
  Menu: SPACE or ENTER selects. In game: the pause menu has QUIT TO MENU.

WHAT TO LOOK FOR WHEN TESTING ON A REAL NEXT
  - Does the title screen load and the menu respond?
  - Frame rate: about 10 frames per second is expected. If it looks much faster or slower, say so.
  - Colour: one colour per 8x8 cell is normal on this hardware; enemies carry their own colour, hits flash red,
    corpses leave a dark red stain.
  - Sound: music in the menu and in the game (128K/Next), gunshot and hit effects.
  - Anything that looks wrong: please note the level, what you did, and if possible take a photo.

FEEDBACK
  Send notes to Alex (who sent you this zip). Please include the version number above.

FILES
{sums}
"""

def main():
    version = sys.argv[1]
    for name, src in FILES.items():
        if not src.exists(): sys.exit("missing input %s (%s)" % (name, src))
    out_dir = ROOT / "build/release"; out_dir.mkdir(exist_ok=True)
    zip_path = out_dir / ("killemall-%s.zip" % version)
    sums = []
    for name, src in FILES.items():
        sums.append("  %s  %8d bytes  sha256 %s" % (name.ljust(17), src.stat().st_size, hashlib.sha256(src.read_bytes()).hexdigest()[:16]))
    readme = README.format(version=version, date=time.strftime("%d %b %Y", time.gmtime()), sums="\n".join(sums))
    sha_file = "".join("%s  %s\n" % (hashlib.sha256(src.read_bytes()).hexdigest(), name) for name, src in FILES.items())
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src in FILES.items(): z.write(src, "KILLEMALL/" + name)
        z.writestr("KILLEMALL/README.txt", readme.replace("\n", "\r\n"))       # CRLF: readable on every OS incl. NextZXOS's viewer
        z.writestr("KILLEMALL/SHA256SUMS", sha_file)
    (out_dir / ("README-%s.txt" % version)).write_text(readme)
    print("wrote %s (%d bytes)" % (zip_path, zip_path.stat().st_size))
    print(subprocess.run(["unzip", "-l", str(zip_path)], capture_output=True, text=True).stdout)
    print("sha256 of the zip:", hashlib.sha256(zip_path.read_bytes()).hexdigest())

if __name__ == "__main__":
    main()
