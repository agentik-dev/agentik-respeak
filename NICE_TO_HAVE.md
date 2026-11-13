# Nice to have

Findings that block nothing, one row each, in hq design/05 §2's table; `scripts/recordlint` holds it. The list before 2026-11-01 is frozen in `history/NICE-2026-11-01.md`, never edited: every item there is S4 or unlevelled, so none is open at S1 to S3 and the table below starts empty; a packet that touches an area greps the archive by path.

## Open

| id | level | area | finding | evidence | from |
|---|---|---|---|---|---|
| n1 | S3 | `plugin/scripts/respeak-plug.py` | A setting set by a `scopes:` entry gets a `change.block` for the file's top level, where the scope still wins; the note names the entry | a project `scopes[0]` setting `narrative.profile: exec` for `docs/**`, read from `docs/`: the block is `narrative:\n  default_mode: bluf` | ak9-plug-respeak |
