# agentik-respeak

This repository ships the respeak plugin and uses it on itself. A session
working here follows these rules.

**The human lane.** `README.md`, `CHANGELOG.md`, the five root files as each
lands (`DECISIONS.md`, `DESIGN.md`, `NICE_TO_HAVE.md`, `OPEN-QUESTIONS.md`,
`HANDOFF.md`), top-level `design/*.md`, `design/readme/`, `docs/` and
`plugin/docs/` are read by people, in respeak technical mode for a peer
engineer. `.claude/respeak/config.yaml` lists them in `gate.include`;
`respeak-config.sh explain --for <file>` shows the register. This file,
skills, agent prompts, packets and sittings are read by a model, not gated.

**Editing a human-lane file.** Do not hand-edit prose in those files. Ask the
`respeak:respeak` agent for its technical-mode editorial pass over the file,
written to a scratch path, then prove the edit changed only prose:

```sh
python3 plugin/scripts/respeak-verify-edit.py <before> <after>            # exit 0 = safe
bash plugin/scripts/respeak-check.sh --verify HEAD                        # gate + verify every doc git knows about
```

Headings, links, fenced code, inline code, and numbers must be byte-identical
across an editorial pass. New content is written once, then passed the same
way. Under about ten new lines, the check is the pass: write the change once
and let `make doclint` check it.

**The README is rendered.** `README.md` is written by `make readme` only:
it renders `design/readme/source.md` through the translator in technical
mode, proves the render prose-only with `respeak-verify-edit.py`, and stamps
both files in `design/readme/rendered.sha256`. Edit the source, then run
`make readme`. `make check` refuses a README whose stamp no longer matches.
Links in the source are `/`-rooted, so one target resolves from the source
and from the root. The source stays at or under 24,576 bytes;
`scripts/readme-fresh.sh` enforces the ceiling.

**The check.** `make doclint` runs `respeak-check.sh`, which scans the human-lane files from the committed config. No hook runs it: this plugin ships none, and `examples/layered/project/` is gated by that fixture's own config.

**Before committing.** Run `bash plugin/scripts/respeak-check.sh` (every doc passes
its own gate) and `make check`. Use `python3` for anything Python: in this
repo it is the pyenv virtualenv `.python-version` declares,
`agentik-respeak` (3.12, with PyYAML); until the switch builds it, the
Makefile takes the venv on the file's second line, its name before agentik-r1.

**The machine lane left in 0.12.0** (`design/packets/r19-cut.md`): no lexicon, no shorthand, no digest import. The code is in git history. Past packets, sittings and `research/` keep their words.
