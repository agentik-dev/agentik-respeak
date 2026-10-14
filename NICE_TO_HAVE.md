---
status: current
updated: 2026-10-13
owner: the owner
audience: the owner, agent
---
# claude-code-respeak: what is left open, none of it blocking

Nothing here blocks a review or a merge. An item leaves when it lands, or when a decision retires it.

- include-r1's refuter round (2026-10-11; BLOCK on B1, fixed before the merge), the notes left: N5, the import from the user-level CLAUDE.md that the owner's answer names stays a by-hand step. N8, the owner's ruling sits in no DECISIONS.md, since this repo keeps no ledger. Unchecked: whether Claude Code hides the include's HTML-comment stamp line from the model.
- `/respeak:include`'s two rounds (2026-10-11; round one's B1 to B4 and round two's F1 fixed before the merge), the notes left: a change to the script alone makes `check` say "hand-edited" where the file is only stale. Over the cap, `check` exits 2 and prints "nothing written". A backtick inside a `gate.include` pattern breaks its code span. A separate git dir under another name inside the root (`--separate-git-dir=.gitstore`) is not refused. `CLAUDE_CONFIG_DIR` is not guarded the way ~/.claude is. A tracked config hard-linked to a user-layer file reaches the render (the index rule allows it). With its parent directory at mode 000, the tracked config is skipped with no warning, and `check` exits 0.
- `/respeak:init` still copies the plugin's lexicon into every repo (packet n1, 2026-10-12), so it offers the `lexicon-active.md` import only when `.claude/respeak/lexicon.yaml` was there before the run. Whether `init` should seed a lexicon at all is open.
- S4, n1 review: `include write`'s uncommitted note fires on edits the render never reads (a `hooks:` key, a comment), and stays silent on a tracked config or digest deleted from the work tree, or on a skip-worktree edit.
- S4, n1 review: `propose` counts a symlinked `README.md` but skips a symlinked `docs/*.md`.
- S4, n1 review: `propose --root ""` silently means the current directory.
- S4, n1 round two: a bare `yes` or `on` in a config file is a YAML 1.1 boolean, so `validate`, the resolver and the hook all accept it for `hooks.session_start`, while `--set hooks.session_start=yes` is refused; the comment at `plugin/scripts/respeak-config.py:788` says `yes` is refused.
- S4, n1 round two, unchecked: whether init's `Bash(git add .claude/respeak/*)` allowance also matches `git add .claude/respeak/x .`, which stages the whole tree; Claude Code's permission matcher was not run.
- agentik-r1-respeak (2026-10-13): c10's migration is `make venv`, but this repo has no `venv` target. Until one lands or the owner builds `agentik-respeak` (3.12, PyYAML) at the switch, the Makefile runs on the old venv named on `.python-version`'s second line.
- agentik-r1-respeak (2026-10-13): README.md and its source took the same hand edit and were stamped by `readme-fresh.sh --stamp` after the verifier passed, since `make readme` spawns `claude -p`. The next `make readme` gives the new install paragraph its editorial pass.
