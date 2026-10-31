# respeak architecture

respeak renders agent work for a person. It holds one skill, one translator agent, a corpus of bad phrasing as data, a layered tone configuration, and three scripts that callers run without a session.

The machine lane left in 0.12.0 (packet `design/packets/r19-cut.md`, the owner's word of 2026-10-31): a ratified shorthand lexicon, its tooling, and a style-gate hook on every Write and Edit. It carried three terms and no traffic outside this repo. The code is in git history; `research/` keeps the studies behind it.

## The translator

`plugin/agents/respeak.md` is a subagent that reads the source, the resolved configuration and the corpus. Its only writes are rendered narratives. It runs in its own context window, so the calling session pays for the narrative alone. `respeak-render.sh` builds its system prompt from the same file, and a caller may ask for it by name as `respeak:respeak`.

| Mode | The contract |
| --- | --- |
| `eli5` | no assumed background, one analogy at most, repaid at once |
| `bluf` | the first sentence is the result, decision or ask; forwardable unedited |
| `technical` | the conclusion first, evidence as file:line, open questions last |

Every rendered narrative opens with a marker line, `📣 respeak · <mode>`, so the reader knows which voice is speaking. The headless renderer strips it from files.

## What is never compressed

`never_compress` in `plugin/config/respeak.config.yaml` holds seven classes, each with its failure story: error messages and stack traces, security findings, user quotes, numbers with units, safety and caution instructions, an ask with its owner and deadline, and identifiers, novel decisions and negations. The agent and the skill state the rule; `respeak-verify-edit.py` holds numbers across an editorial pass. A project may change the list in its committed file; a user or folder layer cannot.

## The corpus and the check

The rules are data (`plugin/corpus/*.yaml`), not prompt prose, so they are versionable and lintable. `respeak-measure.py` scans a narrative in zero tokens; the skill and the renderer rewrite up to two rounds against its report. `respeak-check.sh` applies the same scan to a repo's Markdown from committed config, for a make target or CI, and reads a setup failure as an error, never a pass. A project opts in with `gate.enabled: true` in its committed file. No hook runs any of this.

## The editorial pass

An editorial pass edits someone else's document in place. `respeak-verify-edit.py BEFORE AFTER` proves the edit prose-only: headings, block structure, links, fenced code, inline code and numbers byte-identical. `design/readme/contract.txt` and the same verifier make a README render an editorial pass rather than a summary.

## The layers

`plugin/docs/config-layers.md` is the contract: plugin defaults, userConfig, user, ancestors, project, project local, scopes, folders, the session provider, `RESPEAK_CONFIG`, the invocation; nearest wins. Tone may vary anywhere. What the check covers and what is never compressed are project decisions, and the resolver drops them from other layers with a warning.

## Who calls it

| Caller | What it runs | What must stay |
| --- | --- | --- |
| a repo's `make readme`, under `claude -p` | `/respeak:respeak technical <source>; <contract>` | the skill's `arguments: [mode, source]` |
| a repo's `scripts/readme-render` | `respeak-render.sh`, `respeak-verify-edit.py` from the installed plugin | both, with `respeak-deadline.sh`, the measure, the resolver, the corpus, the agent |
| a ledger tool's question render | `respeak-render.sh --contract` | the same |
| an overnight queue's morning report | the agent `respeak:respeak` | the agent's name |
| a repo's style target | `respeak-check.sh`, `respeak-include.py` from a source checkout | both, by path |

Each is optional for its caller: without respeak it prints its source or names the install line.
