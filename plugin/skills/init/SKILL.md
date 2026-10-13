---
name: init
description: >
  Set up respeak here: state dirs, a config listing the human-lane files,
  the lexicon and its digest; with consent, the include file and its
  import, gitignore entries, the statusline. User-invoked only.
disable-model-invocation: true
argument-hint: "(no arguments)"
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh *) Bash(bash ${CLAUDE_PLUGIN_ROOT}/scripts/render-lexicon-digest.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/py respeak-include.py *) Bash(git rev-parse --show-toplevel) Bash(git add .claude/respeak/*)
---

# respeak project setup

Perform these steps in the current project, reporting each as done/skipped:

1. Create `.claude/respeak/` and `.claude/respeak/proposals/` if missing.
2. Seed project state from the plugin if the files don't exist yet (never
   overwrite existing project files). First note whether
   `.claude/respeak/lexicon.yaml` exists already: only then does the repo
   have its own lexicon (step 6).
   - `.claude/respeak/config.yaml` ← `${CLAUDE_PLUGIN_ROOT}/config/project-seed.yaml`.
     Propose its `gate.include` first: run
     `"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py propose --root "${CLAUDE_PROJECT_DIR}"`.
     It prints one YAML flow list on one line: the human-lane files present
     at the root (`README.md`, `CHANGELOG.md`, `DECISIONS.md`, `DESIGN.md`,
     `NICE_TO_HAVE.md`, `OPEN-QUESTIONS.md`, `HANDOFF.md`, and the
     `docs/`, `design/readme/` and `plugin/docs/` globs that match a file),
     or `["**/*.md"]` when none is. Show the user that list and
     `narrative.profile: peer-engineer`, and ask whether to seed with them.
     With consent, replace the seed's `include: ["**/*.md"]` value with the
     printed list, verbatim, and add `narrative:` with `profile:
     peer-engineer` in place of the commented example. Without consent, or
     when `propose` exits 2 (no git work tree), copy the seed as it is.
     The seed is deliberately sparse: `version`, a `gate:` block (`enabled:
     false`, `include`, `exclude: []`, `fail_on: error`, `allow: []`), and
     commented examples of `narrative:`, `hooks:` and `scopes:`.
     Do not copy the full plugin config: a project file that restates every
     default pins every key and hides the user's own
     `~/.claude/respeak/config.yaml` (docs/config-layers.md, "Upgrading").
     The PostToolUse style gate (`scripts/respeak-gate.sh`) is seeded OFF; a
     human turns it on by editing `gate.enabled` to `true` once the project
     trusts its excludes/allow list. `/respeak:on gate` runs it for one session
     first, as a trial, without editing anything. Only this file (or `config.local.yaml`)
     can turn it on.
   - `.claude/respeak/lexicon.yaml` ← `${CLAUDE_PLUGIN_ROOT}/corpus/lexicon.yaml`
3. Generate the lexicon digest: run
   `bash "${CLAUDE_PLUGIN_ROOT}/scripts/render-lexicon-digest.sh"` — it writes
   `.claude/respeak/lexicon-active.md` (ratified terms only, compact table).
4. Show the effective configuration stack: run
   `"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" explain --launch-dir "${CLAUDE_PROJECT_DIR}"`
   and report which layers exist (a user-level `~/.claude/respeak/config.yaml`,
   an ancestor `.respeak.yaml` above the project, the file just seeded), any
   warnings, and the closing `session overrides:` line. If `project:` names a directory other than this one (a
   parent directory carries its own `.claude/respeak/config.yaml`, or a
   nested package does), say so: that file, not the seeded one, governs
   the files under it. If the user wants a folder-specific tone now, create
   `<folder>/.respeak.yaml` with only the keys that differ (for example
   `narrative: {profile: exec}`) and validate it with
   `"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" validate "<folder>/.respeak.yaml"`.
5. Ask the user (do not do it silently) whether to add these two lines to the
   project's `.gitignore`, so personal overrides never get committed:
   `.claude/respeak/config.local.yaml` and `.respeak.local.yaml`.
6. The include file, the repo's default writing rules for a reader without
   respeak (`/respeak:include`). `write` reads the config and writes the file
   at the git root, so first run `git rev-parse --show-toplevel`. When it
   prints a directory other than `${CLAUDE_PROJECT_DIR}` (compare real paths:
   the project sits below the git root), skip both the write and the
   `@.claude/respeak/include.md` import, and say why in one line: the include
   would render the git root's config, not this project's, and land where
   this project's import cannot reach it. At the git root, ask the user
   whether to render it now. It reads the config and the digest only once git
   tracks them, and step 3 wrote the digest, so with consent stage both, so
   the include renders from what the author will commit
   (`git add .claude/respeak/config.yaml .claude/respeak/lexicon-active.md`),
   then run `"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py write` and
   relay its output as written, including the lines that name a file with
   uncommitted changes: the author commits those with the include. Then ask
   whether to add these lines to the project's `CLAUDE.md`:
   - `@.claude/respeak/include.md`, so every session loads the rules (at the
     git root only, as above);
   - `@.claude/respeak/lexicon-active.md`, so every session loads the
     ratified lexicon, offered only when the repo had its own
     `.claude/respeak/lexicon.yaml` before step 2.
7. Ask the user whether to install the statusline segment; if yes, set in
   `.claude/settings.json`:
   `"statusLine": {"type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT}/scripts/statusline.sh\""}`
   (If a statusLine already exists, show it and let the user decide.) The
   segment shows the effective mode and, when a nearer layer decided it,
   which file: `respeak bluf/t1 exec @docs/exec/.respeak.yaml · lexicon v0 · 0 proposals`.
8. Report: paths created, seeds copied, digest entry count, the layers
   `explain` found, which integrations the user accepted, whether the
   plugin root `${CLAUDE_PLUGIN_ROOT}` contains a space (if it does, say
   that `/respeak:respeak` will abort its permission check under default
   permissions until the plugin is reinstalled under a space-free path;
   the hooks still work), and the gate's current state (`gate: disabled (default) — enable in
   .claude/respeak/config.yaml` or, if the user asks to turn it on now, edit
   `gate.enabled: true` there and confirm `gate.include`/`gate.exclude`
   match the project's layout). Close by naming the two ways to change
   respeak's behavior later without editing this file: `/respeak:off` and
   `/respeak:on [gate]` for the current session, and the gitignored
   `.claude/respeak/config.local.yaml` for a durable personal preference.
   Say that the SessionStart lexicon note is off by default and that
   `hooks: {session_start: true}` in the config turns it on.
