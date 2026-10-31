# respeak

<img src="assets/icon.svg" alt="" width="56" align="left">

respeak is a Claude Code plugin that renders agent work for a person. One skill and one translator agent write a narrative in ELI5, BLUF or technical mode, in a tone you set by layers. Error messages, security findings, user quotes and numbers with units are never compressed.

The machine lane left in 0.12.0: the shorthand lexicon, its tooling and the style-gate hook are in git history, last at commit `4cd4ec3`, removed on the owner's word of 2026-10-31.

## What it does

`/respeak:respeak [eli5|bluf|technical] [text or file]` reads the source, resolves the tone for that file, hands both to the `respeak:respeak` agent and measures what comes back against the banned-phrase corpus before you see it. The agent runs in its own context window, so the session that called it pays for one narrative and nothing else.

| Mode | The reader | The contract |
| --- | --- | --- |
| `eli5` | a newcomer | one idea per sentence, at most one analogy, and the next sentence says the real thing |
| `bluf` | a manager | the result, decision or ask first, with owner and deadline; forwardable unedited |
| `technical` | a peer engineer | the conclusion first, then evidence as file:line or a command, then open questions |

A caller may add a contract after a `;`, and a repository can render its README this way, under `claude -p`:

```sh
claude -p "/respeak:respeak technical design/readme/source.md; $(cat design/readme/contract.txt)" --allowedTools 'Read Write' --max-turns 8
```

A claim that work is done, fixed, passing or green is stated as fact only when the source holds the tool result that shows it; otherwise the narrative says claimed, not verified, and what would verify it.

## Install

Prerequisites: Claude Code ≥ 2.1.196, a plugin path without spaces, bash 3.2 or newer, and a python3 (3.9 or newer) with PyYAML. The scripts pick the first interpreter that imports PyYAML (override with `RESPEAK_PYTHON`).

One marketplace, `agentik`, lists respeak and its sibling plugins:

```sh
claude plugin marketplace add agentik-dev/agentik-commons
claude plugin install respeak@agentik
# optionally: --config default_mode=bluf --config tech_level=2
```

From a checkout, `make install` installs `respeak@agentik`, or updates it when it is already installed; it never adds or removes a marketplace. `make doctor` prints one line per check: python, claude, marketplace, plugin, provider, config.

```sh
make install
make doctor
```

The plugin needs no setup per project, and it ships no hooks: nothing runs until you call it. After pulling a change, run `claude plugin update respeak`: the installed copy under `~/.claude/plugins/cache` is a snapshot.

## Skills and scripts

| What | Use |
| --- | --- |
| `/respeak:respeak [mode] [source]` | render a narrative |
| `/respeak:include [write\|check] [--out PATH]` | a static file of a repo's writing rules, at most 1,500 bytes, loaded by an `@` line |
| `plugin/scripts/respeak-render.sh --mode M --source F --out F [--contract F]` | render with no session, for `make` targets; it measures and retries, exit 0 written, 1 still failing, 2 setup, 4 an account failure |
| `plugin/scripts/respeak-verify-edit.py BEFORE AFTER` | prove an edit changed prose only: headings, links, fenced code, inline code and numbers byte-identical |
| `plugin/scripts/respeak-check.sh [--verify REF] [FILE...]` | the style check from committed config, for a make target or CI; exit 0 clean, 1 a block, an error or a changed file, 2 setup |
| `plugin/scripts/respeak-measure.py FILE --fail-on error` | the scanner: banned phrases, em-dash density, sentence length, in zero tokens |
| `plugin/scripts/respeak-config.sh explain\|resolve\|gate\|validate` | show or check what the layers resolve to |

## Where the tone comes from

Configuration resolves from layers, and the layer nearest the target wins:

| Layer | File | Typical use |
| --- | --- | --- |
| plugin defaults | `config/respeak.config.yaml` in the plugin | the shipped contract |
| plugin userConfig | `claude plugin install respeak@agentik --config default_mode=bluf` | a quick personal default |
| user | `~/.claude/respeak/config.yaml` | your default across every repo |
| project | `.claude/respeak/config.yaml` | the project's baseline; the only place the check turns on |
| project local | `.claude/respeak/config.local.yaml` (gitignored) | your override for one repo |
| scopes | `scopes:` entries with `paths:` globs, applied right after their file | path-keyed overrides |
| folder | `.respeak.yaml` in any folder from the project root down | a folder's own audience |
| provider | the `respeak` section of `agentik-session`'s resolved file (major 2) | the session's tone; optional |
| invocation | `/respeak:respeak bluf`, `--mode`, `--set` | this one render |

Folder, user, and provider layers set tone only; `gate.enabled`, `gate.include`, `gate.exclude` and `never_compress` are project-only. The knobs are tone axes (formality, directness, confidence), `tech_level` 1–5 with audience profiles, and per-mode sentence budgets. They live in [`plugin/config/respeak.config.yaml`](/plugin/config/respeak.config.yaml). The contract and worked examples: [`plugin/docs/config-layers.md`](/plugin/docs/config-layers.md); a runnable tree: [`examples/layered/`](/examples/layered/).

## Design of record

- [`docs/architecture.md`](/docs/architecture.md): the translator, the corpus, the layers, the callers.
- [`docs/references.md`](/docs/references.md): the published sources behind each design concept.
- `research/`: the source studies; they keep their words, the machine lane's included.
- `design/packets/`: one build packet per change, with its rulings and acceptance lines; `r19-cut.md` is the cut.
- `history/sittings/`: one charter per working session.

## Tests

Each file runs alone in seconds:

| File | What it pins |
| --- | --- |
| `tests/test_measure_gate.py` | the scanner and its budgets |
| `tests/test_corpus.py` | the shipped banned-phrase rules |
| `tests/test_verify_edit.py` | the prose-only proof |
| `tests/test_config_layers.py` | the layers, the key policy, `never_compress` |
| `tests/test_provider_layer.py` | the optional session provider |
| `tests/test_include.py` | the include file |
| `tests/test_plugin_shape.py` | what ships and what callers run |
| `tests/test_readme.py` | this README's status line and shape |
| `tests/test_hygiene.py` | the name and path lint |
| `tests/test_render.sh` | the renderer, with a fake runner |
| `tests/test_check.sh` | the committed verdict and the verifier |
| `tests/test_doctor.sh` | `make doctor` |
| `tests/test_install.sh` | `make install`, with a fake `claude` |
| `tests/test_readme_fresh.sh` | the README freshness check |
| `tests/test_bounded.sh` | the vendored breaker |

## Conventions shared with the sibling plugins

respeak is one of several plugins built to the same conventions. `scripts/hygiene` (the name and path lint) and `scripts/doclint` (charters, packets, links) are byte-identical across them, pinned by hash in the Makefile. Each README is rendered from its source, and the sidecar `design/readme/rendered.sha256` holds the two hashes `make check` reads. The one sibling respeak reads is `agentik-session`, major 2, as the optional provider of the session's tone. Nothing breaks without it.

## What can go wrong

A confident wrong BLUF is worse than the raw transcript. `never_compress` and the verifier limit it; spot-check a narrative against the evidence it cites. The style check is opt-in per project and runs only when something calls it, so a project that never calls it gets no enforcement.

## Status

Status: version `0.12.0`, rendered `2026-10-31`, `275` unittest cases and `6` bash suites.

| Surface | State |
|---|---|
| Translator agent, three modes | Working |
| Corpus and scanner | Working |
| Skills: `respeak:respeak`, `/respeak:include` | Working |
| Measure and verify tools, with their suites | Working |
| Headless renderer: `respeak-render.sh` wraps `claude -p` | Working |
| Configuration resolver: `respeak-config.sh resolve\|explain\|gate\|validate` | Working |

See CHANGELOG.md for what each version changed and why.

## Layout

```
.claude/respeak/           this repo's respeak layer: the human-lane scope
.hygiene-allow             the names scripts/hygiene permits, per path
.python-version            the pyenv virtualenv the checks run under (3.12, PyYAML)
CLAUDE.md                  how a session in this repo writes and checks the docs
Makefile                   make check, make readme, make doctor, make install
assets/icon.svg            the project icon
plugin/                    the plugin, self-contained: what an install copies
plugin/.claude-plugin/     manifest + userConfig
plugin/agents/respeak.md   the translator
plugin/skills/             respeak, include
plugin/scripts/            resolver, measure, verify-edit, render, check, doctor, include
plugin/config/             plugin defaults, the include template
plugin/corpus/             banned phrases, replacements, style maps
plugin/docs/               the configuration contract
scripts/readme-render.sh   make readme: the status line, the render, the stamp
scripts/readme-fresh.sh    the README freshness check
scripts/hygiene            the name and path lint
scripts/doclint            charters, packets, and relative links
scripts/bounded            the wall, lock and load breaker make check runs under
tests/                     unittest and bash suites
design/                    the README's source and the build packets
docs/                      architecture and references
examples/layered/          a runnable tree the config tests pin
history/sittings/          one charter per working session
research/                  11 source studies, 4 synthesis passes
```

`make readme` renders this README from `design/readme/source.md` in technical mode; `make check` refuses a README older than its source.

## License

[MIT](/LICENSE); LICENSE names the copyright holder.

Third-party material: the research notes summarize published sources under
their own terms, with links. The catalog of AI-writing tells condensed in
[`research/sources/deai-language-landscape.md`](/research/sources/deai-language-landscape.md)
§1 derives from Wikipedia's
["Signs of AI writing"](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing)
by Wikipedia contributors (CC BY-SA 4.0). That section is available under
the same license. Some banned-phrase categories were informed by the
[antislop-sampler](https://github.com/sam-paech/antislop-sampler) project
(Apache-2.0); no code or text from it is included.
