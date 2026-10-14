# Packet agentik-r1-respeak: `respeak@agentik`, the provider's new state folder, the venv's new name

| item | value |
|---|---|
| from | agentik-commons `design/agentik-r1.md` §5.1–§5.3, §6.1, §6.2 (this repo's row), §6.3 (c1 c7 c10), §8.1–§8.2, §10 (D4); step 0 landed in the owner's ledger (2026-10-13). The builder reads THIS packet, those sections and §5; nothing else |
| pin | `main` at `319f060` or later; agentik-commons `main` after agentik-r1-commons merges; branch and worktree `agentik-r1-respeak`, off main |
| wall | this repo only; agentik-commons read-only (its `scripts/sync` writes here). No push, `--amend`, rebase, network. Merged without installing (§8.1 step 2): no `make install` but `test_install.sh`'s fake `claude`, no `make venv`; no `claude plugin` command but `make check`'s `validate`. Never write in `~/.local/state` or `~/.config`, read a transcript, or build or run a relay binary or verb |
| may touch | `Makefile`, `.python-version`, `CLAUDE.md`, `.hygiene-allow`, `plugin/scripts/{respeak-config.py,respeak-doctor.sh,respeak-gate.sh}`, `plugin/docs/config-layers.md`, `tests/**`, `design/readme/source.md` then `make readme` (README.md and its sidecar), `scripts/{agentik,hygiene,bounded,vendored.sha256}` by sync only, `NICE_TO_HAVE.md`; delete `.claude-plugin/marketplace.json`. Under `design/`, only this packet's §6 report |
| acceptance | `test -e .claude-plugin/marketplace.json; echo $?` reads `1`; `head -1 .python-version` reads `agentik-respeak`; `grep -c '^SESSION_PROVIDER = "agentik-session"$' plugin/scripts/respeak-config.py` reads `1` |
| budget | 80 turns, 120k context; commit per act; checkpoint at 80% |
| verify | `make check` |

## 1. What the source says

- **§5.1–§5.3.** The plugin becomes `respeak@agentik`; its namespace is unchanged. This repo's `marketplace.json` is deleted: one `agentik` marketplace, in agentik-commons, lists all five plugins, and two install paths would double the hooks. Sessions started before the switch keep the old ID.
- **D4.** respeak gets no command in r1; a later packet adds `doctor`, `config`, `render`.
- **§6.3.** c1: the session state folder `claude-code-session` → `agentik-session`, read by `respeak-config.py:140,624` and named in `respeak-gate.sh:158`. c7: plugin IDs → `respeak@agentik`; doctors accept both and warn (`respeak-doctor.sh`). c10: the venv `claude-code-respeak` → `agentik-respeak` (`.python-version`, `Makefile:6`), fallback `pyenv prefix new || old`, migration `make venv` at the switch. Only names change, never formats.
- **§6.2, this row.** (a) `CLAUDE.md`, `plugin/docs/config-layers.md`; (b) `mkt.json`, `README.md`, `Makefile:84–95` (the install target); (c) as above. Tests that follow: `tests/test_{check,doctor,install}.sh`, `test_provider_layer.py`.
- **§6.1.** The `renamed` check scans live files; exceptions are `.hygiene-allow` rows: the fallback constants, hygiene's patterns, `test_readme`'s reject list, respeak's `claude-code-integration` (not ours).
- **§8.2.** Vendor `scripts/{agentik,hygiene,bounded}` by commons' `scripts/sync`; `renamed` reads 0. The test that fails before: `test_doctor.sh` reports `respeak@agentik`.

**Live hits today** (lines per file). To clear (7): `marketplace.json` 1, `CLAUDE.md` 2, `README.md` 4, `plugin/docs/config-layers.md` 1, `respeak-gate.sh` 1, `tests/test_check.sh` 3, `tests/test_install.sh` 6. To allow (9, ruling 7): `.python-version` 1, `Makefile` 10, `respeak-config.py` 6, `respeak-doctor.sh` 6, `scripts/doclint` 1, `scripts/readme-render.sh` 1, `tests/test_doctor.sh` 4, `tests/test_provider_layer.py` 6, `tests/test_readme.py` 2. Plus one charter, `history/sittings/2026-09-23-5-adv6.md` 2 (ruling 8).

## 2. Rulings (decided inside the record, one sentence each)

1. A c-item reader takes the new path when it exists, else the old one when it exists, else the new; a writer writes where its reader resolved.
2. `SESSION_PROVIDER` becomes `agentik-session` (the provider line reads `provider: agentik-session <v> profile <p>`), and `SESSION_PROVIDER_OLD = "claude-code-session"` is the c1 fallback folder only.
3. The doctor keeps its six lines: the marketplace line names `agentik` when that marketplace is known, else the old one with `; old, the switch moves it`; the plugin line names `respeak@agentik`, else the old ID with `; old id, use respeak@agentik`.
4. `.python-version` holds two lines, `agentik-respeak` then `claude-code-respeak`; the Makefile's `PYTHON` takes the first venv whose `python3` exists, and `lint` checks the first line against `VENV`.
5. `make install` never adds a marketplace: with `agentik` known it runs `claude plugin install respeak@agentik` (or `update` when listed); without it, it prints the commons marketplace line and exits 2. respeak puts no `agentik` on PATH (D4: no command).
6. `validate` runs `claude plugin validate plugin/` only; `hygiene` checks `shasum -a 256 -c --status scripts/vendored.sha256` in place of `HYGIENE_SHA` and `BOUNDED_SHA`, and `DOCLINT_SHA` stays; `test_hygiene.py` swaps its expected exits to 1 hit, 2 usage and changes nothing else.
7. Each allowed file gets one row `<path>: renamed  # <reason>`: the §6.1 exceptions (the vendored hygiene if it hits its own patterns, doclint, readme-render, test_readme's reject list), the c1 fallback (`respeak-config.py`, `test_provider_layer.py`), the c7 fallback (`respeak-doctor.sh`, `test_doctor.sh`), the c10 fallback (`.python-version`, `Makefile`); old names in their comments and prose still go.
8. `history/sittings/*: renamed  # per-packet records (§5.3); no chain runs here`, since commons' newest-per-suffix rule would count the packet charter as live; the header line "No entry covers history/" says so.

Any further fork: decide inside the record; log it in §6.

## 3. Interfaces

| item | contract |
|---|---|
| `respeak-doctor.sh` | six lines as today; ruling 3's wording on the old IDs; exit 0, or 2 without PyYAML |
| `tests/test_doctor.sh` | the fake `claude` lists `{"name":"agentik",…}` and `{"id":"respeak@agentik","version":"0.6.0"}`; checks named `marketplace line agentik` and `plugin line respeak@agentik`; a second fake lists only the old IDs, check named `old id warns` |
| `tests/test_install.sh` | the fake `claude`: `agentik` known and the plugin absent calls `plugin install respeak@agentik`; listed calls `plugin update respeak@agentik`; unknown exits 2 and calls nothing |
| README | install: `claude plugin marketplace add agentik-dev/agentik-commons`, `claude plugin install respeak@agentik`; the provider row names `agentik-session` |

## 4. Findings that name this row

None. The table below is the whole acceptance (the header row holds its read-only subset; `verify` is the gate line). Run in the worktree after the last commit.

| # | line | reads |
|---|---|---|
| 1 | `make check >/dev/null 2>&1; echo $?` | `0` |
| 2 | `scripts/hygiene --json \| python3 -c 'import json,sys;print(sum(f["group"]=="renamed" for f in json.load(sys.stdin)["files"]))'` | `0` |
| 3 | `bash tests/test_doctor.sh \| grep -cE '^ok   - (marketplace line agentik\|plugin line respeak@agentik\|old id warns)$'` | `3` |
| 4 | `bash tests/test_doctor.sh >/dev/null 2>&1; echo $?` | `0` |
| 5 | `bash tests/test_install.sh >/dev/null 2>&1; echo $?` | `0` |
| 6 | `test -e .claude-plugin/marketplace.json; echo $?` | `1` |
| 7 | `shasum -a 256 -c scripts/vendored.sha256 \| grep -c ': OK$'` | `3` |
| 8 | `C="$(git rev-parse --path-format=absolute --git-common-dir)/../../agentik-commons"; cmp -s scripts/hygiene "$C/scripts/hygiene" && cmp -s scripts/agentik "$C/bin/agentik" && echo same` | `same` |
| 9 | `head -1 .python-version; grep -c '^VENV = agentik-respeak$' Makefile` | `agentik-respeak` then `1` |
| 10 | `grep -c 'SESSION_PROVIDER = "agentik-session"' plugin/scripts/respeak-config.py` | `1` |
| 11 | `git status --short \| wc -l` | `0` |

The test that fails before: line 3 (the doctor knows only `respeak@claude-code-respeak`); lines 2, 6, 7 fail before too.

## 5. Forbidden reads

Read-only outside this repo: `$C` (line 8): `design/agentik-r1.md` (the sections in `from`), `GUIDE.md`; run `"$C/scripts/sync" .` once.

Forbidden: transcripts, `~/.local/state`, `~/.config` (hygiene reads its private list; never print it), the owner's ledger, other repos.

## 6. Report (under 1,500 words)

The acceptance table with each line's output; the commits; each ruling beyond §2, one sentence; what went to `NICE_TO_HAVE.md`.

Rulings beyond §2 (builder, 2026-10-13):

- c1's fallback is per resolved file, not per folder; both present, the new wins.
- No `make readme` (it spawns `claude -p`): README.md and its source took one hand edit, stamped by `readme-fresh.sh --stamp` after the verifier passed.
- `test_provider_layer.py` names the old folder only as `SESSION_PROVIDER_OLD`: no allow row.
- Ruling 8's rows dropped: no `.hygiene-live` declares a chain here.
- `test_readme` also rejects `agentik-{agents,relay,decisions}`; the layout's `.claude-plugin/` line went.
