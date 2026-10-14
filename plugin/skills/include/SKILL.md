---
name: include
description: >
  Write or check this repo's static include file: its default writing rules,
  at most 1,500 bytes, shipped in the repo and loaded by an @ line.
  User-invoked only.
disable-model-invocation: true
argument-hint: "[write|check] [--out PATH]"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/py respeak-include.py *)
---

# respeak: the repo's include file

The include file holds this repo's default writing rules: the two lanes, the
default mode for its reader, and the other modes. It is rendered from the
plugin defaults and the repo's git-tracked `.claude/respeak/config.yaml`
only, and it ships in the repo, so a reader without respeak still gets the
rules. No personal layer reaches it: not `config.local.yaml`, the user file,
the plugin's userConfig, the session or the environment. No model runs.

Before a `write`, tell the author to commit `.claude/respeak/config.yaml`
and, when the repo has a lexicon, `.claude/respeak/lexicon-active.md`: the
render reads only what git tracks, and `write` names on stderr each one that
differs from HEAD (it still writes, exit 0).

Run exactly this command and relay its output to the user as written. When
`$ARGUMENTS` is empty, run it with `check`.

```sh
"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py $ARGUMENTS
```

- `write [--out PATH]` renders `.claude/respeak/include.md` under the git
  root, or PATH, which must resolve inside the git root. Exit 0: written.
  Exit 2: a usage error. Over 1,500 bytes it prints the size and writes
  nothing; tell the user which input made it long (usually a long
  `gate.include` list) and do not edit their config to fit.
- `check [--out PATH]` renders in memory and compares. Exit 0: current.
  Exit 1: the file is absent, stale (an input changed: the config, the
  lexicon digest, or the plugin after an update) or hand-edited; offer
  `write`. Exit 2: a usage error.

Never edit the include file by hand, and never write it under `~/.claude`.

After a `write`, list the steps left to the author, and take none of them
unless asked:

1. Commit the file at its path, and `.claude/respeak/lexicon-active.md` when
   the repo has a lexicon.
2. Import it with one line, `@.claude/respeak/include.md` (or the `--out`
   path): in `CLAUDE.md` for Claude Code, in `AGENTS.md` for other tools, or
   in both. As of Claude Code 2.1.296 (the memory docs, re-read
   2026-10-14), it reads `AGENTS.md` only in a project with no `CLAUDE.md`
   of its own.
3. Check the cap without respeak, in the repo's own check target:
   `test "$(wc -c < .claude/respeak/include.md)" -le 1500`. A repo that runs
   the shared `scripts/hygiene` adds `.claude/respeak/include.md: sibling`
   to its `.hygiene-allow`, since the file names respeak.

The author runs `check` after a config, lexicon or plugin update, then
`write`, and commits. The consuming repo's make never calls respeak.
