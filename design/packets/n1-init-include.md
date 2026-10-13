# Packet n1: init joins include, the SessionStart off key, the wrapper's name, the include's notes (0.8.0)

| item | value |
|---|---|
| from | `NICE_TO_HAVE.md` at `main` 6591869: the SessionStart bullet, N3 in the include-r1 bullet, the include's uncommitted-config and commit-the-lexicon sentences, the init/include bullet; the owner's word, 2026-10-12 18:42: implement respeak's NICE items; portfolio entry 26 (the wrapper `scripts/py`) |
| pin | this repo's `main` at ba05d92; branch `n1-init-include`; worktree `.claude/worktrees/n1-init-include`; a hand-run builder, not a relay row |
| wall | this repo only. Public repo: no private repo name, home path or personal name in any file. No push, merge, `--amend` or rebase. Never `relay run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; never build or run a relay binary. Tests set `HOME` and the XDG dirs to temp dirs; no live `claude` in a test |
| may touch | `plugin/scripts/respeak-include.py`, `plugin/scripts/lexicon-status.sh`, `plugin/scripts/respeak-config.py`, `plugin/scripts/py` (new), `plugin/scripts/respeak-py.sh`, `plugin/config/respeak.config.yaml`, `plugin/config/project-seed.yaml`, `plugin/skills/init/SKILL.md`, `plugin/skills/include/SKILL.md`, every skill or doc that names `respeak-py.sh`, `.claude/respeak/config.yaml`, `design/include-r1.md`, `design/packets/n1-init-include.md`, `tests/test_include.py`, `tests/test_hooks.sh`, `tests/test_overrides.sh`, `tests/test_config_layers.py`, `CHANGELOG.md`, the plugin and marketplace manifests, `design/readme/source.md`, `README.md` and `design/readme/rendered.sha256` (by `make readme`), `NICE_TO_HAVE.md`, `history/sittings/*.md` |
| acceptance | `python3 -m unittest tests.test_include -k propose 2>&1 \| tail -1` reads `OK`; `python3 -m unittest tests.test_include -k uncommitted 2>&1 \| tail -1` reads `OK`; `grep -rl 'respeak-py.sh' plugin/skills plugin/hooks design/include-r1.md \| wc -l` reads 0; `test -x plugin/scripts/py` exits 0; `grep -c 'session_start' plugin/config/respeak.config.yaml` reads 1 or more; `grep -c '"version": "0.8.0"' plugin/.claude-plugin/plugin.json` reads 1; `grep -c '^# Packet n1:' design/packets/n1-init-include.md` reads 1 |
| budget | one builder sitting; one commit per act; `make readme` once, last |
| verify | `make check` |

## 1. What the source says

1. **init proposes the include.** A new verb, `respeak-include.py propose [--root R]`, prints the `gate.include` list built from the human-lane files present at the root, in this order and only when present: `README.md`, `CHANGELOG.md`, `DECISIONS.md`, `DESIGN.md`, `NICE_TO_HAVE.md`, `OPEN-QUESTIONS.md`, `HANDOFF.md`, `docs/**/*.md`, `design/readme/**/*.md`, `plugin/docs/**/*.md` (a glob only when it matches a file). With none present it prints `["**/*.md"]`. One flow list on one line; exit 0; exit 2 outside a git work tree.
2. **init renders and offers the include.** With consent, init seeds the proposed list and `narrative.profile: peer-engineer`, runs `respeak-include.py write`, and offers `@.claude/respeak/include.md` as a CLAUDE.md import. It offers the `lexicon-active.md` line only when the repo has its own `.claude/respeak/lexicon.yaml`.
3. **The SessionStart hook's off key.** `hooks.session_start`, default `false`, any layer. `lexicon-status.sh` prints nothing unless it resolves `true`. This repo's config sets it `true`. `validate` refuses a non-boolean. `RESPEAK_HOOKS=off` and `/respeak:off` still win.
4. **N3, the wrapper's name.** `plugin/scripts/py` holds today's `respeak-py.sh` logic; `respeak-py.sh` becomes a one-line `exec` of `py`. Skills, hooks, docs and `design/include-r1.md` name `scripts/py`. The interpreter choice does not change.
5. **The uncommitted source.** `respeak-include.py write` warns on stderr for each tracked source it rendered from that differs from HEAD, naming it; exit stays 0. The include skill's first step says to commit the config and lexicon before `write`.

## 2. Rulings

Decide what §1 leaves open and log each choice in one sentence in the report. What lies outside §1 goes to `NICE_TO_HAVE.md`. The human lane is gated: a change under ten new lines needs no editorial pass. `README.md` changes only through `make readme`. Remove from `NICE_TO_HAVE.md` the four notes §1 closes and leave every other note.

## 3. Interfaces

`respeak-include.py propose [--root R]` (new); `respeak-include.py write` (a stderr warning, no exit change); the config key `hooks.session_start`; `plugin/scripts/py <script.py> [args]`.

## 4. Findings that name this row

None; the four NICE notes in the `from` row are the findings.

## 5. Forbidden reads

Transcripts whole; anything under `~/.local/state/agent-relay`.

## 6. Report

At most 250 words: each act's commit, each acceptance line's result, the choices made, any note filed.
