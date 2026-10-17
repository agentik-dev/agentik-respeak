---
name: audit
description: >
  Run the shorthand lexicon's fresh-decoder audit when it is due: a fresh
  agent reads today's sample of ratified terms unaided, and the audit
  records what it decoded. User-invoked only.
disable-model-invocation: true
allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/py respeak-lexicon.py *)
---

# respeak — audit the lexicon's legibility

Steps:

1. Run
   `"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py due --root "${CLAUDE_PROJECT_DIR}"`.
   Stop unless a line begins `audit: due`: relay its `audit:` line and end.
   The sample is the terms after `sample: ` on that line, joined by `, `;
   `sample: none` holds no term: say so and end.
2. Give the sample's terms alone, nothing else from the lexicon, to a fresh
   `general-purpose` agent, the terms one a line after this prompt: "Read
   no file. Write `<term>: <meaning>` for each". It counts as fresh though
   it loads the project's CLAUDE.md, a lexicon digest that file imports
   included: it reads no file, and its first guess is the reading.
3. Pass its `<term>: <meaning>` lines to the audit on stdin, verbatim, in a
   heredoc (no temp file, so no file-write permission is needed):
   ```
   "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py audit --root "${CLAUDE_PROJECT_DIR}" <<'RESPEAK_EOF'
   <the agent's lines, verbatim>
   RESPEAK_EOF
   ```
4. Relay its output verbatim: a line a term, decoded or missed, then
   `audit: D of N decoded, audited <date>`. It set the lexicon's
   `audited:` line, then appended the readings to
   `.claude/respeak/audits.jsonl`, both for a person to commit. A refusal
   writes nothing: name it in one line. A failure between the two leaves
   the stamp set and no records: name it, and run step 3 again today to
   record them.
