---
name: respeak
description: >
  Render agent output or a file as a human-facing narrative. Fires on
  /respeak:respeak [mode] [source] and on asks like "explain that to my manager",
  "give me the ELI5", "make this readable".
argument-hint: "[eli5|bluf|technical] [text or file path — defaults to this session's latest outcome]"
arguments: [mode, source]
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/scripts/py *)
---

# respeak: render a narrative

The invocation: `$ARGUMENTS`. A caller may add a contract after a `;`, as in
`/respeak:respeak technical design/readme/source.md; <contract>`: the source is
then the path before the `;`, and the contract binds this render, where to write
included.

Effective configuration for this directory:

!`"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" explain --brief --launch-dir "${CLAUDE_PROJECT_DIR}"`

**Never compress.** In every mode these pass verbatim: error messages and stack
traces, security findings, user quotes, numbers with units, safety and caution
instructions, an ask with its owner and deadline, identifiers, novel decisions
and negations.

1. **The mode.** `$mode` if it is `eli5`, `bluf` or `technical`; otherwise infer
   it from the audience named (a child, a newcomer, "plain English": eli5; a
   manager, "bottom line", "leadership": bluf; an engineer, a reviewer, "for the
   docs": technical); otherwise the effective `narrative.default_mode` above.
2. **The source.** `$source` if given, text or a readable file path, without a
   trailing `;`; otherwise this session's latest substantive outcome.
3. **The configuration.** The target is the source file when there is one (a
   folder's `.respeak.yaml` governs the files in it), else the working directory:
   `"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" resolve --for "<target>" --launch-dir "${CLAUDE_PROJECT_DIR}" [--mode <mode>] [--profile <name>] --format yaml --out "/tmp/respeak-${CLAUDE_CODE_SESSION_ID}.yaml"`
   Add `--profile` when the user named an audience matching a `profiles:` entry.
4. **The render.** Delegate to the `respeak:respeak` agent with the mode, that
   file's contents under the heading `Resolved respeak configuration`, the source,
   any contract, and the working directory. When a contract names a file, or the
   agent tool is refused, as under `claude -p --allowedTools 'Read Write'`, follow
   `${CLAUDE_PLUGIN_ROOT}/agents/respeak.md` yourself, with no try at the agent, in
   seven turns, since such a caller may set `--max-turns 8`: (1) in one message,
   step 3 with reads of the source, that agent file and, from the plugin's `corpus/`
   and the project's `.claude/respeak/`, `banned-phrases.yaml`, `replacements.yaml`
   and `style/tone-mapping.md`; (2) the resolved file; (3-5) step 5 with its two
   rewrites; (6) the Write; (7) the answer. Read nothing else.
5. **The check.** Trust no narrative unmeasured. Feed it to the scanner on stdin:
   ```
   "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-measure.py - --fail-on error --config "/tmp/respeak-${CLAUDE_CODE_SESSION_ID}.yaml" <<'RESPEAK_EOF'
   <the narrative, verbatim>
   RESPEAK_EOF
   ```
   Exit 1: rewrite to clear every error-severity hit and check again, at most 2
   rounds. Still failing: go on, with the final report appended under
   `respeak gate: still failing after 2 rounds`, so the reader sees what did not clear.
6. **The answer.** Relay the narrative verbatim, its `📣 respeak · <mode>` marker
   line first, with no commentary. When a contract names a file, write the
   narrative alone there: no marker line, no `gate:` or `config:` line, no report
   from step 5. Answer with the path and any of those lines.
