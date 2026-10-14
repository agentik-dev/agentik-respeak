#!/bin/bash
# Tests for `make install` (agentik-r1 5.2): with the `agentik` marketplace
# known, install respeak@agentik, or update it when listed; without it, print
# the line that adds the marketplace, run nothing, exit 2; a missing CLI exits
# 2. It never adds or removes a marketplace. A fake `claude`, passed as
# CLAUDE=, records its argv; a decoy `claude` first on PATH records any call
# that bypassed the variable. Bash 3.2 compatible.
#
# Run: bash tests/test_install.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"

pass=0
fail=0
check() {
  # $1 = description, $2 = expected, $3 = actual
  if [ "$2" = "$3" ]; then pass=$((pass + 1)); echo "ok   - $1"
  else fail=$((fail + 1)); echo "FAIL - $1 (expected '$2', got '$3')"; fi
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
py="$("${PYTHON:-python3}" -c 'import sys; print(sys.executable)')"
mkdir -p "$work/bin"
cat > "$work/bin/claude" <<'SH'
#!/bin/bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "plugin marketplace list --json") cat "$FAKE_MKT" ;;
  "plugin list --json") cat "$FAKE_PLUGINS" ;;
esac
exit 0
SH
chmod +x "$work/bin/claude"
mkdir -p "$work/decoy"
printf '#!/bin/sh\necho "BARE claude $*" >> "$FAKE_LOG"\nexit 1\n' > "$work/decoy/claude"
chmod +x "$work/decoy/claude"

run_install() { # $1 = marketplace list JSON, $2 = plugin list JSON, $3 = the CLAUDE to pass (default the fake)
  printf '%s\n' "$1" > "$work/mkt.json"; printf '%s\n' "${2:-[]}" > "$work/plugins.json"; : > "$work/log"
  FAKE_LOG="$work/log" FAKE_MKT="$work/mkt.json" FAKE_PLUGINS="$work/plugins.json" PATH="$work/decoy:$PATH" \
    make -s -C "$REPO_ROOT" install PYTHON="$py" CLAUDE="${3:-$work/bin/claude}" > "$work/out" 2>&1
}
calls() { grep -v -e '^plugin marketplace list --json$' -e '^plugin list --json$' "$work/log" | tr '\n' ';'; }
AGENTIK='[{"name":"other","source":"directory","path":"/elsewhere"},{"name":"agentik","source":"github","repo":"agentik-dev/agentik-commons"}]'

# 1. agentik known, the plugin absent: install it, add nothing.
run_install "$AGENTIK" '[{"id":"other@agentik","version":"1.0.0"}]'; rc=$?
check "absent: exit 0" 0 "$rc"
check "absent: install respeak@agentik" "plugin install respeak@agentik;" "$(calls)"

# 2. agentik known, the plugin listed: update it.
run_install "$AGENTIK" '[{"id":"respeak@agentik","version":"0.6.0"}]'; rc=$?
check "listed: exit 0" 0 "$rc"
check "listed: update respeak@agentik" "plugin update respeak@agentik;" "$(calls)"

# 3. agentik unknown: print the marketplace line; run nothing; exit 2.
run_install '[{"name":"other","source":"directory","path":"/elsewhere"}]'; rc=$?
check "unknown: exit 2" 2 "$rc"
check "unknown: nothing but the list ran" "" "$(calls)"
check "unknown: prints the marketplace line" 1 "$(grep -c '^  claude plugin marketplace add agentik-dev/agentik-commons$' "$work/out")"

# 4. No claude CLI at CLAUDE: exit 2, name it, run nothing.
run_install '[]' '[]' "$work/bin/no-such-claude"; rc=$?
check "missing CLAUDE: exit 2" 2 "$rc"
check "missing CLAUDE: nothing ran" "" "$(cat "$work/log")"
check "missing CLAUDE: names it" 1 "$(grep -c "no claude CLI at CLAUDE=$work/bin/no-such-claude" "$work/out")"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
