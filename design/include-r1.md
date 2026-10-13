# claude-code-respeak: a static include file a repo ships (include r1)

**Status:** design r1, 2026-10-11, docs only. Input: the owner's ruling of 2026-10-11, made after a study of Claude Code mods and clarified the same day. A repo's author, with respeak installed, generates the repo's default communication behavior as one static file under 1.5 KB. The file ships in that repo and is imported from its `CLAUDE.md` or `AGENTS.md` with an `@` line. Users of the repo get the behavior without installing respeak. No mod ships, and nothing runs per turn: the study found `@` imports and the `AGENTS.md` loader already feed a static file to the model.

## §1 The verb

`/respeak:include`, a new skill over a new deterministic script, `plugin/scripts/respeak-include.py` (run through `scripts/py`; no model call):

- `write [--out PATH]` renders the file. Inputs: the config resolved from the plugin defaults and the repo's tracked `.claude/respeak/config.yaml` only (`narrative` default mode and profile, `gate.include`), a new template, `plugin/config/include.md.tmpl`, that holds the mode contracts, and whether git tracks `.claude/respeak/lexicon-active.md`. The default output is `.claude/respeak/include.md`. The path is the author's choice; a plugin repo may write the file under `plugin/`.
- No layer outside git is read: not the author's userConfig, user or ancestor layers, `config.local.yaml`, the session or the environment. A personal default, such as a user-layer `default_mode`, never reaches the shipped file. The project config is read from its work-tree copy only when git's index holds it as a regular file and its real path stays inside the git root; a tracked symlink, or a path through one that leaves the root, exits 2. `check` resolves the same way.
- `check [--out PATH]` renders to memory and compares: exit 0 when current, 1 when the file differs, 2 on a usage error. Under portfolio entry 25 (exit codes report the task, not the content), `check` takes a gate's reading, as this repo's other gates do: its task is to confirm the file is current, so drift fails the task and exits 1, as `respeak-check.sh` exits 1 on a block.
- The cap is 1,500 bytes, the stricter reading of 1.5 KB. Over the cap, `write` exits 2, prints the size and writes nothing. It never truncates.
- `--out` must resolve inside the repo's git root. Nothing writes `~/.claude`.

The first line stamps the template version and a short hash of the inputs, so `check` tells a stale file from a hand-edited one.

## §2 The file

A rendered example for a repo whose config sets technical mode for a peer engineer, 1,306 bytes (`wc -c`):

```markdown
<!-- respeak include v1, inputs 3f2a9c01; regenerate with /respeak:include, do not edit -->
# How to write in this repo

Two lanes. Notes, packets, tool output and messages between agents are the
machine lane. What a person reads is the human lane: replies to the user,
and README.md, CHANGELOG.md, docs/ and design/*.md.

Machine lane: write in full. Use shorthand only for the terms in
`.claude/respeak/lexicon-active.md`, when the repo ships it. Never shorten
error messages, security findings, the user's quotes, or numbers with units.

Human lane: write for a peer engineer in technical mode: the conclusion
first, then the evidence as file:line or the command that shows it, then
open questions. When the user names another reader, switch mode:
- eli5 (a newcomer, "plain English"): one idea per sentence, at most one
  analogy, and the next sentence says the real thing.
- bluf (a manager, "bottom line"): the result, decision or ask first, with
  owner and deadline; a manager can forward it unedited.
In every mode: short sentences, active voice, concrete words, no filler
openers, no hype, no closing summary of what was just said.

The respeak plugin is optional. With it installed, `/respeak:respeak [mode]`
renders a narrative and its gate checks these rules. Without it, follow
them by hand.
```

## §3 Where a consuming repo puts it

The author commits the file at its output path, `.claude/respeak/include.md` by default, and the digest when the repo has a lexicon. The import is one line, here for the default path:

```text
@.claude/respeak/include.md
```

For Claude Code the line goes in `CLAUDE.md`. In Claude Code 2.1.296 the `AGENTS.md` loader defaults to `claude-md-or-agents-md`: it reads `AGENTS.md` only in a project with no `CLAUDE.md` of its own, so an `@` line in `AGENTS.md` does nothing beside a `CLAUDE.md`. For other tools the line goes in `AGENTS.md`. A repo that serves both puts it in both.

A user may also import a copy from their own `~/.claude/CLAUDE.md` by hand. That is optional, and no script does it.

Every rendering names respeak, and so does the default path, so hygiene's `sibling` group hits the file. A consuming repo that runs this repo's `scripts/hygiene` adds `.claude/respeak/include.md: sibling`, or the path it chose, to its `.hygiene-allow`.

## §4 Keeping it current

- **Size, for everyone.** The consuming repo checks the cap with no respeak present. One line in its own check target: `test "$(wc -c < .claude/respeak/include.md)" -le 1500`.
- **Drift, for the author.** `/respeak:include check` runs only in a Claude Code session with the plugin. The consuming repo's make never calls respeak, so a user without it never sees a red drift check. The author runs it after a config, lexicon or plugin update, then `write` and commits.
- **In this repo.** A new `tests/test_include.py` fails when the template's mode names differ from the `argument-hint` modes in `plugin/skills/respeak/SKILL.md`, or when the fixture under `examples/layered/project/` renders over the cap.

## §5 What it replaces and leaves alone

It replaces the mod the study weighed: none ships. It leaves alone the SessionStart lexicon status, the Stop narrative, the PostToolUse gate, `/respeak:init` and the digest import it offers, and this repo's `CLAUDE.md`.

## §6 Acceptance criteria

- `python3 -m unittest tests.test_include 2>&1 | tail -1` reads `OK`.
- On the fixture: `write` then `check` exits 0; after a `gate.include` edit, `check` exits 1.
- An over-cap fixture makes `write` exit 2, and the output path stays absent.
- `write --out` with a path outside the git root exits 2.
- The rendered fixture is 1,500 bytes or less, and `scripts/hygiene` finds no hit in it outside the allowlist.
- `git diff --name-only main...HEAD | grep -c '^plugin/hooks/'` reads 0.
- `make doclint` and `make hygiene` exit 0.

## §7 Open risks

- Tools other than Claude Code may not follow an `@` line in `AGENTS.md`. Those readers then miss the file; pasting it inline is the fallback.
- The stamp line counts against the cap, and readers see it.
- The template restates the agent's mode contracts in fewer words; the test pins the names only, not the wording.
- A consumer may hand-edit the file. `check` reports it, but only the author runs `check`.
