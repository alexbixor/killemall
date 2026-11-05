#!/usr/bin/env python3
"""themis_launch_m25e.py <round> - launch a Themis round on the Kill'em all step-E packet. Brief = TASK-r<N>.md verbatim.
Writes answer to <packet>/ANSWER-r<N>.txt and launch log to <packet>/launch-r<N>.log. Client timeout 5400 s."""
import json, re, sys, time, urllib.request, pathlib
rnd = sys.argv[1] if len(sys.argv) > 1 else "1"
W = pathlib.Path("/home/ubuntu/.hermes/profiles/themis/work/killemall-m25e-1nov")
brief = (W / f"TASK-r{rnd}.md").read_text()
key = re.search(r"^API_SERVER_KEY=(.+)$", open("/home/ubuntu/.hermes/profiles/themis/.env").read(), re.M).group(1).strip()
log = open(W / f"launch-r{rnd}.log", "a")
print(f"{time.strftime('%H:%M:%SZ', time.gmtime())} launch r{rnd} brief {len(brief)} chars", file=log, flush=True)
req = urllib.request.Request("http://127.0.0.1:8643/v1/chat/completions", method="POST",
                             data=json.dumps({"model": "themis", "messages": [{"role": "user", "content": brief}]}).encode(),
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
t0 = time.time()
try:
    j = json.load(urllib.request.urlopen(req, timeout=5400))
    out = j["choices"][0]["message"]["content"]
    (W / f"ANSWER-r{rnd}.txt").write_text(out)
    print(f"{time.strftime('%H:%M:%SZ', time.gmtime())} done in {time.time()-t0:.0f}s usage={j.get('usage')} answer {len(out)} chars", file=log, flush=True)
    print(f"done in {time.time()-t0:.0f}s usage={j.get('usage')}")
except Exception as e:
    print(f"{time.strftime('%H:%M:%SZ', time.gmtime())} FAILED after {time.time()-t0:.0f}s: {e!r}", file=log, flush=True)
    print("FAILED", repr(e)); sys.exit(1)
