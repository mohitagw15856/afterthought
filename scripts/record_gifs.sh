#!/usr/bin/env bash
# Record the README GIFs with vhs (https://github.com/charmbracelet/vhs).
# Each tape builds on the demo vault state left by the previous one.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
rm -rf demo-vault
for tape in compile provenance idempotent decide-review verify replay; do
  echo "recording $tape"
  vhs "docs/gifs/tapes/$tape.tape" >/dev/null
done
ls -la docs/gifs/*.gif
