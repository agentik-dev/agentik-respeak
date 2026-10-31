# Packet r19-cut: the machine lane, the gate hook and the lexicon tooling go; the narrator stays

| item | value |
|---|---|
| from | the owner's word of 2026-10-31, agentik-hq `HANDOFF.md` item 17, build 3 of the Fable review; agentik-hq `docs/REVIEW-2026-10-31-suite-review.md` §2.6, read as `record <file> --section 12`, and §5, `--section 24` |
| pin | `main` at `4cd4ec3` plus this packet's commit; branch `r-cut`, worktree `.claude/worktrees/r-cut`, off main; a hand-run builder; sibling repos read-only |
| wall | this worktree only. No push, merge, tag, `--amend`, rebase, install or network; no `claude` beyond `claude plugin validate`; never build or run a relay binary, never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`; a caller in another repo that needs a change is a line in the hand-back |
| may touch | `plugin/**`, `tests/**`, `scripts/readme-render.sh`, `scripts/readme-fresh.sh`, `Makefile`, `CLAUDE.md`, `CHANGELOG.md`, `NICE_TO_HAVE.md`, `README.md`, `design/readme/source.md`, `design/readme/rendered.sha256`, `design/readme/contract.txt`, `docs/architecture.md`, `docs/references.md`, `examples/layered/**`, `.claude/respeak/**`, `.hygiene-allow`, `.gitignore`, `design/packets/r19-cut.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `test ! -e plugin/scripts/respeak-lexicon.py -a ! -e plugin/scripts/respeak-gate.sh -a ! -e plugin/hooks/hooks.json -a ! -e plugin/corpus/lexicon.yaml` exits 0 (main: 1); `ls plugin/skills \| tr '\n' ' '` reads `include respeak ` (main: seven); `grep -rIlE 'respeak-lexicon\|respeak-gate\|lexicon-status\|lexicon-active\|render-lexicon\|session_start\|auto_narrative\|block_on' --exclude=config-layers.md plugin CLAUDE.md design/readme/source.md README.md .claude \| wc -l` reads `0`; `grep -c -F 'arguments: [mode, source]' plugin/skills/respeak/SKILL.md` reads `1`; `grep -c -F 'never_compress:' plugin/config/respeak.config.yaml` reads `1`; `test "$(wc -l < plugin/skills/respeak/SKILL.md)" -le 60` exits 0 (main: 84); `cmp design/readme/source.md README.md` exits 0 |
| budget | 90 tool calls, 180k context, `claude-opus-5-5`; five commits, this packet's first; the charter opens with doclint's five rows |
| verify | `make check` |

## 1. What the source says

- The verdict, §2.6: "delete the machine lane, the gate hook and the lexicon tooling. Keep one `respeak` skill of a page, with the never-compress rule".
- Measured at the pin: `plugin/corpus/lexicon.yaml` holds 3 terms; the digest import `@.claude/respeak/lexicon-active.md` is in this repo's `CLAUDE.md` alone; `plugin/hooks/hooks.json` holds three hooks; `respeak-lexicon.py` is 876 lines, `respeak-gate.sh` 314.
- This repo has no `DECISIONS.md`, so no ledger entry states the lane; the note on where it went sits in the README.

## 2. Rulings

1. Callers keep working. `make readme` in session, agents and decisions and `decisions ask` run `plugin/scripts/respeak-render.sh` and `respeak-verify-edit.py` from the installed plugin, with `respeak-deadline.sh`, `respeak-measure.py`, `respeak-config.py`, the corpus and `agents/respeak.md` behind them. All of these stay. The research site's `make style` and `make include` run `respeak-check.sh` and `respeak-include.py` from a source checkout: both stay. `/relay:report` asks for the `respeak:respeak` agent by name: it stays. decisions' `CLAUDE.md` names `/respeak:include`: it stays.
2. `respeak-check.sh` keeps its verdict and its exits; the committed-config gate it took from `respeak-gate.sh --file --committed` moves inside it. `tests/test_check.sh` stays unweakened. `gate:` remains the check's and the render's config.
3. `never_compress` leaves `shorthand:` for a top-level project-only key, without the `reserved-metawords` class, which was the shorthand's repair channel.
4. All three hooks go, and `hooks.json` with them: the gate by the verdict; SessionStart read the lexicon; Stop nudged a narrative no config turned on. With no hook left, the session overrides, `/respeak:on`, `/respeak:off` and `RESPEAK_HOOKS` and `RESPEAK_GATE` have nothing to silence, and `gate.block_on`, `hooks.*`, `narrative.auto_narrative` and `narrative.lexicon_access` have no reader.
5. `/respeak:audit`, `/respeak:init` (it seeded the lexicon, the gate and the statusline) and `/respeak:report` (no caller; the verdict keeps one narrator) go, with `statusline.sh`, `report-env.sh` and their tests.
6. The invocation `/respeak:respeak technical design/readme/source.md; <contract>` with `--allowedTools 'Read Write'` stays valid: the skill's `arguments: [mode, source]` stays, and the page states what follows the `;`.
7. The include template loses the shorthand line and bumps its version; a rendered include file in another repo reads stale until its author rewrites it (a line for the hand-back).
8. The README is edited by hand: the source and the render byte-identical, the sidecar re-stamped with `scripts/readme-fresh.sh --stamp`; no `claude` runs. Past design records, packets and sittings keep their words. No archive folder: the deleted code stays in git history.
9. Plugin `0.12.0`: `0.x` may break on a minor (GUIDE §7). The bump lands in the last commit that touches `plugin/`.

10. `plugin/docs/config-layers.md` names the removed keys once, in its upgrade note; the acceptance grep excludes that file.

Amendment 1 (2026-10-31, the coordinator's rulings), after the refuter's round 1, each with a test that goes red first: (F3) `respeak-config.py` drops the unreachable `fmt_statusline` branch and the statusline comment. (F4) `validate` on a config holding the removed `hooks`, `shorthand`, `block_on` and `lexicon_access` warns and exits 0; the dropped case returns as one test in `tests/test_config_layers.py`. (F5) the `.mdx`, upper-case and non-Markdown cases of the old `tests/test_gate_hook.sh` move into `tests/test_check.sh`. (R4) a rendered file holds the narrative alone, whichever path renders it: the marker, the `gate:` and `config:` lines and the still-failing report go in the answer; `respeak-render.sh` strips the closing lines as it strips the marker, and the skill and the agent state it; a fake runner pins the script and a static test the two texts. A real `claude -p` render stays unproved. (R5) the skill's serial render fits relay's `--max-turns 8` (agentik-relay `Makefile:58-59`, not edited) in seven turns: a contract naming a file never tries the agent, and the reads go in one message. The plugin bumps to `0.12.1` in the last commit that touches `plugin/`, since `plugin-version-check` reads a file changed after the bump as a failure; the README moves by hand, source and render byte-identical.

## 3. Interfaces

- Gone: every hook; `/respeak:audit`, `init`, `on`, `off`, `report`; config keys `shorthand.*`, `hooks.*`, `gate.block_on`, `narrative.auto_narrative`, `narrative.lexicon_access`; userConfig `auto_narrative`; env `RESPEAK_HOOKS`, `RESPEAK_GATE`.
- Kept: `/respeak:respeak`, `/respeak:include`, the `respeak:respeak` agent, `respeak-render.sh`, `respeak-verify-edit.py`, `respeak-measure.py`, `respeak-check.sh`, `respeak-config.sh` and its verbs, `respeak-include.py`, `make readme`, `make doctor`, `make install`.
- New: top-level `never_compress:`.

`make check`'s `validate` runs `claude plugin validate plugin/`.

## 4. Findings that name this row

agentik-hq `HANDOFF.md` item 17 is answered for respeak when this branch merges; the note is agentik-hq's to make, as is commons' marketplace line.

## 5. Forbidden reads

Transcripts; anything under `~/.local/state`; the whole of the review (sections 12 and 24 only); a file over 8 KB whole.

## 6. Report

At most twelve lines: the branch and sha, the gate id and exit, lines removed and kept, each caller and whether it works, the lines other repos need, any review claim that failed, anything decided or left.
