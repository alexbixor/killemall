#!/bin/bash
# deck_pad_caps.sh - READ-ONLY: joydev numbering of the Steam virtual X-Box pad (axes/buttons) + display/session facts
for ev in /sys/class/input/event*; do
  n=$(cat $ev/device/name 2>/dev/null)
  case "$n" in *X-Box*) echo "== $(basename $ev) : $n  js=$(ls $ev/device | grep -E '^js[0-9]' | tr '\n' ' ')"
    echo "abs bitmap: $(cat $ev/device/capabilities/abs)"; echo "key bitmap: $(cat $ev/device/capabilities/key)"
    echo "id: $(cat $ev/device/id/vendor):$(cat $ev/device/id/product) bus $(cat $ev/device/id/bustype)";;
  esac
done
python3 - <<'EOF'
import glob
for d in glob.glob('/sys/class/input/event*/device'):
    name=open(d+'/name').read().strip()
    if 'X-Box' not in name: continue
    def bits(s):
        words=[int(w,16) for w in s.split()][::-1]; out=[]
        for i,w in enumerate(words):
            for b in range(64):
                if w>>b&1: out.append(i*64+b)
        return out
    absn={0:'X',1:'Y',2:'Z(LT)',3:'RX',4:'RY',5:'RZ(RT)',16:'HAT0X',17:'HAT0Y'}
    keyn={304:'A',305:'B',307:'X',308:'Y',310:'TL',311:'TR',314:'SELECT',315:'START',316:'MODE',317:'THUMBL',318:'THUMBR'}
    a=bits(open(d+'/capabilities/abs').read()); k=bits(open(d+'/capabilities/key').read())
    print('joydev axis numbering :', ', '.join('%d=%s'%(i,absn.get(c,c)) for i,c in enumerate(a)))
    print('joydev button numbering:', ', '.join('%d=%s'%(i,keyn.get(c,c)) for i,c in enumerate(k)))
EOF
echo "--- session"
echo "DISPLAY in user env: $(systemctl --user show-environment | grep -E '^(DISPLAY|WAYLAND_DISPLAY)=' | tr '\n' ' ')"
xrandr --display :0 2>/dev/null | grep -E ' connected' | head -3
echo "--- emudeck zx config (how RetroArch gets launched for tapes)"
grep -rl -iE 'zxspectrum' ~/ES-DE/custom_systems ~/.emulationstation/custom_systems 2>/dev/null | head -3
grep -h -A8 -i '<name>zxspectrum' ~/ES-DE/custom_systems/es_systems.xml 2>/dev/null | grep -E 'command|extension' | cut -c1-200 | head -4
date -u +%H:%MZ
