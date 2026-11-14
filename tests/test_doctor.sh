#!/bin/bash
# Tests for scripts/respeak-doctor.sh (`make doctor`): six lines, one per
# check, against a fake `claude` on a temporary PATH. Bash 3.2 compatible.
#
# Run: bash tests/test_doctor.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
DOCTOR="$REPO_ROOT/plugin/scripts/respeak-doctor.sh"

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
pyver="$("$py" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')"
manifest="$("$py" -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$REPO_ROOT/plugin/.claude-plugin/plugin.json")"

mkdir -p "$work/bin" "$work/oldbin" "$work/cfg/respeak" "$work/proj/.claude/respeak"
cat > "$work/bin/claude" <<'SH'
#!/bin/bash
case "$*" in
  "--version") echo "9.9.9 (Claude Code)" ;;
  "plugin marketplace list --json") echo '[{"name":"other","source":"github","repo":"x/y"},{"name":"agentik","source":"github","repo":"agentik-dev/agentik-commons"}]' ;;
  "plugin list --json") echo '[{"id":"respeak@agentik","version":"0.6.0","scope":"user"}]' ;;
  *) exit 1 ;;
esac
SH
# A machine before the switch (agentik-r1 c7) knows only the old marketplace and ID.
old_mkt="claude-code-respeak"
cat > "$work/oldbin/claude" <<SH
#!/bin/bash
case "\$*" in
  "--version") echo "9.9.9 (Claude Code)" ;;
  "plugin marketplace list --json") echo '[{"name":"$old_mkt","source":"directory","path":"/src/respeak"}]' ;;
  "plugin list --json") echo '[{"id":"respeak@$old_mkt","version":"0.6.0","scope":"user"}]' ;;
  *) exit 1 ;;
esac
SH
chmod +x "$work/bin/claude" "$work/oldbin/claude"
printf 'narrative: {default_mode: technical}\nno_such_key: 1\n' > "$work/proj/.claude/respeak/config.yaml"

run_doctor() { # $1 = PATH
  (cd "$work/proj" && env -u CLAUDE_PLUGIN_ROOT PATH="$1" HOME="$work" CLAUDE_CONFIG_DIR="$work/cfg" \
    CLAUDE_PROJECT_DIR="$work/proj" RESPEAK_PYTHON="$py" RESPEAK_CACHE_DIR="$work/cache" bash "$DOCTOR")
}

# 1. A fake claude answers: the six lines, exit 0.
out="$(run_doctor "$work/bin:$(dirname "$py"):/usr/bin:/bin")"; rc=$?
check "exits 0 with a PyYAML python" 0 "$rc"
check "six lines" 6 "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
check "python line" "python: $py $pyver pyyaml=yes" "$(printf '%s\n' "$out" | sed -n 1p)"
check "claude line" "claude: 9.9.9" "$(printf '%s\n' "$out" | sed -n 2p)"
check "marketplace line agentik" "marketplace: agentik github agentik-dev/agentik-commons" "$(printf '%s\n' "$out" | sed -n 3p)"
check "plugin line respeak@agentik" "plugin: respeak@agentik 0.6.0, manifest $manifest" "$(printf '%s\n' "$out" | sed -n 4p)"
check "provider line" 1 "$(printf '%s\n' "$out" | sed -n 5p | grep -c '^provider: ')"
check "config line counts the unknown key" "config: 1 unknown keys" "$(printf '%s\n' "$out" | sed -n 6p)"

# 2. Only the old IDs: both lines name them and warn; still six lines, exit 0.
out="$(run_doctor "$work/oldbin:$(dirname "$py"):/usr/bin:/bin")"; rc=$?
check "exits 0 with the old ids" 0 "$rc"
check "six lines with the old ids" 6 "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
check "old marketplace warns" "marketplace: $old_mkt directory /src/respeak; old, the switch moves it" "$(printf '%s\n' "$out" | sed -n 3p)"
check "old id warns" "plugin: respeak@$old_mkt 0.6.0, manifest $manifest; old id, use respeak@agentik" "$(printf '%s\n' "$out" | sed -n 4p)"

# 3. No claude on PATH: claude missing, no marketplace, not installed; still exit 0.
mkdir -p "$work/nobin"
for t in bash dirname sed grep head cat env; do ln -s "$(command -v $t)" "$work/nobin/$t"; done
out="$(run_doctor "$work/nobin:$(dirname "$py")")"; rc=$?
check "exits 0 without claude" 0 "$rc"
check "claude: missing" "claude: missing" "$(printf '%s\n' "$out" | sed -n 2p)"
check "marketplace: none" "marketplace: none" "$(printf '%s\n' "$out" | sed -n 3p)"
check "plugin: not installed" "plugin: not installed" "$(printf '%s\n' "$out" | sed -n 4p)"

# 4. The plugin line names the entry whose installPath is this plugin's folder, whatever its id.
P="$REPO_ROOT/plugin"
L="$work/L"
ln -s "$P" "$L"
mkdir -p "$work/other"
fake_list() { # $1 = a new bin dir, $2 = the plugin list it prints
  mkdir -p "$1"
  printf '%s\n' "$2" > "$1/plist.json"
  cat > "$1/claude" <<SH
#!/bin/bash
case "\$*" in
  "--version") echo "9.9.9 (Claude Code)" ;;
  "plugin marketplace list --json") echo '[]' ;;
  "plugin list --json") cat "$1/plist.json" ;;
  *) exit 1 ;;
esac
SH
  chmod +x "$1/claude"
}
run_script() { # $1 = PATH, $2 = the script, the rest = more of the environment
  p="$1"; s="$2"; shift 2
  (cd "$work/proj" && env -u CLAUDE_PLUGIN_ROOT PATH="$p" HOME="$work" CLAUDE_CONFIG_DIR="$work/cfg" \
    CLAUDE_PROJECT_DIR="$work/proj" RESPEAK_PYTHON="$py" RESPEAK_CACHE_DIR="$work/cache" "$@" bash "$s")
}
line4() { printf '%s\n' "$1" | sed -n 4p; }
tail_path="$(dirname "$py"):/usr/bin:/bin"
fork="plugin: respeak@acme-tools 0.12.6-acme.1, manifest $manifest"

fake_list "$work/fork" '[{"id":"respeak@acme-tools","version":"0.12.6-acme.1","scope":"user","installPath":"'"$P"'"}]'
out="$(run_script "$work/fork:$tail_path" "$DOCTOR")"; rc=$?
check "a fork's install, by its installPath" "$fork" "$(line4 "$out")"
check "exits 0 from a fork's install" 0 "$rc"
check "six lines from a fork's install" 6 "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
out="$(run_script "$work/fork:$tail_path" "$L/scripts/respeak-doctor.sh")"
check "a fork's install, run through a link to it" "$fork" "$(line4 "$out")"
out="$(run_script "$work/fork:$tail_path" "$DOCTOR" CLAUDE_PLUGIN_ROOT="$L")"
check "a fork's install, CLAUDE_PLUGIN_ROOT a link to it" "$fork" "$(line4 "$out")"

fake_list "$work/both" '[{"id":"respeak@agentik","version":"0.6.0","scope":"user","installPath":"'"$work/other"'"},{"id":"respeak@acme-tools","version":"0.12.6-acme.1","scope":"user","installPath":"'"$P"'"}]'
out="$(run_script "$work/both:$tail_path" "$DOCTOR")"
check "the path decides, not the fixed id" "$fork" "$(line4 "$out")"

fake_list "$work/oldat" '[{"id":"respeak@'"$old_mkt"'","version":"0.6.0","scope":"user","installPath":"'"$P"'"}]'
out="$(run_script "$work/oldat:$tail_path" "$DOCTOR")"
check "the old id at this folder keeps its note" "plugin: respeak@$old_mkt 0.6.0, manifest $manifest; old id, use respeak@agentik" "$(line4 "$out")"

# 5. No entry at this folder: the fixed id, then the old id, then not installed; always exit 0.
fake_list "$work/gone" '[{"id":"respeak@agentik","version":"0.6.0","scope":"user","installPath":"'"$work/gone-folder"'"}]'
out="$(run_script "$work/gone:$tail_path" "$DOCTOR")"; rc=$?
check "an installPath that is gone: the fixed id" "plugin: respeak@agentik 0.6.0, manifest $manifest" "$(line4 "$out")"
check "exits 0 with an installPath that is gone" 0 "$rc"
fake_list "$work/gonefork" '[{"id":"respeak@acme-tools","version":"0.12.6-acme.1","scope":"user","installPath":"'"$work/gone-folder"'"}]'
out="$(run_script "$work/gonefork:$tail_path" "$DOCTOR")"; rc=$?
check "a fork at a folder that is gone: not installed" "plugin: not installed" "$(line4 "$out")"
check "exits 0 with a fork at a folder that is gone" 0 "$rc"
fake_list "$work/elsewhere" '[{"id":"respeak@acme-tools","version":"0.12.6-acme.1","scope":"user","installPath":"'"$work/other"'"}]'
out="$(run_script "$work/elsewhere:$tail_path" "$DOCTOR")"
check "a fork at another folder: not installed" "plugin: not installed" "$(line4 "$out")"
fake_list "$work/nojson" 'not json'
out="$(run_script "$work/nojson:$tail_path" "$DOCTOR")"; rc=$?
check "a list that is no JSON: not installed" "plugin: not installed" "$(line4 "$out")"
check "exits 0 with a list that is no JSON" 0 "$rc"
fake_list "$work/nopath" '[{"id":"respeak@agentik","version":"0.6.0","scope":"user"},{"id":"respeak@acme-tools","version":"1.0.0","installPath":null}]'
out="$(run_script "$work/nopath:$tail_path" "$DOCTOR")"
check "entries with no installPath: the fixed id" "plugin: respeak@agentik 0.6.0, manifest $manifest" "$(line4 "$out")"

echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
