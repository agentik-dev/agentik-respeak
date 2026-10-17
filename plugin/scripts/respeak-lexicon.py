#!/usr/bin/env python3
"""respeak-lexicon: the shorthand lexicon's static rules, its use record, and
the ratification verdict.

    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py check [--root R]
    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py use TERM --outcome clean|failure \
        [--readback] [--source S] [--root R]
    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py ratify [--root R]

Inputs, and nothing else: R/.claude/respeak/lexicon.yaml, else the plugin's
seed corpus/lexicon.yaml; and `shorthand` from the plugin defaults
(config/respeak.config.yaml) with R/.claude/respeak/config.yaml over them,
merged by the resolver's own layer merge as respeak-include.py's `resolve`
does. As there, the project file is read only when git tracks it as a
regular file: an untracked or ignored one is named on stderr and not read,
and a tracked symlink, or a path that resolves outside R, is refused.
Shorthand governance is project-only, so the user, userConfig, folder and
local layers, the session and the environment never reach a key. R
defaults to the current directory.

`check` holds the ratified entries, the ones the digest gives the swarm, to
two keys: `shorthand.max_entries`, the cap on their count, and
`shorthand.min_token_edit_distance`, the least Levenshtein distance between
any two of their terms, case-folded. It prints a line per problem, then
one summary line:

    lexicon: ok, 2 ratified of 150, the nearest two 6 apart (min 2)

`use` records one use of a lexicon term in R/.claude/respeak/uses.jsonl,
committed beside the lexicon: one JSON object a line, appended with one
O_APPEND write and never rewritten, its keys `term`, `date` (YYYY-MM-DD,
UTC today, or RESPEAK_TODAY when set), `outcome` (clean | failure),
`readback` (true with --readback), then `source` when given. It refuses a
term the lexicon lacks or has retired, a bad date, and a root with no
.claude/respeak/. It is the file's only writer; a reader skips a line that
is not such a record and names it on stderr.

`ratify` judges each `status: proposed` entry, in file order, by
`shorthand.auto`: it is eligible when its clean uses reach `auto.uses`
(with `auto.readback_evidence` true, only a clean use with readback
counts), its failure uses stay within `auto.fidelity_failures_allowed`, it
is `min_token_edit_distance` or more from each ratified term, fewer than
`max_entries` are ratified, and its legibility meets `legibility_floor`.
A line an entry, `<term>: eligible` or `<term>: not eligible: ` and the
reasons in that order, joined by `; `; then
`ratify: P proposed, E eligible; shorthand.ratification: V`. It writes
nothing: a person ratifies.

Exit: check 0 ok, 1 a problem; use 0 recorded; ratify 0 whatever the
verdicts; each 2 on a usage error, a bad key value, a lexicon that cannot
be read as entries, or a refusal, with one line and no traceback.
"""
import argparse
import datetime
import importlib.util
import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.stderr.write(
        "respeak-lexicon: PyYAML is required (python3 -m pip install pyyaml); "
        "scripts/py picks an interpreter that has it\n")
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
RESOLVER = os.path.join(HERE, "respeak-config.py")
INCLUDE = os.path.join(HERE, "respeak-include.py")
DEFAULTS = os.path.join(PLUGIN_ROOT, "config", "respeak.config.yaml")
SEED = os.path.join(PLUGIN_ROOT, "corpus", "lexicon.yaml")
PROJECT_REL = os.path.join(".claude", "respeak", "config.yaml")
LEXICON_REL = os.path.join(".claude", "respeak", "lexicon.yaml")
USES_REL = os.path.join(".claude", "respeak", "uses.jsonl")
STATUSES = ("proposed", "ratified", "retired")
OUTCOMES = ("clean", "failure")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class Usage(Exception):
    pass


def warn(msg):
    print("respeak-lexicon: %s" % msg, file=sys.stderr)


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Usage("no %s at %s" % (name, path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_resolver():
    return load("respeak_config", RESOLVER)


def tracked(root, rel):
    """Whether git tracks rel under root as a regular file, by
    respeak-include.py's own `tracked_file`: a tracked symlink, or a path
    that resolves outside root, is refused. Outside a git work tree nothing
    is tracked."""
    inc = load("respeak_include", INCLUDE)
    try:
        inc.git_root(root)
    except inc.Usage:
        return False
    try:
        return inc.tracked_file(root, rel)
    except inc.Usage as e:
        raise Usage(str(e))


def shorthand(root):
    """`shorthand` from the plugin defaults with the project file over them,
    through the resolver's layer merge; no other layer is read."""
    rc = load_resolver()
    warnings = []
    layers = [rc.file_layer("plugin", DEFAULTS, PLUGIN_ROOT, warnings)]
    if not layers[0].present:
        raise Usage("plugin defaults unreadable at %s %s" % (DEFAULTS, "; ".join(warnings)))
    project = os.path.join(root, PROJECT_REL)
    if os.path.lexists(project):
        if tracked(root, PROJECT_REL):
            layer = rc.file_layer("project", project, root, warnings)
            if not layer.present:
                raise Usage("%s unreadable: %s" % (PROJECT_REL, "; ".join(warnings) or "not a file"))
            layers.append(layer)
        else:
            warn("%s is not tracked by git; not read, the plugin defaults apply alone" % PROJECT_REL)
    cfg, origins, applied = {}, {}, []
    for layer in layers:
        data = {k: v for k, v in layer.data.items() if k != "scopes"}
        rc.apply_layer(cfg, origins, layer, data, root, warnings, applied)
    for w in warnings:
        warn(w)
    sh = cfg.get("shorthand")
    if not isinstance(sh, dict):
        raise Usage("shorthand must be a mapping")
    return sh


def whole(value):
    return isinstance(value, int) and not isinstance(value, bool)


def fraction(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and 0 <= value <= 1)


def governance(root):
    """The keys this script reads, each checked; a bad value is a Usage."""
    sh = shorthand(root)
    gov = {}
    for key in ("max_entries", "min_token_edit_distance"):
        value = sh.get(key)
        if not whole(value) or value < 1:
            raise Usage("shorthand.%s must be a whole number of 1 or more, not %r" % (key, value))
        gov[key] = value
    auto = sh.get("auto")
    if not isinstance(auto, dict):
        raise Usage("shorthand.auto must be a mapping, not %r" % (auto,))
    for key, low in (("uses", 1), ("fidelity_failures_allowed", 0)):
        value = auto.get(key)
        if not whole(value) or value < low:
            raise Usage("shorthand.auto.%s must be a whole number of %d or more, not %r"
                        % (key, low, value))
    if not isinstance(auto.get("readback_evidence"), bool):
        raise Usage("shorthand.auto.readback_evidence must be true or false, not %r"
                    % (auto.get("readback_evidence"),))
    gov["auto"] = auto
    if not fraction(sh.get("legibility_floor")):
        raise Usage("shorthand.legibility_floor must be a number from 0 to 1, not %r"
                    % (sh.get("legibility_floor"),))
    gov["legibility_floor"] = sh["legibility_floor"]
    if sh.get("ratification") not in ("human", "auto"):
        raise Usage("shorthand.ratification must be human or auto, not %r" % (sh.get("ratification"),))
    gov["ratification"] = sh["ratification"]
    return gov


def lexicon_path(root):
    project = os.path.join(root, LEXICON_REL)
    return (project, LEXICON_REL) if os.path.lexists(project) else (SEED, SEED)


def lexicon(root):
    """The entries, each a mapping with a string term and a known status."""
    path, shown = lexicon_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise Usage("%s unreadable: %s" % (shown, str(e).splitlines()[0] if str(e) else e))
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise Usage("%s: no `entries:` list" % shown)
    for i, e in enumerate(entries):
        where = "%s: entries[%d]" % (shown, i)
        if not isinstance(e, dict):
            raise Usage("%s is not a mapping" % where)
        if not isinstance(e.get("term"), str) or not e["term"].strip():
            raise Usage("%s: term must be a non-empty string, not %r" % (where, e.get("term")))
        if e.get("status") not in STATUSES:
            raise Usage("%s (%s): status must be one of %s, not %r"
                        % (where, e["term"], ", ".join(STATUSES), e.get("status")))
        leg = e.get("legibility")
        if leg is not None and not fraction(leg):
            raise Usage("%s (%s): legibility must be a number from 0 to 1, not %r"
                        % (where, e["term"], leg))
    return entries


def is_date(text):
    if not isinstance(text, str) or not DATE_RE.match(text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def why_not_use(rec):
    """Why rec is not a use record, or None when it is one."""
    if not isinstance(rec, dict):
        return "not a JSON object"
    if not isinstance(rec.get("term"), str) or not rec["term"]:
        return "no term"
    if not is_date(rec.get("date")):
        return "no YYYY-MM-DD date"
    if rec.get("outcome") not in OUTCOMES:
        return "outcome is not clean or failure"
    if not isinstance(rec.get("readback"), bool):
        return "readback is not true or false"
    if "source" in rec and not isinstance(rec["source"], str):
        return "source is not a string"
    return None


def uses(root):
    """The use records in R/.claude/respeak/uses.jsonl, in file order; [] with
    no file. A line that is not a record is skipped and named on stderr."""
    try:
        with open(os.path.join(root, USES_REL), "rb") as f:
            raw = f.read()
    except FileNotFoundError:
        return []
    except OSError as e:
        raise Usage("%s unreadable: %s" % (USES_REL, e.strerror or e))
    records = []
    lines = raw.split(b"\n")
    if lines[-1] == b"":
        lines.pop()  # the file's last newline ends a line; it starts none
    for n, line in enumerate(lines, 1):
        try:
            rec = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            rec, why = None, "not JSON"
        else:
            why = why_not_use(rec)
        if why:
            warn("%s:%d: %s; skipped" % (USES_REL, n, why))
            continue
        records.append(rec)
    return records


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------

def distance(a, b):
    """Levenshtein distance between two terms, case-folded."""
    a, b = a.casefold(), b.casefold()
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def ratified(entries):
    return [e["term"] for e in entries if e["status"] == "ratified"]


def check(root):
    gov = governance(root)
    terms = ratified(lexicon(root))
    cap, least = gov["max_entries"], gov["min_token_edit_distance"]
    problems = []
    if len(terms) > cap:
        problems.append("over the cap: %d ratified, max_entries %d" % (len(terms), cap))
    nearest = None
    for i, a in enumerate(terms):
        for b in terms[i + 1:]:
            d = distance(a, b)
            nearest = d if nearest is None else min(nearest, d)
            if d < least:
                problems.append("too near: %s and %s, %d apart (min %d)" % (a, b, d, least))
    for p in problems:
        print(p)
    n = len(problems)
    head = "ok" if not n else "%d problem%s" % (n, "" if n == 1 else "s")
    near = ("no two to compare" if nearest is None
            else "the nearest two %d apart" % nearest)
    print("lexicon: %s, %d ratified of %d, %s (min %d)" % (head, len(terms), cap, near, least))
    return 1 if n else 0


def plural(n, word):
    return "%d %s%s" % (n, word, "" if n == 1 else "s")


def ratify(root):
    gov = governance(root)
    entries = lexicon(root)
    records = uses(root)
    terms = ratified(entries)
    auto, floor = gov["auto"], gov["legibility_floor"]
    need, allowed, readback = auto["uses"], auto["fidelity_failures_allowed"], auto["readback_evidence"]
    cap, least = gov["max_entries"], gov["min_token_edit_distance"]
    proposed = [e for e in entries if e["status"] == "proposed"]
    eligible = 0
    for e in proposed:
        mine = [r for r in records if r["term"] == e["term"]]
        clean = sum(1 for r in mine if r["outcome"] == "clean" and (r["readback"] or not readback))
        failures = sum(1 for r in mine if r["outcome"] == "failure")
        reasons = []
        if clean < need:
            reasons.append("%d of %d clean uses%s" % (clean, need, " with readback" if readback else ""))
        if failures > allowed:
            reasons.append("%s, %d allowed" % (plural(failures, "fidelity failure"), allowed))
        for t in terms:
            d = distance(e["term"], t)
            if d < least:
                reasons.append("%d apart from %s, min %d" % (d, t, least))
        if len(terms) >= cap:
            reasons.append("the cap, %d ratified" % len(terms))
        leg = e.get("legibility")
        if leg is None or leg < floor:
            reasons.append("legibility %s, floor %s" % ("none" if leg is None else "%g" % leg,
                                                        "%g" % floor))
        if reasons:
            print("%s: not eligible: %s" % (e["term"], "; ".join(reasons)))
        else:
            eligible += 1
            print("%s: eligible" % e["term"])
    print("ratify: %d proposed, %d eligible; shorthand.ratification: %s"
          % (len(proposed), eligible, gov["ratification"]))
    return 0


def today():
    given = os.environ.get("RESPEAK_TODAY")
    if not given:
        return datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    if not is_date(given):
        raise Usage("RESPEAK_TODAY must be a YYYY-MM-DD date, not %r" % given)
    return given


def use(root, term, outcome, readback, source):
    if not os.path.isdir(os.path.join(root, ".claude", "respeak")):
        raise Usage("no .claude/respeak/ under %s; /respeak:init creates it" % root)
    statuses = [e["status"] for e in lexicon(root) if e["term"] == term]
    if not statuses:
        raise Usage("%s is not a lexicon term; refused" % term)
    if all(s == "retired" for s in statuses):
        raise Usage("%s is retired; refused" % term)
    rec = {"term": term, "date": today(), "outcome": outcome, "readback": readback}
    if source is not None:
        rec["source"] = source
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    path = os.path.join(root, USES_REL)
    try:
        fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
                     0o644)
    except OSError as e:
        raise Usage("cannot append to %s: %s" % (USES_REL, e.strerror or e))
    try:
        size = os.fstat(fd).st_size
        if size and os.pread(fd, 1, size - 1) != b"\n":
            line = b"\n" + line  # a last line cut short stays its own line
        if os.write(fd, line) != len(line):
            raise Usage("%s: a short write; the last line may be cut" % USES_REL)
    finally:
        os.close(fd)
    print("use: %s %s%s on %s, recorded in %s" % (term, outcome, " with readback" if readback else "",
                                                   rec["date"], USES_REL))
    return 0


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="respeak-lexicon.py",
                                description="The shorthand lexicon's static rules, its use "
                                            "record, and the ratification verdict.")
    sub = p.add_subparsers(dest="verb", required=True, metavar="{check,use,ratify}")
    s = sub.add_parser("check", help="hold the ratified entries to the cap and the edit distance")
    u = sub.add_parser("use", help="append one use of a term to .claude/respeak/uses.jsonl")
    u.add_argument("term", metavar="TERM")
    u.add_argument("--outcome", required=True, choices=OUTCOMES)
    u.add_argument("--readback", action="store_true", help="the reader read the term back")
    u.add_argument("--source", metavar="S", help="where the use was seen")
    v = sub.add_parser("ratify", help="judge each proposed entry by shorthand.auto; write nothing")
    for x in (s, u, v):
        x.add_argument("--root", metavar="R", default=".",
                       help="the project directory (default: the current one)")
    args = p.parse_args(argv)
    try:
        root = os.path.realpath(args.root)
        if not os.path.isdir(root):
            raise Usage("not a directory: %s" % args.root)
        if args.verb == "use":
            return use(root, args.term, args.outcome, args.readback, args.source)
        if args.verb == "ratify":
            return ratify(root)
        return check(root)
    except Usage as e:
        warn(str(e))
        return 2
    except OSError as e:
        warn("cannot run: %s" % (e.strerror or e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
