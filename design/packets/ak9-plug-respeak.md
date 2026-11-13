# Packet ak9-plug-respeak: respeak gains its command, `agentik-respeak`, and every tone key names the file and line that set it

| item | value |
|---|---|
| from | agentik-hq's brief for row `ak9-plug-respeak` (hq design/15 §4 P4, P5, P9, P10; §13) and the plug's shared contract of rows ak5 to ak9, whose sections 2 to 7 are this packet's §3 |
| pin | `main` at `70089b6` (plugin 0.12.6) plus this packet's commit; branch `ak9-plug-respeak`, worktree `.claude/worktrees/ak9-plug-respeak`; nothing linked (the pyenv virtualenv is found by path) |
| wall | this worktree only; the other agentik repos read, never written. No push, `--amend`, rebase, merge, install or plugin update; no `claude` started (tests use a stub); no relay verb, no relay binary built or run outside `make`'s test harness; never a bare `make`, only the gate queue; no `DECISIONS.md` or rendered block edited |
| may touch | `plugin/bin/agentik-respeak` (new), `plugin/scripts/respeak-plug.py` (new), `tests/test_plug.py` (new), `tests/test_plugin_shape.py` only if it pins the plugin's folders, `CHANGELOG.md`, `plugin/docs/config-layers.md` (one line), the version places (`plugin/.claude-plugin/plugin.json`, the `Status:` line of `README.md` and `design/readme/source.md`, `design/readme/rendered.sha256` by `scripts/readme-fresh.sh --stamp`), `NICE_TO_HAVE.md`, this packet, a charter under `history/sittings/` |
| acceptance | §2's lines A1 to A14: the launcher's reads, each layer and line, warnings, the doctor, nothing written outside the cache, the suite's reader by hand once, the tests and doclint; the gate last |
| budget | One commit per act: the packet, the tests seen red, the code, the version. `claude-opus-5-5`, high |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id> --strict --timeout 540` in the foreground, once, last |

## 1. What the source says

The owner: "Make plugin configuration discoverable and drill down." `explain` already says which layer decided each key, and it was the model for the suite's contract; but the tool has no command on PATH, so the suite cannot ask it, and `explain` names a file, never a line. The repo keeps no `DECISIONS.md`: `CLAUDE.md` binds. The tool stays outside the self-contained plugin design: it keeps its wrapper and its PyYAML need; no `plugin/lib/`, no `install-cli`, no vendored launcher.

## 2. Rulings

0. This packet, committed first; then `tests/test_plug.py` seen red; then the code; then the records and 0.13.0, alone in the last commit that touches `plugin/`.
1. **R1.** `respeak-config.py`'s verbs, output and exits, `respeak-doctor.sh`'s lines and exit, and resolution stand; the new code loads `respeak-config.py` by its path and calls it.
2. **R2, the launcher.** `plugin/bin/agentik-respeak`, bash 3.2, found from its own resolved path. Words: `describe --json`; `describe config --json [KEY]`; `doctor` (the script's lines and exit); `doctor --json`; `config <explain|resolve|gate|validate> ...` (`respeak-config.sh`, words unchanged); `--version`; `--help`/`-h` (exit 0). Anything else: two usage lines on stderr, exit 2. It exports `CLAUDE_PLUGIN_ROOT` when unset. For the three JSON reads it sets `RESPEAK_CACHE_DIR`, when unset, to `${XDG_CACHE_HOME:-$HOME/.cache}/agentik/respeak` and starts the interpreter with `-X pycache_prefix=${XDG_CACHE_HOME:-$HOME/.cache}/agentik/pycache`.
3. **R3.** `plugin/scripts/respeak-plug.py`: the standard library at the top; the config read alone loads PyYAML. Run under `RESPEAK_PY`, else `RESPEAK_PY_STD`. With no PyYAML the config read answers `missing_need`, the wrapper's own sentence, remedy `agentik respeak doctor`, exit 2.
4. **R4, describe.** `tool` `respeak`; `needs` PyYAML (package, required), `claude` (program, optional); verbs `describe`, `doctor`, `config`, none `top`; reads `config` and `doctor`, no `status`.
5. **R5, layers.** From `Resolution.layers` for the cwd: `plugin` is `default`, `userconfig` is `install` (no path), `user` is `user` (travels), every `.respeak.yaml` and local twin is `folder` (only where the file exists), `project` is `repo`, `project-local` is `local`, `session` is `session`, a `RESPEAK_CONFIG` file is `env`.
6. **R6, settings.** Every leaf of `Resolution.config` the summary table knows; `never_compress` reads as its classes. `default` is the plugin layer alone, its profile filled. `source.line` is PyYAML's mark of the key in that file (`#scopes[n]` inside that entry; `(profile p)` the line of `narrative.profile`). `values` read each applied layer's own mapping. `change` is an `edit`, `live` true: the file in force when it is a user, folder, repo or local file, else the user's file where `key_allowed(key, "user")`, else the project's; a note on every key that `--set KEY=VALUE` changes it for one render.
7. **R7, warnings.** `unknown` for each key a layer file sets that the table does not know (a top-level key once, a deeper one at its leaf); `ignored` for a project-only key in a user, folder or scope layer; `unreadable` (key null) for a file the loader skipped. A keyed read of a key that is no setting: `settings` `[]`, exit 0.
8. **R8, doctor.** One check a script line: `name` before the colon, `detail` after. `python` fails on `pyyaml=no` or `missing`; `claude` warns when missing; `marketplace` warns when `none` or old (remedy the line `make install` prints); `plugin` warns when not installed or old (remedy `claude plugin install respeak@agentik`); `provider` is a note when `none` or `unknown`; `config` warns above 0 (remedy `agentik respeak config explain`) and is a note when `unknown`. The exit is the script's.
9. **R9, summaries.** One table in `respeak-plug.py`, a key or a `*` pattern to one sentence under 100 characters; sixteen given word for word by the brief, the rest written from the shipped file's comments.
10. **R10, records.** A `CHANGELOG.md` entry of at most four lines; one line in `plugin/docs/config-layers.md`.

| # | acceptance (`R` = the worktree's launcher, `RESPEAK_PYTHON` the repo's interpreter, a temp HOME and cwd) | at the pin |
|---|---|---|
| A1 | `R describe --json` exit 0, every key of the describe shape, under 1 s; bad words exit 2; `--version` | no such file |
| A2 | `R describe config --json`, shipped file alone: 117 settings, `value` = `default`, sourced to the shipped file and a line | no such file |
| A3 | a user file's line 2 sets `tech_level: 2`: source user, that file, line 2; `values` default then user; `change.block` | no such file |
| A4 | a project file naming `profile: exec` at line 3: `default_mode` `bluf`, source repo, line 3 | no such file |
| A5 | project `gate.fail_on` sourced to repo; `docs/.respeak.yaml`'s `tech_level` to folder | no such file |
| A6 | a user `gate.enabled`: shipped value, `change.path` the project's, one `ignored` warning | no such file |
| A7 | keyed read; `[]` for a key it lacks; `unknown` rows for `narative:` and `tehc_level`; `unreadable` row | no such file |
| A8 | in process: every `value` is `resolve`'s leaf | no such file |
| A9 | under `-S`: describe answers, config `missing_need`; `R config explain` is the wrapper's bytes | no such file |
| A10 | `R doctor --json`: six checks, the marketplace warn with its remedy; `R doctor` the script's lines | no such file |
| A11 | nothing written under HOME outside `$XDG_CACHE_HOME/agentik/`, no bytecode in `plugin/scripts/` | no such file |
| A12 | by hand: the suite's `config` reads respeak with a line | `respeak is not a tool here`, exit 2 |
| A13 | `python3 -m unittest tests.test_plug tests.test_config_layers tests.test_plugin_shape`; `bash tests/test_doctor.sh`; `bash plugin/scripts/respeak-check.sh` | test_plug absent |
| A14 | the gate, once, last | |

## 3. Interfaces

The suite's plug contract (rows ak5 to ak9), in brief. Every read prints one JSON object and a newline, no escape byte; `{"schema": "agentik.<read>/1", "ok": true, "tool": "respeak", ...}`; a read that could not run prints `ok` false and `error` `{code, message, remedy}`, exit 2. `describe --json`: `version`, `summary` (under 80 characters), `repo`, `plugin`, `needs` `[{name, kind, why, optional}]`, `verbs` `[{name, summary, top}]`, `reads` `[{kind, name, argv}]`. The config read: `layers` `[{name, path, present, travels}]` lowest first; `settings` `[{key, value, default, type, choices, summary, source {layer, path, line}, change {kind, command, path, block, note}, live, values [{layer, value, path, line}]}]`; `warnings` `[{key, reason, value, path, line}]`. `doctor --json`: `failed`, `warned`, `checks` `[{name, status, detail, remedy}]`, status `ok`, `note`, `warn` or `fail`. The describe and config reads write nothing outside `${XDG_CACHE_HOME:-~/.cache}/agentik/`.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

Ledgers, transcripts, anything under the home's `.local/state`; `history/` beyond a charter; a file over 8 KB whole.

## 6. Report

The branch and sha; each act's commit; the gate's id and its line; each acceptance line now; the summaries written; choices; leftovers.
