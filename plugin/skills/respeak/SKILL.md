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
the path before the `;`, and the contract binds this render.

Effective configuration for this directory:
!`"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" explain --brief --launch-dir "${CLAUDE_PROJECT_DIR}"`

**Never compress.** In every mode these pass verbatim: error messages and stack
traces, security findings, user quotes, numbers with units, safety and caution
instructions, an ask with its owner and deadline, identifiers, novel decisions
and negations.

**A contract naming a file, or a denied Bash or Agent call: Read and Write only.**
Assume no Bash, no Edit and no agent, and skip the steps below, in three turns:
(1) in one message, Read the source, the file the contract names if it exists, and
from `${CLAUDE_PLUGIN_ROOT}/` `agents/respeak.md`, `config/respeak.config.yaml`,
`corpus/banned-phrases.yaml`, `corpus/replacements.yaml` and
`corpus/style/tone-mapping.md`, with the project's `.claude/respeak/` copies; read
nothing after it. (2) Make the pass by the agent file and Write the file once, the
narrative alone: no marker line, no `gate:` or `config:` line. (3) Answer with the
path in one short line, or with no file named, the narrative. No retry of a denied
tool, no second rewrite. This path runs no measure and no verifier: what it writes
is unmeasured.

Where Bash works, the fuller path:
1. **The mode.** `$mode` if it is `eli5`, `bluf` or `technical`; otherwise by the
   audience named (a child, "plain English": eli5; a manager, "bottom line": bluf;
   an engineer, "for the docs": technical); otherwise `narrative.default_mode` above.
2. **The source.** `$source` if given, text or a readable file path, without a
   trailing `;`; otherwise this session's latest substantive outcome.
3. **The configuration.** The target is the source file when there is one (a
   folder's `.respeak.yaml` governs the files in it), else the working directory:
   `"${CLAUDE_PLUGIN_ROOT}/scripts/respeak-config.sh" resolve --for "<target>" --launch-dir "${CLAUDE_PROJECT_DIR}" [--mode <mode>] [--profile <name>] --format yaml --out "/tmp/respeak-${CLAUDE_CODE_SESSION_ID}.yaml"`
   Add `--profile` when the user named an audience matching a `profiles:` entry.
4. **The render.** Delegate to the `respeak:respeak` agent with the mode, that
   file's contents under the heading `Resolved respeak configuration`, the source,
   any contract, and the working directory; where it is refused, follow `agents/respeak.md`.
5. **The check.** Trust no narrative unmeasured. Feed it to the scanner on stdin:
   ```
   "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-measure.py - --fail-on error --config "/tmp/respeak-${CLAUDE_CODE_SESSION_ID}.yaml" <<'RESPEAK_EOF'
   <the narrative, verbatim>
   RESPEAK_EOF
   ```
   Exit 1: rewrite to clear every error-severity hit and check again, at most 2
   rounds. Still failing: go on, the final report under `respeak gate: still failing after 2 rounds`.
6. **The answer.** Relay the narrative verbatim, its `📣 respeak · <mode>` marker
   line first, with no commentary. A file holds the narrative alone: no marker
   line, no `gate:` or `config:` line, no report from step 5.
