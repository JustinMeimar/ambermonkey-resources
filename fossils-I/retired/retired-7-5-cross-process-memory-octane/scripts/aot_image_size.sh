#!/usr/bin/env bash
# Print the size of the embedded AOT image in a given ELF (libxul.so by
# default) as bytes on stdout. The AOT image is emitted in a .text.aot
# section but the linker folds it into .text, so we bracket it with the
# aot_image_start / aot_image_end symbols instead.
set -euo pipefail
BIN="${1:-/home/justin/spidermonkey/firefox/build-browser-release-aot/dist/bin/libxul.so}"
if ! [ -r "$BIN" ]; then
  echo "aot_image_size: cannot read $BIN" >&2
  exit 1
fi
read start end < <(nm "$BIN" 2>/dev/null | awk '
  / aot_image_start$/ {s=$1}
  / aot_image_end$/   {e=$1}
  END {if (s && e) print s, e}
')
if [ -z "${start:-}" ] || [ -z "${end:-}" ]; then
  echo "aot_image_size: aot_image_start/end symbols not found in $BIN" >&2
  exit 1
fi
echo $((16#$end - 16#$start))
