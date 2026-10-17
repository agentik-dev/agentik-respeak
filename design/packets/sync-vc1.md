# Packet sync-vc1: the vendored `plugin-version-check` and its line in `make check`

| item | value |
|---|---|
| from | agentik-commons `GUIDE.md` §5 (`check` runs `scripts/plugin-version-check`) and §7 (what it checks); commons' `version-check` merge at `dcec631` (the canonical script and `scripts/sync`'s fourth copy); agentik-hq `HANDOFF.md` items 3 and 5: each plugin repo wires the check into its `check` in its next sync packet |
| pin | `main` at `b0b13c8` plus this packet's commit; agentik-commons `main` at `02409f0`, read-only; branch `sync-vc1`, worktree `.claude/worktrees/sync-vc1`, off main; a hand-run builder |
| wall | this repo only; agentik-commons read-only (its `scripts/sync` writes here, once). No push, merge, tag, `--amend`, rebase, `git stash`, network or install; no `claude` beyond `make check`'s `validate`; never build or run a relay binary, never run `relay` or `agentik relay` `run`, `plan`, `gate`, `stop`, `kill`, `clean` or `resume`. Never write under `.venv`, `~/.claude`, `~/.config`, `~/.pyenv` or `~/.local/state`; one `make` at a time on the machine (§2 ruling 5) |
| may touch | `scripts/plugin-version-check` (new) and `scripts/vendored.sha256`, by agentik-commons' `scripts/sync` only; `scripts/agentik`, `scripts/hygiene`, `scripts/bounded`, by the sync only and only if commons' bytes moved since `02409f0` (at the pin they are equal); `Makefile` (the target and its name in the chain); `design/packets/sync-vc1.md`, `history/sittings/*.md`, `history/sessions/NEXT`. Nothing else |
| acceptance | `grep -c -F -e 'c97596e7b129ac53fb2c8b22adfcf3a9d7e5bd71b6c9473d719aa2cda8063c4b  scripts/plugin-version-check' -e '4cd780d9c66d996e58b217b39ee0679e426172ab9ad7bd4e17971b188e7e7600  scripts/agentik' -e '8ef611607c0fdc44703fa48c374ebc00edc1488da56292985380200d219eb2e9  scripts/hygiene' -e '188adff23545f99159a189174baf3771f7e790e5f1256958b0e3e3ac4ed11306  scripts/bounded' scripts/vendored.sha256` reads `4` (on main: `3`, the rf1 pins); `grep -c -F 'scripts/plugin-version-check' Makefile` reads `1` (on main: `0`); `grep -A1 -F 'PYTHON) scripts/hygiene' Makefile \| grep -c -F 'PYTHON) scripts/plugin-version-check'` reads `0` (on main: `0`), the hygiene recipe unchanged; `sed -n '/^check-unlocked:/p' Makefile \| grep -c plugin-version-check` reads `1` (main: `0`) |
| budget | 25 turns, 100k context, `claude-opus-5-5`; three acts, one commit each (§2 ruling 5); checkpoint at 20 turns; the charter opens with doclint's five rows |
| verify | `make check` |

## 1. What the source says

- `GUIDE.md` §5: `check` runs `test`, `lint`, `doclint`, `hygiene`, `validate`, README freshness, `shasum -a 256 -c scripts/vendored.sha256` and `scripts/plugin-version-check`. §7: any change under `plugin/` bumps `plugin.json`'s version, since Claude Code refreshes an installed plugin only on a new version; the check fails when a file under `plugin/` changed after the commit that last changed the version (a bump not yet committed passes).
- The canonical script, commons' `scripts/plugin-version-check` (sha256 `c97596e7…`, act `8e827a1`, merged at `dcec631`): stdlib only; `[--json] [--repo DIR]`, run from the repo root by default; exit 0 nothing changed, 1 a file changed (one stderr line per file), 2 usage, no git work tree, git failing, or no readable `version`.
- Commons' `scripts/sync <repo>` copies four files: `bin/agentik` to `scripts/agentik`, and `scripts/hygiene`, `scripts/bounded` and `scripts/plugin-version-check` into `scripts/`, then rewrites `scripts/vendored.sha256`, four lines in `shasum -a 256 -c` form. It touches nothing else and never commits.
- Measured at the pins: `scripts/agentik`, `scripts/hygiene` and `scripts/bounded` equal commons' bytes (`cmp` exits 0; `shasum -a 256 -c scripts/vendored.sha256` prints three `: OK`). The sync therefore changes two files: `scripts/plugin-version-check` (new) and `scripts/vendored.sha256` (a fourth line, `c97596e7…  scripts/plugin-version-check`).
- On main, commons' script with `--repo` this repo reads `version 0.11.0, set at b0b13c86ffb9; nothing under plugin/ changed since`, exit 0.
- The Makefile: `check` runs `check-unlocked: test lint doclint hygiene readme-fresh validate` under `scripts/bounded`. The `hygiene` recipe holds the vendored sum check, then the `scripts/doclint` pin, then `$(PYTHON) scripts/hygiene`. No line sets `PYTHONDONTWRITEBYTECODE`.
- A scratch clone at the pins, synced and wired as §2 says: `scripts/hygiene` reads `hits outside allowlist: 0` (the new file falls under `scripts/*: sibling`), the check exits 0, and the three acceptance lines read `4`, `1`, `1`.

## 2. Rulings

1. The sync is the only writer of the vendored files: agentik-commons' `scripts/sync`, run once with this worktree's root as its argument. None is edited by hand. If it changes a vendored file §1 does not name, commons moved since the pin: commit what it wrote and report the file and its new sum (acceptance line 1 then reads under `4`, and the sitting that cut this packet re-pins it).
2. The Makefile gains a target `plugin-version-check` with a `##` help line and one recipe line, the call the brief drafted (`$(PYTHON) scripts/plugin-version-check`), and `check-unlocked`'s prerequisite list names `plugin-version-check` right after `hygiene`; the `hygiene` recipe and `make hygiene` are unchanged; no help text or comment spells `scripts/plugin-version-check`, so the acceptance count stays 1.
3. No version bump: the check reads clean on main and no act touches `plugin/`; `plugin.json` stays `0.11.0`.
4. `.hygiene-allow` is not edited. A new hygiene hit is red: report its group and count and leave the branch as it is.
5. Three acts, commits by explicit path (`git add <paths>`). Act 1: the worktree, this packet committed alone (the copy-in rule), the charter `history/sittings/2026-10-17-<n>.md` (the next free `n`) opened in doclint's five-part shape. Act 2: the sync; commit the files it wrote. Act 3: the Makefile line; commit `Makefile` with the charter. Then the hand checks (§6), then one `make check`, last, only when `ps -axo command | grep -E '(^|/)make (check|check-unlocked)( |$)' | grep -v grep` prints nothing: sibling repos build this same packet today, and a relay night's `make check-fast` does not hold this. While it prints, wait 20 to 60 s with jitter and read again, up to 20 minutes; then report `make check` unrun. A last stderr line `bounded: stop: lock`, `load` or `wall` is unrun, not red: wait 60 s and run it once more.

## 3. Interfaces

- `make check` gains one step: `scripts/plugin-version-check` after `scripts/hygiene`. From the next packet on, a change under `plugin/` with no bump on its branch is red (make exits 2 on the script's 1).
- The `plugin-version-check` target runs it inside `check-unlocked`, after `hygiene`; `make hygiene` does not, and a packet that edits `plugin/` and bumps in a later act reads `make check` red until the bump is in its working tree (an uncommitted bump passes).
- `scripts/vendored.sha256` has four lines; the recipe's `shasum -a 256 -c --status` reads all four. Its failure message and the comment above `DOCLINT_SHA` still name three files: they stay (ruling 2), a lead for this repo's NICE when a packet next touches the Makefile.
- `scripts/agentik`, `scripts/hygiene` and `scripts/bounded` keep their bytes, flags and exits. `plugin.json` is unchanged.

## 4. Findings that name this row

agentik-hq `HANDOFF.md` item 3 (its first bullet: each plugin repo wires `plugin-version-check` into its `check` in its next sync packet) and item 5 (commons S3, "Left: each plugin repo's sync packet wires the check into its `check`") are answered for this repo when this branch merges; the note is agentik-hq's to make. Commons' `make versions` line for this plugin (0.11.0, the marketplace at `02409f0`) is unchanged by this packet: no version moves.

## 5. Forbidden reads

Transcripts; anything under `~/.local/state` or `~/.claude/projects`; any other repo, except agentik-commons' `scripts/sync`, `bin/agentik`, `scripts/hygiene`, `scripts/bounded`, `scripts/plugin-version-check` and `GUIDE.md`.

## 6. Report

At most six lines: the branch head and its three commits; the files the sync changed; each acceptance line's reading; the hand checks (`shasum -a 256 -c scripts/vendored.sha256` prints four lines ending `: OK`; `cmp` of `scripts/agentik`, `scripts/hygiene`, `scripts/bounded` and `scripts/plugin-version-check` against agentik-commons' `bin/agentik` and its three `scripts/` files exits 0; `PYTHONDONTWRITEBYTECODE=1 scripts/plugin-version-check; echo rc=$?` in the worktree after act 3 reads `nothing under plugin/ changed since` and `rc=0`); and `make check`'s result (green; red, with the failing target's last lines; or unrun, on a `bounded: stop:` line twice or 20 busy minutes).
