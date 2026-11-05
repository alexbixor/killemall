#!/usr/bin/env python3
"""m22_themis_r2.py - launch Themis round 2 on the M2.2 implementation packet (brief = TASK-r2.md); answer -> REVIEW-r2.md path.
Client timeout 5400 s; the deliverable is REVIEW-r2.md written by Themis in the packet dir (poll by mtime)."""
import json, re, urllib.request, time, pathlib
W = pathlib.Path.home() / ".hermes/profiles/themis/work/killemall-m22-20261028"
key = re.search(r"^API_SERVER_KEY=(.+)$", (pathlib.Path.home() / ".hermes/profiles/themis/.env").read_text(), re.M).group(1).strip()
brief = (W / "TASK-r2.md").read_text()
assert "killemall-m22-20261028" in brief and "REVIEW-r2.md" in brief
req = urllib.request.Request("http://127.0.0.1:8643/v1/chat/completions", method="POST",
                             data=json.dumps({"model": "themis", "messages": [{"role": "user", "content": brief}]}).encode(),
                             headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
t0 = time.time()
try:
    j = json.load(urllib.request.urlopen(req, timeout=5400))
    out = j["choices"][0]["message"]["content"]
    (W / "ANSWER-r2.txt").write_text(out)
    print(f"done in {time.time()-t0:.0f}s usage={j.get('usage')}")
    print(out[:400])
except Exception as e:
    print(f"request ended after {time.time()-t0:.0f}s: {e!r}")
print("REVIEW-r2.md exists:", (W / "REVIEW-r2.md").exists())
