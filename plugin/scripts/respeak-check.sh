#!/bin/bash
# Gate, and optionally verify, a set of Markdown files from the committed
# configuration: the style check, run by hand or in CI. No hook runs it.
#
#   respeak-check.sh [--verify <git-ref>] [--prose-keys KEYS] [--allow-strings]
#                    [--allow-restructure] [--quiet] [FILE...]
#
# With no FILE, every Markdown file git knows about under the current
# directory is checked: tracked files plus untracked files that are not
# ignored, so a new page is gated before its first commit. The project's
# gate.include and gate.exclude decide which of them apply, so an excluded
# file reports "skipped", never "blocked".
#
# --verify REF  For each file that differs from REF, also require the edit
#               to be meaning-invariant (scripts/respeak-verify-edit.py):
#               headings, block structure, links, fenced code, inline code,
#               and numbers unchanged. Files absent from REF are new and are
#               not verified. What the verifier may relax comes from each
#               file's resolved configuration, `editorial_pass`:
#               `restructure: apply` passes --allow-restructure,
#               `verify.prose_keys` passes --prose-keys, `verify.allow_strings`
#               passes --allow-strings, and `verify.paths` (git pathspecs,
#               read from the project layer) names the non-Markdown files
#               (page generators, data YAML) that are verified as well, though
#               never gated. --prose-keys, --allow-strings, and
#               --allow-restructure set the same things for one run, for every
#               file, on top of the configuration.
#
# RESPEAK_CONFIG and the session provider (CLAUDE_CODE_SESSION_ID,
# XDG_STATE_HOME) are ignored here on purpose: this command answers what the
# committed configuration says, not what one session or one shell chose.
# Every gate.* key comes from the plugin defaults and the committed project
# file (its scopes included), so a folder file or an ignored local file
# cannot soften the verdict either; each key dropped from another layer is
# named in the report. A file the gate cannot judge is an ERROR, never a
# pass: no python, a resolver failure, a measure setup error, or a measure
# past RESPEAK_GATE_DEADLINE seconds (default 15). A file over
# RESPEAK_GATE_MAX_BYTES (default 2097152) blocks as too large to gate.
# Exit 0 = every file allowed and verified; 1 =
# at least one block, error, or verification failure; 2 = usage or setup
# error, a git failure (the run stops at the first, with its line), or the
# per-file counts do not add up to the files named.
# bash 3.2 compatible.
set -u
unset RESPEAK_CONFIG CLAUDE_CODE_SESSION_ID XDG_STATE_HOME 2>/dev/null || true
script_dir="$(cd "$(dirname "$0")" && pwd)"
RESPEAK_PY=""; RESPEAK_PY_STD=""
. "$script_dir/respeak-python.sh"
[ -n "$RESPEAK_PY" ] || { echo "respeak-check: no python3 with PyYAML found; set RESPEAK_PYTHON or install PyYAML" >&2; exit 2; }
export CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$script_dir/.." && pwd)}"
resolver="$script_dir/respeak-config.py"

ref=""; quiet=0; files=(); cli_keys=""; cli_strings=0; cli_restructure=0
while [ $# -gt 0 ]; do
  case "$1" in
    --verify) [ $# -ge 2 ] || { echo "respeak-check: --verify needs a git ref" >&2; exit 2; }; ref="$2"; shift 2 ;;
    --prose-keys) [ $# -ge 2 ] || { echo "respeak-check: --prose-keys needs a key list" >&2; exit 2; }; cli_keys="$2"; shift 2 ;;
    --allow-strings) cli_strings=1; shift ;;
    --allow-restructure) cli_restructure=1; shift ;;
    --quiet) quiet=1; shift ;;
    -h|--help) sed -n '2,42p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    --*) echo "respeak-check: unknown option $1" >&2; exit 2 ;;
    *) files+=("$1"); shift ;;
  esac
done
named="${#files[@]}"
if [ "${#files[@]}" -eq 0 ]; then
  git rev-parse --show-toplevel >/dev/null 2>&1 || { echo "respeak-check: not in a git repository; name the files to check" >&2; exit 2; }
  while IFS= read -r f; do [ -n "$f" ] && files+=("$f"); done < <(git ls-files --cached --others --exclude-standard -- '*.md' '*.markdown' '*.mdx' 2>/dev/null | sort -u)
fi
[ "${#files[@]}" -gt 0 ] || { echo "respeak-check: nothing to check"; exit 0; }
if [ -n "$ref" ]; then git rev-parse --verify --quiet "$ref^{commit}" >/dev/null || { echo "respeak-check: unknown git ref $ref" >&2; exit 2; }; fi
launch_dir="$(pwd -P)"

# The verifier's leniencies for one file, one flag per line, from the
# file's resolved `editorial_pass`. A resolver failure yields no flags: the
# strict verdict, never a skipped check.
verify_flags() {
  "$RESPEAK_PY" "$resolver" resolve --for "$1" --launch-dir "$launch_dir" --format json 2>/dev/null \
    | "$RESPEAK_PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
ep = d.get("editorial_pass") or {}
v = ep.get("verify") or {}
keys = v.get("prose_keys") or []
if isinstance(keys, list) and keys:
    print("--prose-keys=" + ",".join(str(k) for k in keys))
if v.get("allow_strings") is True:
    print("--allow-strings")
if ep.get("restructure") == "apply":
    print("--allow-restructure")
' 2>/dev/null
}

# The non-Markdown files the project asks to have verified
# (editorial_pass.verify.paths): only with --verify, and only when the
# file list was not given by hand.
vonly=(); globs=()
if [ -n "$ref" ] && [ "$named" -eq 0 ]; then
  while IFS= read -r g; do [ -n "$g" ] && globs+=("$g"); done < <("$RESPEAK_PY" "$resolver" resolve --for "$launch_dir" --launch-dir "$launch_dir" --format json 2>/dev/null | "$RESPEAK_PY" -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for g in ((d.get("editorial_pass") or {}).get("verify") or {}).get("paths") or []:
    print(g)
' 2>/dev/null)
  if [ "${#globs[@]}" -gt 0 ]; then
    while IFS= read -r f; do
      case "$f" in ""|*.md|*.markdown|*.mdx) continue ;; esac
      vonly+=("$f")
    done < <(git ls-files --cached --others --exclude-standard -- "${globs[@]}" 2>/dev/null | sort -u)
  fi
fi

say() { [ "$quiet" -eq 1 ] || echo "$*"; }
# gate_one keeps the resolver's stderr to itself, so its exit 3 asks the
# resolver once more for its reason; a `git failed` line is a failure of the
# whole run, never one file's error (review ADV11-2).
git_failure() {
  "$RESPEAK_PY" "$resolver" gate --for "$1" --committed 2>&1 >/dev/null | grep -m1 'respeak-config: git failed'
}
tmp="$(mktemp 2>/dev/null)" || { echo "respeak-check: mktemp failed" >&2; exit 2; }; trap 'rm -f "$tmp" "$tmp.before" "$tmp.cfg"' EXIT
passed=0; skipped=0; blocked=0; errors=0; missing=0; verified=0; vfailed=0

# The committed verdict for one file, its report on stdout. Exit 0 = passed
# or not Markdown; 2 = blocked; 3 = no verdict; 4 = skipped, not applicable.
gate_one() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    *.md|*.markdown|*.mdx) ;;
    *) return 0 ;;
  esac
  local decision verdict fail_on report status size max_bytes deadline
  decision="$("$RESPEAK_PY" "$resolver" gate --for "$1" --committed --write-config "$tmp.cfg" 2>/dev/null)" \
    || { echo "respeak gate: resolver failed; no verdict for $1 (committed)"; return 3; }
  verdict="$(printf '%s' "$decision" | "$RESPEAK_PY" -c '
import json, sys
d = json.load(sys.stdin)
fail_on = d.get("fail_on") if d.get("fail_on") in ("none", "warn", "error") else "error"
print(("1" if d.get("applies") else "0") + " " + fail_on)
for x in d.get("dropped") or []:
    layer, _, key = str(x).rpartition(": ")
    print("respeak gate: ignored %s %s (committed)" % (layer, key))
' 2>/dev/null)" || { echo "respeak gate: resolver output unparseable; no verdict for $1 (committed)"; return 3; }
  printf '%s\n' "$verdict" | sed '1d'
  verdict="$(printf '%s\n' "$verdict" | sed -n '1p')"
  [ "${verdict%% *}" = "1" ] || return 4
  fail_on="${verdict#* }"
  max_bytes="${RESPEAK_GATE_MAX_BYTES:-2097152}"
  case "$max_bytes" in ''|*[!0-9]*) max_bytes=2097152 ;; esac
  size="$(wc -c < "$1" 2>/dev/null | tr -d ' ')"
  if [ -n "$size" ] && [ "$size" -gt "$max_bytes" ]; then
    echo "respeak gate: $1 is too large to gate ($size bytes, over RESPEAK_GATE_MAX_BYTES=$max_bytes); split it or exclude it in gate.exclude"
    return 2
  fi
  deadline="${RESPEAK_GATE_DEADLINE:-15}"
  case "$deadline" in ''|*[!0-9]*|0) deadline=15 ;; esac
  report="$(bash "$script_dir/respeak-deadline.sh" "$deadline" "$RESPEAK_PY" "$script_dir/respeak-measure.py" "$1" \
    --fail-on "$fail_on" --config "$tmp.cfg" --corpus "$CLAUDE_PLUGIN_ROOT/corpus/banned-phrases.yaml" 2>&1 </dev/null)"
  status=$?
  if [ "$status" -eq 0 ]; then return 0; fi
  if [ "$status" -eq 1 ]; then
    echo "respeak gate: $1 failed the style gate (fail-on: $fail_on)"
    echo "$report"
    return 2
  fi
  [ "$status" -eq 124 ] && { echo "respeak gate: measure passed its $deadline s deadline (RESPEAK_GATE_DEADLINE); no verdict for $1 (committed)"; return 3; }
  echo "$report"
  echo "respeak gate: measure exited $status (setup error, not a verdict); no verdict for $1 (committed)"
  return 3
}

# Verify one file against REF when it exists there and differs.
verify_one() {
  git cat-file -e "$ref:$1" 2>/dev/null && ! git diff --quiet "$ref" -- "$1" 2>/dev/null || return 0
  git show "$ref:$1" > "$tmp.before"
  vargs=()
  while IFS= read -r a; do [ -n "$a" ] && vargs+=("$a"); done < <(verify_flags "$1")
  [ -n "$cli_keys" ] && vargs+=("--prose-keys=$cli_keys")
  [ "$cli_strings" -eq 1 ] && vargs+=(--allow-strings)
  [ "$cli_restructure" -eq 1 ] && vargs+=(--allow-restructure)
  note=""; [ "${#vargs[@]}" -gt 0 ] && note="; ${vargs[*]}"
  if "$RESPEAK_PY" "$script_dir/respeak-verify-edit.py" ${vargs[@]+"${vargs[@]}"} "$tmp.before" "$1" >"$tmp" 2>&1; then
    verified=$((verified + 1)); say "verified $1 (prose-only edit since $ref$note)"
  else
    vfailed=$((vfailed + 1)); echo "CHANGED  $1 (meaning-carrying content differs from $ref)"; sed 's/^/         /' "$tmp"
  fi
}

for f in "${files[@]}"; do
  [ -f "$f" ] || { missing=$((missing + 1)); say "missing  $f"; continue; }
  gate_one "$f" >"$tmp" 2>&1; rc=$?
  if [ "$rc" -eq 3 ] && gitfail="$(git_failure "$f")"; then
    echo "$gitfail" >&2
    echo "respeak-check: stopped at $f; a git failure spoils every file, not one" >&2
    exit 2
  elif [ "$rc" -eq 2 ]; then
    blocked=$((blocked + 1)); echo "BLOCKED  $f"; sed 's/^/         /' "$tmp"
  elif [ "$rc" -eq 4 ]; then
    skipped=$((skipped + 1)); say "skipped  $f"
  elif [ "$rc" -ne 0 ]; then
    errors=$((errors + 1)); echo "ERROR    $f"; sed 's/^/         /' "$tmp"
  else
    passed=$((passed + 1)); say "pass     $f"
  fi
  [ -n "$ref" ] && verify_one "$f"
done
for f in ${vonly[@]+"${vonly[@]}"}; do
  [ -f "$f" ] && verify_one "$f"
done
# Invariant: every file named lands in exactly one count. A file that
# slipped through every branch would otherwise read as a quiet green.
counted=$((passed + skipped + blocked + errors + missing))
if [ "$counted" -ne "${#files[@]}" ]; then
  echo "respeak-check: counted $counted of ${#files[@]} files; refusing to report" >&2
  exit 2
fi
echo "respeak-check: $passed passed, $skipped skipped, $blocked blocked, $errors errors${ref:+; $verified verified, $vfailed changed against $ref}"
[ "$blocked" -eq 0 ] && [ "$errors" -eq 0 ] && [ "$vfailed" -eq 0 ]
