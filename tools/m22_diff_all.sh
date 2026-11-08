#!/bin/bash
# m22_diff_all.sh - every source/tool file that differs from the pre-M2.2 backup (read-only)
cd ~/work/killemall
[ -d /tmp/pre22/src ] || { mkdir -p /tmp/pre22 && tar xzf build/pre_m22/src_pre_m22.tgz -C /tmp/pre22; }
for old in $(find /tmp/pre22 -type f); do
  rel=${old#/tmp/pre22/}
  if [ ! -f "$rel" ]; then echo "DELETED  $rel"; continue; fi
  if ! cmp -s "$old" "$rel"; then echo "CHANGED  $rel  ($(diff "$old" "$rel" | grep -c '^[<>]') lines)"; fi
done
for f in $(find src tools -type f -newer build/pre_m22/src_pre_m22.tgz 2>/dev/null); do
  [ -f "/tmp/pre22/$f" ] || echo "NEW      $f"
done
