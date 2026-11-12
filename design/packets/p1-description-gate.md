# Packet p1-description-gate: the plugin's descriptions held under 1,024 bytes by `make check`

| item | value |
|---|---|
| from | agentik-hq's brief `BRIEF-2026-11-11-plugins-p1-description-gate.md`; hq design/09 §1 (F7), §2 (the row "A plugin's descriptions"), §6, §9 step 4; the owner's yes to question 7 of hq design/09; agentik-commons packet p1 (`scripts/plugin-description-bytes`, its branch `p1-description-gate` at 06a2cf5) |
| pin | `main` at `ed31c1a` plus this packet's commit; branch `p1-description-gate`, worktree `.claude/worktrees/p1-description-gate`; plugin 0.12.6; nothing linked (the pyenv virtualenv is found by path) |
| wall | this worktree only; agentik-hq, agentik-commons and the other agentik repos read, never written. No push, `--amend`, rebase, merge, real `make install`, plugin update; `claude` only as the check's `claude plugin validate`; no relay verb, no relay binary built or run outside `make`'s test harness; never a bare `make`, only the gate queue; no `DECISIONS.md` or rendered block edited |
| may touch | `scripts/plugin-description-bytes` (new, vendored), `scripts/vendored.sha256`, `Makefile` (`check-unlocked` and a `descriptions` target), `tests/test_description_gate.py` (new), `design/packets/p1-description-gate.md`, `NICE_TO_HAVE.md`, a charter under `history/sittings/` |
| acceptance | `python3 scripts/plugin-description-bytes plugin` exits 0, its last line `total 574 of 1024 B` (main: no such script); `python3 -m unittest tests.test_description_gate` OK (main: red); `shasum -a 256 -c scripts/vendored.sha256` exits 0 with a `scripts/plugin-description-bytes: OK` line; `grep -c 'plugin-description-bytes plugin' Makefile` reads 1 (main: 0); `git diff main --stat -- plugin \| wc -l` reads 0 |
| budget | One commit per act: the packet, the tests red, the vendored script in the check. `claude-opus-5-5`, high; the charter, if one is written, opens with doclint's five rows |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id> --strict` in one background Bash, last |

## 1. What the source says

The owner, 2026-11-11, his yes to question 7 of hq design/09: "The plugins hide the commands only the owner types, under 1,024 B a plugin: yes." And: "A focus should be on avoiding Claude.md bloat".

hq design/09 §1, F7: a skill's or command's description is in context in every main session unless it sets `disable-model-invocation: true`; a general-purpose helper carries the skill list and the agent-type list too; an agent type whose tool list has neither Skill nor Agent carries neither. §9 step 4: "the 1,024 B gate in `make check`, landing in each repo in the same change that brings its descriptions under it".

At the pin, by commons' script: 574 B, under. The `include` skill sets `disable-model-invocation: true` and is not counted; the `respeak` skill is 189 B and the `respeak` agent 385 B, each `description` a `>` block counted as YAML folds it. The plugin has no `commands/`. hq design/09 §6 gives 532 B: that figure predates 5fa9669 (the audit's narrator description, 323 B to 385 B) and counted the blocks as written.

## 2. Rulings

0. This packet, committed first.
1. **R3.** No command ships, so none is hidden; `include` already is.
2. **R4.** 574 B is under the ceiling: no description changes. The script enters `make check` here, as in the other plugin repos.
3. **R5.** The agent lists `tools: Read, Grep, Glob, Write`: nothing to add.
4. **R1 in the check.** `scripts/plugin-description-bytes`, copied byte for byte from commons' branch, its sum added to `scripts/vendored.sha256` where `sync` writes it, after `plugin-version-check`. `check-unlocked` gains `descriptions`, `$(PYTHON) scripts/plugin-description-bytes plugin`. Placed by hand: `sync` would also replace `scripts/hygiene` with commons' newer copy, which is not this packet's.
5. **R6.** Nothing under `plugin/` changes, so the version stays 0.12.6, and no README line moves.

## 3. Interfaces

`scripts/plugin-description-bytes [--max BYTES] [PLUGIN_DIR]`: commons' (packet p1 there), exit 0 at or under 1,024 B. `tests/test_description_gate.py`: G1 the script passes on `plugin/` at 574 B; G2 `include` stays hidden, every counted description non-empty and a skill's under 201 characters (doclint's bound); G3 the vendored copy listed at its sum; G4 `check-unlocked` names `descriptions`.

## 4. Findings that name this row

None in `NICE_TO_HAVE.md` at the pin.

## 5. Forbidden reads

Ledgers, transcripts, anything under the home's `.local/state`; `history/` beyond a charter; a file over 8 KB whole.

## 6. Report

The branch and sha; each act's commit; the gate's id and its line; the bytes before and after; choices; leftovers.
