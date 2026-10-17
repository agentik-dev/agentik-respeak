#!/usr/bin/env python3
"""respeak-lexicon: the shorthand lexicon's static rules.

    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py check [--root R]

Inputs, and nothing else: R/.claude/respeak/lexicon.yaml, else the plugin's
seed corpus/lexicon.yaml; and `shorthand` from the plugin defaults
(config/respeak.config.yaml) with R/.claude/respeak/config.yaml over them,
merged by the resolver's own layer merge as respeak-include.py's `resolve`
does. Shorthand governance is project-only, so the user, userConfig,
folder and local layers, the session and the environment never reach a key.
R defaults to the current directory.

`check` holds the ratified entries, the ones the digest gives the swarm, to
two keys: `shorthand.max_entries`, the cap on their count, and
`shorthand.min_token_edit_distance`, the least Levenshtein distance between
any two of their terms, case-folded. It prints a line per problem, then
one summary line:

    lexicon: ok, 2 ratified of 150, the nearest two 6 apart (min 2)

Exit: check 0 ok, 1 a problem; 2 on a usage error, a bad key value, or a
lexicon that cannot be read as entries, with one line and no traceback.
"""
import argparse
import importlib.util
import os
import sys

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
RESOLVER = os.path.join(HERE, "respeak-config.py")
DEFAULTS = os.path.join(PLUGIN_ROOT, "config", "respeak.config.yaml")
SEED = os.path.join(PLUGIN_ROOT, "corpus", "lexicon.yaml")
PROJECT_REL = os.path.join(".claude", "respeak", "config.yaml")
LEXICON_REL = os.path.join(".claude", "respeak", "lexicon.yaml")
STATUSES = ("proposed", "ratified", "retired")


class Usage(Exception):
    pass


def warn(msg):
    print("respeak-lexicon: %s" % msg, file=sys.stderr)


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def load_resolver():
    spec = importlib.util.spec_from_file_location("respeak_config", RESOLVER)
    if spec is None or spec.loader is None:
        raise Usage("no resolver at %s" % RESOLVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        layer = rc.file_layer("project", project, root, warnings)
        if not layer.present:
            raise Usage("%s unreadable: %s" % (PROJECT_REL, "; ".join(warnings) or "not a file"))
        layers.append(layer)
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


def governance(root):
    """The keys this script reads, each checked; a bad value is a Usage."""
    sh = shorthand(root)
    gov = {}
    for key in ("max_entries", "min_token_edit_distance"):
        value = sh.get(key)
        if not whole(value) or value < 1:
            raise Usage("shorthand.%s must be a whole number of 1 or more, not %r" % (key, value))
        gov[key] = value
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
        if leg is not None and (isinstance(leg, bool) or not isinstance(leg, (int, float))
                                or not 0 <= leg <= 1):
            raise Usage("%s (%s): legibility must be a number from 0 to 1, not %r"
                        % (where, e["term"], leg))
    return entries


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


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(prog="respeak-lexicon.py",
                                description="The shorthand lexicon's static rules.")
    sub = p.add_subparsers(dest="verb", required=True, metavar="{check}")
    s = sub.add_parser("check", help="hold the ratified entries to the cap and the edit distance")
    s.add_argument("--root", metavar="R", default=".",
                   help="the project directory (default: the current one)")
    args = p.parse_args(argv)
    try:
        root = os.path.realpath(args.root)
        if not os.path.isdir(root):
            raise Usage("not a directory: %s" % args.root)
        return check(root)
    except Usage as e:
        warn(str(e))
        return 2
    except OSError as e:
        warn("cannot run: %s" % (e.strerror or e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
