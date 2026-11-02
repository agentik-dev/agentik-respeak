# Packet r17-rows: resync recordlint, run it in doclint, the NICE as a table

| item | value |
|---|---|
| from | agentik-hq `HANDOFF.md` item 18 (build 7, the owner's word of 2026-11-01); agentik-hq `design/05-records-as-tables.md` §2, §3, §4, §7 items 6, 7, 8; hq entry 6; the shared brief of 2026-11-01 for d27, AR99 and r17, cut to this repo's row |
| pin | `main` at `d711740` plus this packet's commit; branch `r17-rows`, worktree `.claude/worktrees/r17-rows`; agentik-commons `main` at `eff4fd5` (`scripts/recordlint` d6c5c217, on `env python3`); plugin 0.12.3 |
| wall | this worktree only; agentik-hq, agentik-commons and the other agentik repos read at main, never written, except that agentik-commons `scripts/sync <this worktree>` writes into this worktree. No push, `--amend`, rebase, merge, real `make install`, real `install-cli`; `claude` only as `claude plugin validate` and `claude plugin test plugin`; a test never writes under the live `~/.local`, `~/.claude`, `~/.config`; never touch `~/.config/agentik/hooks-follow-launcher`; no relay verb, no relay binary built or run outside `make`'s test harness; no `kill`, `pkill` or signal from a script; never a gate verb under a temp HOME; zsh here, `bash -c` for bash syntax; `rm -r` only as `"${VAR:?}"` |
| may touch | `scripts/` (by `sync` only), `plugin/bin/` and `plugin/lib/` only as `sync` places its canonical copies, `Makefile` (the doclint target), `NICE_TO_HAVE.md`, `history/NICE-2026-11-01.md` (by `git mv` only), `.hygiene-allow`, `plugin/.claude-plugin/plugin.json` and what a test pins to its version (only if `plugin-version-check` asks), `design/packets/r17-rows.md`, a charter under `history/sittings/` |
| acceptance | §2's acts; `python3 scripts/recordlint NICE_TO_HAVE.md` exits 0 and prints `held:` (main: `skip`); `grep -c 'scripts/recordlint' Makefile` reads 1 or more (main: 0); `grep -c 'respeak-check.sh' Makefile` reads 1; `make doclint` exits 0 and runs recordlint; `grep -c '^history/NICE-2026-11-01.md: sibling' .hygiene-allow` reads 1; `make hygiene` exits 0 |
| budget | One commit per act. **Stop at 100k context or 70 tool calls:** commit the act in flight, write the exact resume line, report. `claude-opus-5-5`; the charter opens with doclint's five rows |
| verify | `agentik session gate run <absolute worktree path> -- /bin/sh -c "make check > <scratch log> 2>&1"`, then `agentik session gate wait <id>` in one background Bash, last. It exits 0 whatever the job's code: read the code from its line |

## 1. What the source says

The last three repos take design/05's tables, as commons, agents, session and hq did on 2026-11-01. design/05 §2: a NICE is a title, one head paragraph naming the archive, then tables under `##` headings, each `\| id \| level \| area \| finding \| evidence \| from \|`; `id` `n<k>`, never reused; `level` `S1` to `S4`; `area` a component or a backticked path; `evidence` a `file:line`, sha, record, repro or "not confirmed"; `from` a date and source. A cell is one line, every pipe `\|`. §3: `git mv NICE_TO_HAVE.md history/NICE-2026-11-01.md`, and in the same commit `history/NICE-2026-11-01.md: sibling` under the row that allows `NICE_TO_HAVE.md`, since hygiene skips `sibling` only under `history/sittings/`. An archive is never edited. §4: `sync` places `scripts/recordlint` in each tool repo's `scripts/` under `vendored.sha256`; each repo's `doclint` target runs it after doclint. **Not here:** any other repo; any change to doclint; code.

## 2. Rulings

0. This packet, committed first, as `design/packets/r17-rows.md`, reshaped from the shared brief so doclint and hygiene pass (this repo's row only, no home path).
1. **Resync.** agentik-commons `scripts/sync <this worktree>`; commit what it places. If it changes anything beyond `scripts/recordlint` and its `vendored.sha256` line, list each path in the report, and run the tests before committing: a canonical copy that breaks a test of today's behaviour is a stop.
2. **Makefile.** The `doclint` target runs `scripts/recordlint` after its existing lines; the `respeak-check.sh` line stays.
3. **The NICE.** design/05 §3: `git mv NICE_TO_HAVE.md history/NICE-2026-11-01.md`, and in that commit `history/NICE-2026-11-01.md: sibling` under the `NICE_TO_HAVE.md: sibling` row of `.hygiene-allow` (same group and a matching comment). A new `NICE_TO_HAVE.md`: a title, one head paragraph naming the archive, then `\| id \| level \| area \| finding \| evidence \| from \|` under a `##`, holding the S1 to S3 items confirmed open on main by a `file:line` or a test; ids from `n1`. S4 and unlevelled stay archived. An empty table is fine when none is open; the head paragraph says so.
4. **The version**, only if `plugin-version-check` asks: the patch.
5. The gate, last.

## 3. Interfaces

`Makefile` `doclint:` gains `$(PYTHON) scripts/recordlint` as its last line. `NICE_TO_HAVE.md` holds the canonical header row and its separator; `scripts/recordlint` prints `NICE_TO_HAVE.md: held: N rows`. Commits `r17 act N: <one line>`.

## 4. Findings that name this row

design/05 counts 0 open S1 to S3 items in this repo's NICE. An S1 or S2 found open is reported, never fixed here.

## 5. Forbidden reads

Any repo beyond this worktree, agentik-commons `scripts/` and `GUIDE.md` §9, and agentik-hq design/05; ledgers, transcripts; `history/` beyond the charter; a file over 8 KB is read by section, never whole.

## 6. Report

At most eight lines: the branch and sha; each act's commit; what `sync` placed; the gate's id and its code from its line; the suite's counts; the NICE rows kept (ids, levels, one line each); if stopped, the exact resume line. A stop (`sync` breaking a test; hygiene red on a file that needs a new reason row; an S1 or S2 open) is a result: commit what is there and report.
