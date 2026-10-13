#!/usr/bin/env python3
"""respeak-include: render or check a repo's static include file (design/include-r1.md).

    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py write [--out PATH]
    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py check [--out PATH]
    "${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-include.py propose [--root R]

The file holds the repo's default communication rules, at most 1,500 bytes,
and ships in the repo; CLAUDE.md or AGENTS.md imports it with an `@` line,
so a reader without respeak still gets the rules. No model is called.

Inputs, and nothing else: the plugin defaults (config/respeak.config.yaml),
the repo's .claude/respeak/config.yaml when git tracks it as a regular file
(its work-tree copy, refused when it is a symlink or resolves outside the
root; `scopes:` is not read, since the file is repo-wide), the template
config/include.md.tmpl, and whether git tracks
.claude/respeak/lexicon-active.md. The user, userConfig, ancestor, folder
and local layers, the session and the environment never reach the file.
The repo is the git work tree of the current directory.

`--out` defaults to .claude/respeak/include.md under the git root; a
relative PATH is read from the current directory and must resolve inside
the git root (not under .git, never under ~/.claude). The first line stamps
the template version and a short hash of the inputs, so `check` tells a
stale file from a hand-edited one.

After a write, each tracked input it rendered from (the config, the
lexicon digest) that differs from HEAD is named on stderr, one line each;
the exit stays 0.

`propose` prints, for /respeak:init, the gate.include list of the
human-lane files present at R (default: the current directory), as one
YAML flow list on one line; with none present, the seed's ["**/*.md"].
It reads no config and writes nothing.

Exit: write 0 written; check 0 current, 1 drift (absent, stale or
hand-edited); propose 0 printed; each 2 on a usage error: arguments, no git
work tree, an --out outside the git root, an unreadable input, or a render
over the cap (write then prints the size and writes nothing), and 2 on an
OS error reading or writing the file, with one line and no traceback.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HERE)
RESOLVER = os.path.join(HERE, "respeak-config.py")
DEFAULTS = os.path.join(PLUGIN_ROOT, "config", "respeak.config.yaml")
TEMPLATE = os.path.join(PLUGIN_ROOT, "config", "include.md.tmpl")
PROJECT_REL = ".claude/respeak/config.yaml"
LEXICON_REL = ".claude/respeak/lexicon-active.md"
DEFAULT_OUT = ".claude/respeak/include.md"
REGULAR = ("100644", "100755")
CAP = 1500
WIDTH = 76
GIT_TIMEOUT = 30
REQUIRED = ("version", "stamp", "body", "switch", "shorthand lexicon", "shorthand none", "readers")
MODE_KEYS = ("reader", "cue", "contract")
STAMP_RE = re.compile(r"^<!-- respeak include v(\S+), inputs ([0-9a-f]{8});")
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
# propose: the human lane, in this order; a file counts when it is present
# at the root, a glob when it matches at least one file
HUMAN_FILES = ("README.md", "CHANGELOG.md", "DECISIONS.md", "DESIGN.md", "NICE_TO_HAVE.md",
               "OPEN-QUESTIONS.md", "HANDOFF.md")
HUMAN_GLOBS = ("docs/**/*.md", "design/readme/**/*.md", "plugin/docs/**/*.md")
FALLBACK = ["**/*.md"]


class Usage(Exception):
    pass


def warn(msg):
    print("respeak-include: %s" % msg, file=sys.stderr)


# --------------------------------------------------------------------------
# git and paths
# --------------------------------------------------------------------------

def git(cwd, *args):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=GIT_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Usage("git failed: %s" % e)


def git_root(cwd):
    p = git(cwd, "rev-parse", "--show-toplevel")
    top = p.stdout.strip()
    if p.returncode != 0 or not top:
        raise Usage("not inside a git work tree: %s" % cwd)
    return os.path.realpath(top)


def index_mode(root, rel):
    """The mode git's index holds rel at ("100644", "120000", ...), or None
    when git does not track it."""
    p = git(root, "ls-files", "-s", "-z", "--", rel)
    if p.returncode != 0:
        raise Usage("git failed: git ls-files %s: %s" % (rel, p.stderr.strip()))
    entry = p.stdout.split("\0", 1)[0]
    return entry.split(" ", 1)[0] if entry else None


def tracked_file(root, rel):
    """Whether git tracks rel as a regular file whose work-tree copy is a
    regular file, not a symlink, with its real path inside the root. A
    tracked symlink, or a path through one that leaves the root, is
    refused: either would let a file outside git into the render."""
    mode = index_mode(root, rel)
    if mode is None:
        return False
    path = os.path.join(root, rel)
    if mode not in REGULAR or os.path.islink(path):
        raise Usage("%s is tracked as %s, not a regular file; refused, a file outside git "
                    "could reach the render" % (rel, "a symlink" if mode == "120000"
                                                 or os.path.islink(path) else "mode " + mode))
    if not under(os.path.realpath(path), root):
        raise Usage("%s resolves outside the git root %s; refused" % (rel, root))
    return os.path.isfile(path)


def under(path, root):
    return os.path.commonpath([path, root]) == root


def same(a, b):
    """Whether a and b both exist and are one file, however each is spelled."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def in_git_dir(real, root):
    """Whether a part of real below root is a `.git`: its name casefolds to
    `.git`, or it exists and is its parent's `.git` (a nested repo's too)."""
    part = root
    for name in os.path.relpath(real, root).split(os.sep):
        part = os.path.join(part, name)
        if name.casefold() == ".git" or same(part, os.path.join(os.path.dirname(part), ".git")):
            return True
    return False


def claude_homes():
    """~/.claude by HOME and by the user database, each resolved."""
    homes = {os.path.expanduser("~")}
    try:
        homes.add(pwd.getpwuid(os.getuid()).pw_dir)
    except KeyError:
        pass
    return {os.path.realpath(os.path.join(h, ".claude")) for h in homes if h}


def in_claude_home(real):
    """Whether real is ~/.claude or below it: an existing part of the path is
    the same file as ~/.claude, or, as a backstop, the casefolded path is under
    the casefolded ~/.claude. No spelling of the name reaches it."""
    for home in claude_homes():
        if under(real.casefold(), home.casefold()):
            return True
        part = real
        while True:
            if same(part, home):
                return True
            parent = os.path.dirname(part)
            if parent == part:
                break
            part = parent
    return False


def out_path(root, out):
    """The output's real path and its name relative to the git root."""
    if out is None:
        path = os.path.join(root, DEFAULT_OUT)
    elif not out.strip():
        raise Usage("--out is empty")
    else:
        path = os.path.abspath(out)
    name = "the default output %s" % path if out is None else "--out %s" % out
    real = os.path.realpath(path)
    if real == root or not under(real, root):
        raise Usage("%s is outside the git root %s" % (name, root))
    # The path as given too: a `.git` that is a symlink resolves away its name.
    given = out.split(os.sep) if out is not None else []
    if in_git_dir(real, root) or any(p.casefold() == ".git" for p in given):
        raise Usage("%s is inside .git" % name)
    if in_claude_home(real):
        raise Usage("%s is under ~/.claude; nothing writes there" % name)
    if os.path.isdir(real):
        raise Usage("%s is a directory" % name)
    return real, os.path.relpath(real, root)


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


def resolve(root, sources):
    """The plugin defaults with the tracked project file over them, through
    the resolver's own layer merge (profile expansion included). Appends the
    tracked project file to sources when it is read."""
    rc = load_resolver()
    warnings = []
    layers = [rc.file_layer("plugin", DEFAULTS, PLUGIN_ROOT, warnings)]
    if not layers[0].present:
        raise Usage("plugin defaults unreadable at %s %s" % (DEFAULTS, "; ".join(warnings)))
    if tracked_file(root, PROJECT_REL):
        sources.append(PROJECT_REL)
        layer = rc.file_layer("project", os.path.join(root, PROJECT_REL), root, warnings)
        if not layer.present:
            raise Usage("%s unreadable: %s" % (PROJECT_REL, "; ".join(warnings)))
        layers.append(layer)
    elif os.path.lexists(os.path.join(root, PROJECT_REL)):
        warn("%s is not tracked by git; not read, the plugin defaults render alone" % PROJECT_REL)
    cfg, origins, applied = {}, {}, []
    for layer in layers:
        data = {k: v for k, v in layer.data.items() if k != "scopes"}
        rc.apply_layer(cfg, origins, layer, data, root, warnings, applied)
    for w in warnings:
        warn(w)
    return cfg


def parse_template(text):
    sections, cur = {}, None
    for line in text.split("\n"):
        if line.startswith("%%"):
            continue
        if line.startswith("@@ "):
            cur = " ".join(line[3:].split())
            if cur in sections:
                raise Usage("template: section %r appears twice" % cur)
            sections[cur] = []
        elif cur is not None:
            sections[cur].append(line)
        elif line.strip():
            raise Usage("template: text before the first section")
    out = {k: "\n".join(v).strip("\n") for k, v in sections.items()}
    missing = [k for k in REQUIRED if k not in out]
    if missing:
        raise Usage("template: no section %s" % ", ".join(missing))
    modes = {}
    for k, v in out.items():
        if k.startswith("mode "):
            modes[k[5:]] = fields(v, k)
            absent = [f for f in MODE_KEYS if not modes[k[5:]].get(f)]
            if absent:
                raise Usage("template: section %r lacks %s" % (k, ", ".join(absent)))
    if not modes:
        raise Usage("template: no mode section")
    return out, modes, fields(out["readers"], "readers")


def fields(text, section):
    d = {}
    for line in text.split("\n"):
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise Usage("template: section %r: %r is not `key: value`" % (section, line))
        d[key.strip()] = value.strip()
    return d


def fill(text, values):
    def sub(m):
        if m.group(1) not in values:
            raise Usage("template: unknown placeholder {{%s}}" % m.group(1))
        return values[m.group(1)]
    return PLACEHOLDER.sub(sub, text)


def join_words(items):
    return items[0] if len(items) == 1 else "%s and %s" % (", ".join(items[:-1]), items[-1])


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def wrap_unit(text, indent):
    # a code span is never broken across lines
    protected = re.sub(r"`[^`]*`", lambda m: m.group(0).replace(" ", "\x00"), text)
    lines = textwrap.wrap(protected, width=WIDTH, subsequent_indent=indent,
                          break_long_words=False, break_on_hyphens=False)
    return "\n".join(line.replace("\x00", " ") for line in lines)


def wrap(body):
    """Re-wrap each paragraph and list item at WIDTH; a heading, a comment
    and a blank line pass as they are."""
    units = []
    for line in body.split("\n"):
        if not line.strip():
            units.append(("blank", ""))
        elif line.startswith(("#", "<!--")):
            units.append(("raw", line))
        elif line.startswith("- "):
            units.append(["item", line.strip()])
        elif units and isinstance(units[-1], list):
            units[-1][1] += " " + line.strip()
        else:
            units.append(["para", line.strip()])
    out = []
    for kind, text in units:
        if kind == "item":
            out.append(wrap_unit(text, "  "))
        elif kind == "para":
            out.append(wrap_unit(text, ""))
        else:
            out.append(text)
    return "\n".join(out).strip("\n")


def render(root):
    """The file's bytes, its inputs hash, and the tracked repo files it read."""
    try:
        with open(TEMPLATE, "rb") as f:
            raw = f.read()
    except OSError as e:
        raise Usage("template unreadable: %s" % e)
    sections, modes, readers = parse_template(raw.decode("utf-8"))
    sources = []
    cfg = resolve(root, sources)
    narrative = cfg.get("narrative") if isinstance(cfg.get("narrative"), dict) else {}
    mode = narrative.get("default_mode")
    if mode not in modes:
        raise Usage("narrative.default_mode %r is not a template mode (%s)" % (mode, ", ".join(modes)))
    profile = narrative.get("profile") if isinstance(narrative.get("profile"), str) else None
    gate = cfg.get("gate") if isinstance(cfg.get("gate"), dict) else {}
    include = gate.get("include") or []
    if isinstance(include, str):
        include = [include]
    if not isinstance(include, list) or not all(isinstance(i, str) for i in include):
        raise Usage("gate.include must be a list of path patterns")
    # the digest counts only when git tracks it: an untracked or ignored one
    # is a file the repo's consumers never get
    lexicon = (index_mode(root, LEXICON_REL) is not None
               and os.path.lexists(os.path.join(root, LEXICON_REL)))
    if lexicon:
        sources.append(LEXICON_REL)

    inputs = {"mode": mode, "profile": profile, "include": include, "lexicon": lexicon}
    h = hashlib.sha256(raw)
    h.update(b"\0" + json.dumps(inputs, sort_keys=True).encode("utf-8"))
    short = h.hexdigest()[:8]

    switches = "\n".join(
        fill(sections["switch"], {"mode": name, "reader": m["reader"], "cue": m["cue"],
                                  "contract": m["contract"]})
        for name, m in modes.items() if name != mode)
    body = fill(sections["body"], {
        "files": ", and " + join_words(["`%s`" % i for i in include]) if include else "",
        "shorthand": sections["shorthand lexicon" if lexicon else "shorthand none"].strip(),
        "reader": readers.get(profile) or modes[mode]["reader"],
        "mode": mode,
        "contract": modes[mode]["contract"],
        "switches": switches,
    })
    stamp = fill(sections["stamp"], {"version": sections["version"].strip(), "inputs": short})
    text = stamp.strip() + "\n" + wrap(body) + "\n"
    return text.encode("utf-8"), short, sources


# --------------------------------------------------------------------------
# verbs
# --------------------------------------------------------------------------

def over_cap(data):
    if len(data) <= CAP:
        return False
    warn("the render is {:,} bytes, over the {:,}-byte cap; nothing written".format(len(data), CAP))
    return True


def uncommitted(root, rel):
    """Whether rel's index or work-tree copy differs from HEAD (no HEAD: it
    does). A git failure says no: this is a note, never the verdict."""
    try:
        p = git(root, "--no-optional-locks", "status", "--porcelain", "-z",
                "--untracked-files=no", "--", rel)
    except Usage:
        return False
    return p.returncode == 0 and p.stdout != ""


def write(path, rel, data, root=None, sources=()):
    if over_cap(data):
        return 2
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".include-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print("include: wrote {} ({:,} bytes, cap {:,})".format(rel, len(data), CAP))
    for src in sources:
        if uncommitted(root, src):
            warn("%s has uncommitted changes; commit it with the include, or check reports stale"
                 % src)
    return 0


def check(path, rel, data, short):
    if over_cap(data):
        return 2
    redo = "; run /respeak:include write"
    if not os.path.isfile(path):
        print("include: %s is absent%s" % (rel, redo))
        return 1
    with open(path, "rb") as f:
        have = f.read()
    if have == data:
        print("include: {} is current ({:,} bytes)".format(rel, len(have)))
        return 0
    m = STAMP_RE.match(have.split(b"\n", 1)[0].decode("utf-8", "replace"))
    if m is None:
        print("include: %s is hand-edited: it has no stamp line%s" % (rel, redo))
    elif m.group(2) != short:
        print("include: %s is stale: rendered from inputs %s, now %s%s" % (rel, m.group(2), short, redo))
    else:
        print("include: %s is hand-edited: it differs from the render of its own inputs%s" % (rel, redo))
    return 1


def os_error(what, e, rel=None):
    """One line for an OS error: what failed, on which file, and why."""
    line = "cannot %s%s: %s" % (what, " " + rel if rel else "", e.strerror or e)
    return line + (" (%s)" % e.filename if e.filename else "")


def spelled(parent, name):
    """Whether parent holds an entry spelled exactly name: on a
    case-insensitive disk `Docs` answers to `docs`, but the gate's globs
    are case-sensitive, so presence is the name os.listdir returns."""
    try:
        return name in os.listdir(parent)
    except OSError:
        return False


def glob_matches(root, pattern, match):
    """Whether pattern matches at least one regular file under its literal
    directory prefix, each part spelled as on disk (symlinks are not
    followed)."""
    head = pattern.split("*", 1)[0].rsplit("/", 1)[0]
    top = root
    for part in head.split("/"):
        if not spelled(top, part):
            return False
        top = os.path.join(top, part)
    if not os.path.isdir(top) or os.path.islink(top):
        return False
    for d, dirs, files in os.walk(top):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(d, name)
            if (not os.path.islink(full) and os.path.isfile(full)
                    and match(pattern, os.path.relpath(full, root).replace(os.sep, "/"))):
                return True
    return False


def propose(root):
    """The gate.include list of the human-lane files present at root."""
    try:
        names = set(os.listdir(root))  # as spelled on disk: readme.md is not README.md
    except OSError as e:
        raise Usage(os_error("read", e))
    match = load_resolver().match_glob  # the gate's own glob semantics
    found = [n for n in HUMAN_FILES if n in names and os.path.isfile(os.path.join(root, n))]
    found += [g for g in HUMAN_GLOBS if glob_matches(root, g, match)]
    print(json.dumps(found or FALLBACK))  # JSON is YAML: one flow list on one line
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="respeak-include.py",
                                description="Render or check the repo's static include file.")
    sub = p.add_subparsers(dest="verb", required=True, metavar="{write,check,propose}")
    for verb, text in (("write", "render the file; over the cap, write nothing"),
                       ("check", "exit 0 when the file is current, 1 when it differs")):
        s = sub.add_parser(verb, help=text)
        s.add_argument("--out", metavar="PATH",
                       help="output path inside the git root (default %s)" % DEFAULT_OUT)
    s = sub.add_parser("propose", help="print the gate.include list of the human-lane files present")
    s.add_argument("--root", metavar="R", help="the directory to look in (default: the current one)")
    args = p.parse_args(argv)
    if args.verb == "propose":
        try:
            root = os.path.realpath(args.root or os.getcwd())
            if not os.path.isdir(root):
                raise Usage("not a directory: %s" % root)
            git_root(root)
            return propose(root)
        except Usage as e:
            warn(str(e))
            return 2
    try:
        root = git_root(os.getcwd())
        path, rel = out_path(root, args.out)
        data, short, sources = render(root)
    except Usage as e:
        warn(str(e))
        return 2
    except OSError as e:
        warn(os_error("run", e))
        return 2
    try:
        if args.verb == "write":
            return write(path, rel, data, root, sources)
        return check(path, rel, data, short)
    except OSError as e:
        # the task could not run: exit 2, never check's 1, which means drift
        warn(os_error("write" if args.verb == "write" else "read", e, rel))
        return 2


if __name__ == "__main__":
    sys.exit(main())
