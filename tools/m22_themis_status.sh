#!/bin/bash
# m22_themis_status.sh - read-only: did Themis r2 run? (launch log, answer, review file)
cd ~/work/killemall
date -u +%H:%MZ
echo "== launch log"
cat build/m22_themis_r2_launch.log
W=$HOME/.hermes/profiles/themis/work/killemall-m22-20261028
echo "== workspace"
ls -la "$W"
echo "== REVIEW-r2.md"
cat "$W/REVIEW-r2.md"
