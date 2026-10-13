#!/bin/bash
# The wrapper's old name, kept for callers outside this repo: scripts/py is the wrapper.
#
#   bash "${CLAUDE_PLUGIN_ROOT}/scripts/respeak-py.sh" respeak-measure.py doc.md --fail-on error
RESPEAK_PY_AS=respeak-py.sh exec "$(cd "$(dirname "$0")" && pwd)/py" "$@"
