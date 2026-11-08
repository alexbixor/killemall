#!/bin/bash
# ci_check.sh - after tools/ci_build.sh: compare the fresh artefacts with tools/ci_expected_sha256.txt.
# killemall48_m25.tap is NOT in the list on purpose: the shipped tape was wrapped on 5 Nov with the mktap48.py of that day
# (code block 37,319 B); today's mktap48.py pads the code block to the full image (37,874 B).  kea48.tap (the raw engine image
# from pasmo) is byte-identical, which is the proof that matters; the wrapper difference is tracked in the release notes.
set -e
cd "$(dirname "$0")/.."
sha256sum -c tools/ci_expected_sha256.txt
echo "all expected artefacts byte-identical"
