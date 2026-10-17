"""Tests for plugin/scripts/respeak-lexicon.py: the lexicon's static rules, its
use record, the ratification verdict, and its clocks; and the writer's
wiring, the translator's `uses:` line and the skill's step 6 that records it;
and the seams, the record's union merge and `--root`'s default, the git top.

The script reads R/.claude/respeak/lexicon.yaml, else the plugin's seed, and
`shorthand` from the plugin defaults with R/.claude/respeak/config.yaml over
them, when git tracks it; no user, folder or local layer. `use` appends to
R/.claude/respeak/uses.jsonl. Each case builds a project, a git work tree,
under a temp HOME (CLAUDE_CONFIG_DIR inside it) and runs the script with
--root.
Exits: check 0 ok, 1 a problem; use 0; ratify and due 0 whatever the
verdicts; each 2 on a bad value, a bad lexicon or a refusal.
"""
import contextlib
import datetime
import fnmatch
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")
SCRIPT = os.path.join(PLUGIN, "scripts", "respeak-lexicon.py")
PY_WRAPPER = os.path.join(PLUGIN, "scripts", "py")
SHIPPED = os.path.join(PLUGIN, "config", "respeak.config.yaml")
SEED_LINE = "lexicon: ok, 2 ratified of 150, the nearest two 6 apart (min 2)\n"
USES_REL = os.path.join(".claude", "respeak", "uses.jsonl")
LEXICON_REL = os.path.join(".claude", "respeak", "lexicon.yaml")

_spec = importlib.util.spec_from_file_location("respeak_lexicon", SCRIPT)
assert _spec is not None and _spec.loader is not None
lex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lex)


def entry(term, status="ratified", legibility=0.9):
    return ('  - term: "%s"\n    expansion: "x"\n    definition: "x"\n    scope: repo\n'
            "    status: %s\n    uses: 0\n    legibility: %s\n" % (term, status, legibility))


class Project:
    """A git work tree under a temp HOME, with a .claude/respeak/ directory;
    config() writes the project file and stages it."""

    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="respeak-lexicon-"))
        self.home = os.path.join(self.root, "home")
        self.cfgdir = os.path.join(self.home, ".claude")
        self.dir = os.path.join(self.home, "code", "proj")
        self.respeak = os.path.join(self.dir, ".claude", "respeak")
        os.makedirs(self.respeak)
        os.makedirs(os.path.join(self.cfgdir, "respeak"))
        self.env = dict(os.environ)
        self.env.update({"HOME": self.home, "CLAUDE_CONFIG_DIR": self.cfgdir,
                         "RESPEAK_PYTHON": sys.executable, "GIT_CONFIG_NOSYSTEM": "1"})
        for k in ("RESPEAK_CONFIG", "RESPEAK_TODAY", "CLAUDE_PLUGIN_ROOT", "GIT_DIR",
                  "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            self.env.pop(k, None)
        self.git("init", "-q")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.dir, env=self.env, check=True,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, timeout=60)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(textwrap.dedent(text))
        return path

    def config(self, text, track=True):
        path = self.write(".claude/respeak/config.yaml", text)
        if track:
            self.git("add", "-f", ".claude/respeak/config.yaml")
        return path

    def lexicon(self, *entries):
        return self.write(".claude/respeak/lexicon.yaml", "version: 1\nentries:\n" + "".join(entries))

    def record(self, term, outcome="clean", readback=True, n=1, date="2026-10-16"):
        path = os.path.join(self.dir, USES_REL)
        with open(path, "a") as f:
            for _ in range(n):
                f.write(json.dumps({"term": term, "date": date, "outcome": outcome,
                                    "readback": readback}) + "\n")

    def tree(self):
        found = {}
        for d, _, files in os.walk(self.root):
            for name in files:
                with open(os.path.join(d, name), "rb") as f:
                    found[os.path.join(d, name)] = f.read()
        return found

    def uses(self):
        with open(os.path.join(self.dir, USES_REL), "rb") as f:
            return f.read()

    def run(self, *args, wrapper=False, env=None):
        argv = [PY_WRAPPER, "respeak-lexicon.py"] if wrapper else [sys.executable, SCRIPT]
        return subprocess.run(argv + list(args) + ["--root", self.dir], cwd=self.root,
                              env=env or self.env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=60)


class Case(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)

    def assertRan(self, r, code, stdout=None):
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        if stdout is not None:
            self.assertEqual(r.stdout, stdout)


class LexiconCheck(Case):
    def test_the_seed(self):
        # no lexicon.yaml in the project: the seed, the shipped keys
        self.assertRan(self.p.run("check"), 0, SEED_LINE)
        self.assertRan(self.p.run("check", wrapper=True), 0, SEED_LINE)

    def test_a_project_cap_and_distance(self):
        self.p.config("shorthand: {max_entries: 2}\n")
        self.assertRan(self.p.run("check"), 0,
                       "lexicon: ok, 2 ratified of 2, the nearest two 6 apart (min 2)\n")
        self.p.config("shorthand: {max_entries: 1}\n")
        self.assertRan(self.p.run("check"), 1,
                       "over the cap: 2 ratified, max_entries 1\n"
                       "lexicon: 1 problem, 2 ratified of 1, the nearest two 6 apart (min 2)\n")
        self.p.config("shorthand: {min_token_edit_distance: 7}\n")
        self.assertRan(self.p.run("check"), 1,
                       "too near: cfg and R1..R7, 6 apart (min 7)\n"
                       "lexicon: 1 problem, 2 ratified of 150, the nearest two 6 apart (min 7)\n")

    def test_two_terms_one_apart(self):
        self.p.lexicon(entry("IU"), entry("IV"), entry("cfg"))
        self.assertRan(self.p.run("check"), 1,
                       "too near: IU and IV, 1 apart (min 2)\n"
                       "lexicon: 1 problem, 3 ratified of 150, the nearest two 1 apart (min 2)\n")

    def test_the_distance_is_case_folded(self):
        self.p.lexicon(entry("cfg"), entry("CFG"), entry("IU"))
        self.p.config("shorthand: {max_entries: 2}\n")
        self.assertRan(self.p.run("check"), 1,
                       "over the cap: 3 ratified, max_entries 2\n"
                       "too near: cfg and CFG, 0 apart (min 2)\n"
                       "lexicon: 2 problems, 3 ratified of 2, the nearest two 0 apart (min 2)\n")

    def test_retired_and_proposed_entries_count_for_nothing(self):
        self.p.lexicon(entry("cfg"), entry("CFG", "retired"), entry("cfh", "proposed"),
                       entry("IU"), entry("IV", "retired"))
        self.p.config("shorthand: {max_entries: 2}\n")
        self.assertRan(self.p.run("check"), 0,
                       "lexicon: ok, 2 ratified of 2, the nearest two 3 apart (min 2)\n")
        self.p.lexicon(entry("cfg"), entry("cfh", "retired"))
        self.assertRan(self.p.run("check"), 0,
                       "lexicon: ok, 1 ratified of 2, no two to compare (min 2)\n")

    def test_a_user_file_moves_nothing(self):
        # shorthand is project-only: the user layer, the local file, a folder
        # file and RESPEAK_CONFIG are never read
        keys = "shorthand: {max_entries: 1, min_token_edit_distance: 9}\n"
        with open(os.path.join(self.p.cfgdir, "respeak", "config.yaml"), "w") as f:
            f.write(keys)
        self.p.write(".claude/respeak/config.local.yaml", keys)
        self.p.write(".respeak.yaml", keys)
        env = dict(self.p.env, RESPEAK_CONFIG=self.p.write("env.yaml", keys))
        self.assertRan(self.p.run("check", env=env), 0, SEED_LINE)

    def test_a_bad_value_exits_2(self):
        for text, key in (("shorthand: {max_entries: x}\n", "shorthand.max_entries"),
                          ("shorthand: {min_token_edit_distance: true}\n",
                           "shorthand.min_token_edit_distance"),
                          ("shorthand: {max_entries: 0}\n", "shorthand.max_entries")):
            with self.subTest(text=text):
                self.p.config(text)
                r = self.p.run("check")
                self.assertRan(r, 2, "")
                self.assertIn(key, r.stderr)

    def test_no_pyyaml_exits_2_with_one_line(self):
        # a yaml module that cannot import, ahead of site-packages
        stub = os.path.join(self.p.root, "stub")
        os.makedirs(stub)
        with open(os.path.join(stub, "yaml.py"), "w") as f:
            f.write("raise ImportError('no yaml here')\n")
        r = self.p.run("check", env=dict(self.p.env, PYTHONPATH=stub))
        self.assertRan(r, 2, "")
        self.assertEqual(r.stderr.splitlines(), [
            "respeak-lexicon: PyYAML is required (python3 -m pip install pyyaml); "
            "scripts/py picks an interpreter that has it"])

    def test_each_key_the_script_reads_is_tagged_with_it(self):
        with open(SHIPPED) as f:
            lines = f.read().split("\n")
        start = lines.index("shorthand: # project-only: governance never varies by folder or by user")
        for key in ("max_entries", "min_token_edit_distance", "auto", "legibility_floor",
                    "ratification"):
            with self.subTest(key=key):
                i = next(n for n in range(start, len(lines)) if lines[n].startswith("  %s:" % key))
                block = [lines[i]]
                for line in lines[i + 1:]:
                    if not line.lstrip().startswith("#") or line.startswith("  #"):
                        break
                    block.append(line)
                self.assertIn("[respeak-lexicon.py", "\n".join(block))
                self.assertNotIn("no script checks it", "\n".join(block))

    def test_a_config_git_does_not_track_is_not_read(self):
        # as respeak-include.py's resolve: untracked or ignored, named and not read
        note = ("respeak-lexicon: .claude/respeak/config.yaml is not tracked by git; not read, "
                "the plugin defaults apply alone\n")
        self.p.write(".gitignore", ".claude/respeak/config.yaml\n")
        self.p.config("shorthand: {max_entries: 1}\n", track=False)
        for env in (self.p.env, dict(self.p.env, GIT_DIR=os.path.join(self.p.root, "none"))):
            r = self.p.run("check", env=env)
            self.assertRan(r, 0, SEED_LINE)
            self.assertEqual(r.stderr, note)
        # tracked, it is read
        self.p.git("add", "-f", ".claude/respeak/config.yaml")
        self.assertRan(self.p.run("check"), 1)

    def test_a_tracked_symlink_or_a_path_outside_is_refused(self):
        outside = os.path.join(self.p.root, "outside")
        os.makedirs(outside)
        with open(os.path.join(outside, "config.yaml"), "w") as f:
            f.write("shorthand: {max_entries: 1}\n")
        link = os.path.join(self.p.respeak, "config.yaml")
        os.symlink(os.path.join(outside, "config.yaml"), link)
        # untracked, the symlink is not read
        r = self.p.run("check")
        self.assertRan(r, 0, SEED_LINE)
        self.assertIn("not tracked by git; not read", r.stderr)
        # tracked as a symlink: refused
        self.p.git("add", ".claude/respeak/config.yaml")
        r = self.p.run("check")
        self.assertRan(r, 2, "")
        self.assertIn("tracked as a symlink, not a regular file; refused", r.stderr)
        # tracked as a regular file whose path now resolves outside the root: refused
        self.p.git("rm", "-q", "--cached", ".claude/respeak/config.yaml")
        os.remove(link)
        self.p.config("shorthand: {max_entries: 1}\n")
        moved = os.path.join(outside, "dot-claude")
        os.rename(os.path.join(self.p.dir, ".claude"), moved)
        os.symlink(moved, os.path.join(self.p.dir, ".claude"))
        r = self.p.run("check")
        self.assertRan(r, 2, "")
        self.assertIn("resolves outside the git root", r.stderr)

    def test_a_bad_lexicon_exits_2(self):
        for text, why in (("entries: {}\n", "no `entries:` list"),
                          ("entries:\n  - term: cfg\n    status: done\n", "status must be"),
                          ("entries:\n  - status: ratified\n", "term must be"),
                          ("entries:\n  - {term: cfg, status: proposed, legibility: 2}\n",
                           "legibility must be"),
                          ("entries: [\n", "unreadable")):
            with self.subTest(text=text):
                self.p.write(".claude/respeak/lexicon.yaml", text)
                r = self.p.run("check")
                self.assertRan(r, 2, "")
                self.assertIn(why, r.stderr)
        r = subprocess.run([sys.executable, SCRIPT, "check", "--root", os.path.join(self.p.root, "no")],
                           env=self.p.env, capture_output=True, text=True, timeout=60)
        self.assertRan(r, 2, "")

    def test_a_term_with_a_shell_character_is_refused(self):
        # r17 fix round 1, F3: the skill's step 6 puts a term on a command line
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")
        for term in ("$HOME", "a`b", "x;y", "a|b", "a&b", "a<b", "a>b", 'a\\"b', "it's", "a\\\\b",
                     "x y", "a\\tb", "a\\nb"):
            self.p.write(".claude/respeak/lexicon.yaml",
                         'entries:\n  - {term: "cfg", status: ratified}\n'
                         '  - {term: "%s", status: proposed}\n' % term)
            for argv in (["check"], ["ratify"], ["due"], ["use", "cfg", "--outcome", "clean"]):
                with self.subTest(term=term, verb=argv[0]):
                    r = self.p.run(*argv, env=env)
                    self.assertRan(r, 2, "")
                    self.assertIn("entries[1]", r.stderr)
                    self.assertIn("a term holds a shell character", r.stderr)
                    self.assertEqual(len(r.stderr.splitlines()), 1)
        self.assertFalse(os.path.lexists(os.path.join(self.p.dir, USES_REL)))
        # the seed's terms, and the shapes the tests use, stay valid
        self.p.lexicon(entry("cfg"), entry("R1..R7"), entry("2-lane", "proposed"), entry("IU"))
        self.assertRan(self.p.run("check"), 0)

    def test_no_verb_writes_bytecode(self):
        # r17 fix round 1, F4: the modules the script loads leave no __pycache__
        copy = os.path.join(self.p.root, "plugin")
        shutil.copytree(PLUGIN, copy, ignore=shutil.ignore_patterns("__pycache__"))
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")
        for k in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX"):
            env.pop(k, None)
        script = os.path.join(copy, "scripts", "respeak-lexicon.py")
        for argv in (["check"], ["ratify"], ["due"], ["use", "cfg", "--outcome", "clean"]):
            with self.subTest(verb=argv[0]):
                r = subprocess.run([sys.executable, script, *argv, "--root", self.p.dir], env=env,
                                   capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)
                self.assertRan(r, 0)
                caches = [d for d, _, _ in os.walk(copy) if os.path.basename(d) == "__pycache__"]
                self.assertEqual(caches, [])



def utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


class UseRecord(Case):
    def setUp(self):
        super().setUp()
        self.env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")

    def test_the_line(self):
        r = self.p.run("use", "2-lane", "--outcome", "clean", "--readback", "--source", "night 4",
                       env=self.env)
        self.assertRan(r, 0, "use: 2-lane clean with readback on 2026-10-16, recorded in %s\n"
                       % USES_REL)
        first = (b'{"term": "2-lane", "date": "2026-10-16", "outcome": "clean", '
                 b'"readback": true, "source": "night 4"}\n')
        self.assertEqual(self.p.uses(), first)
        # appended, never rewritten; no source, no key; readback false without the flag
        r = self.p.run("use", "cfg", "--outcome", "failure", env=self.env, wrapper=True)
        self.assertRan(r, 0)
        self.assertEqual(self.p.uses(), first + b'{"term": "cfg", "date": "2026-10-16", '
                         b'"outcome": "failure", "readback": false}\n')
        self.assertEqual([u["term"] for u in lex.uses(self.p.dir)], ["2-lane", "cfg"])

    def test_refusals(self):
        self.p.lexicon(entry("cfg"), entry("old", "retired"), entry("again", "retired"),
                       entry("again", "proposed"))
        for args, env, why in (
                (["nope"], self.env, "not a lexicon term"),
                (["old"], self.env, "retired"),
                (["cfg"], dict(self.env, RESPEAK_TODAY="2026-13-01"), "RESPEAK_TODAY"),
                (["cfg"], dict(self.env, RESPEAK_TODAY="20261016"), "RESPEAK_TODAY"),
                (["cfg"], dict(self.env, RESPEAK_TODAY="today"), "RESPEAK_TODAY"),
                (["cfg", "--outcome", "fine"], self.env, "invalid choice")):
            with self.subTest(args=args, env=env.get("RESPEAK_TODAY")):
                argv = ["use"] + args + ([] if "--outcome" in args else ["--outcome", "clean"])
                r = self.p.run(*argv, env=env)
                self.assertRan(r, 2, "")
                self.assertIn(why, r.stderr)
                self.assertFalse(os.path.lexists(os.path.join(self.p.dir, USES_REL)))
        # a term retired once and proposed again is a term
        self.assertRan(self.p.run("use", "again", "--outcome", "clean", env=self.env), 0)
        # no .claude/respeak/: nothing to commit the record beside
        shutil.rmtree(os.path.join(self.p.dir, ".claude"))
        r = self.p.run("use", "cfg", "--outcome", "clean", env=self.env)
        self.assertRan(r, 2, "")
        self.assertIn("no .claude/respeak/", r.stderr)
        self.assertFalse(os.path.lexists(os.path.join(self.p.dir, ".claude")))

    def test_a_symlinked_record_is_refused(self):
        target = self.p.write("elsewhere.jsonl", "")
        os.symlink(target, os.path.join(self.p.dir, USES_REL))
        r = self.p.run("use", "cfg", "--outcome", "clean", env=self.env)
        self.assertRan(r, 2, "")
        self.assertIn("cannot append", r.stderr)
        with open(target) as f:
            self.assertEqual(f.read(), "")

    def test_the_clock(self):
        for env in (self.p.env, dict(self.p.env, RESPEAK_TODAY="")):
            before = utc_today()
            self.assertRan(self.p.run("use", "cfg", "--outcome", "clean", env=env), 0)
            after = utc_today()
            self.assertIn(lex.uses(self.p.dir)[-1]["date"], (before, after))
        self.assertRan(self.p.run("use", "cfg", "--outcome", "clean",
                                  env=dict(self.p.env, RESPEAK_TODAY="2024-02-29")), 0)
        self.assertEqual(lex.uses(self.p.dir)[-1]["date"], "2024-02-29")

    def test_a_skip(self):
        good = {"term": "cfg", "date": "2026-10-16", "outcome": "clean", "readback": True}
        lines = [json.dumps(good), "not json", "[1, 2]",
                 json.dumps(dict(good, outcome="fine")), "",
                 json.dumps(dict(good, date="2026-10-32")),
                 json.dumps(dict(good, readback="yes")),
                 json.dumps(dict(good, term="2-lane", source="s"))]
        self.p.write(USES_REL, "\n".join(lines) + "\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            records = lex.uses(self.p.dir)
        self.assertEqual(records, [good, dict(good, term="2-lane", source="s")])
        named = [l.split(": ", 2)[1] for l in err.getvalue().splitlines()]
        self.assertEqual(named, ["%s:%d" % (USES_REL, n) for n in (2, 3, 4, 5, 6, 7)])
        self.assertIn("skipped", err.getvalue())
        # a last line cut short: the next use starts its own line
        self.p.write(USES_REL, json.dumps(good) + "\n" + '{"term": "cf')
        self.assertRan(self.p.run("use", "cfg", "--outcome", "clean", "--readback", env=self.env), 0)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(lex.uses(self.p.dir), [good, good])

    def test_concurrent_appends_stay_whole(self):
        # the fork's test (packet r16, section 6): one O_APPEND write a use,
        # so no two lines interleave
        procs = [subprocess.Popen([sys.executable, SCRIPT, "use", "cfg", "--outcome", "clean",
                                   "--source", "writer %02d" % i, "--root", self.p.dir],
                                  env=self.env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                 for i in range(16)]
        for proc in procs:
            _, err = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, err)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            records = lex.uses(self.p.dir)
        self.assertEqual(err.getvalue(), "")
        self.assertEqual(sorted(r["source"] for r in records),
                         ["writer %02d" % i for i in range(16)])



SEED_RATIFY = ("2-lane: not eligible: 0 of 5 clean uses with readback\n"
               "ratify: 1 proposed, 0 eligible; shorthand.ratification: human\n")


class RatifyGate(Case):
    def setUp(self):
        super().setUp()
        # the seed's shape: cfg and R1..R7 ratified, 2-lane proposed at 0.6
        self.p.lexicon(entry("cfg"), entry("R1..R7", legibility=0.5),
                       entry("2-lane", "proposed", 0.6))

    def verdict(self, line, tail="ratify: 1 proposed, %d eligible; shorthand.ratification: human\n"):
        r = self.p.run("ratify")
        self.assertRan(r, 0, line + "\n" + tail % (line.endswith(": eligible")))
        return r

    def test_the_seed(self):
        os.remove(os.path.join(self.p.respeak, "lexicon.yaml"))
        before = self.p.tree()
        self.assertRan(self.p.run("ratify"), 0, SEED_RATIFY)
        self.assertRan(self.p.run("ratify", wrapper=True), 0, SEED_RATIFY)
        self.assertEqual(self.p.tree(), before, "ratify writes nothing")

    def test_eligible(self):
        self.p.record("2-lane", n=5)
        before = self.p.tree()
        self.verdict("2-lane: eligible")
        self.assertEqual(self.p.tree(), before, "ratify writes nothing: a person ratifies")

    def test_too_few_clean_uses(self):
        self.p.record("2-lane", n=3)
        self.p.record("cfg", n=5)       # another term's uses count for nothing
        self.p.record("2-LANE", n=5)    # nor a spelling the lexicon does not hold
        self.verdict("2-lane: not eligible: 3 of 5 clean uses with readback")

    def test_readback_on_and_off(self):
        self.p.record("2-lane", n=3)
        self.p.record("2-lane", readback=False, n=2)
        self.verdict("2-lane: not eligible: 3 of 5 clean uses with readback")
        self.p.config("shorthand: {auto: {readback_evidence: false}}\n")
        self.verdict("2-lane: eligible")
        self.p.config("shorthand: {auto: {readback_evidence: false, uses: 6}}\n")
        self.verdict("2-lane: not eligible: 5 of 6 clean uses")

    def test_fidelity_failures(self):
        self.p.record("2-lane", n=5)
        self.p.record("2-lane", "failure", readback=False)
        self.verdict("2-lane: not eligible: 1 fidelity failure, 0 allowed")
        self.p.config("shorthand: {auto: {fidelity_failures_allowed: 1}}\n")
        self.verdict("2-lane: eligible")
        self.p.record("2-lane", "failure")
        self.verdict("2-lane: not eligible: 2 fidelity failures, 1 allowed")

    def test_too_near_a_ratified_term(self):
        self.p.lexicon(entry("cfg"), entry("R1..R7"), entry("CFH", "proposed", 0.6))
        self.p.record("CFH", n=5)
        self.verdict("CFH: not eligible: 1 apart from cfg, min 2")
        self.p.config("shorthand: {min_token_edit_distance: 1}\n")
        self.verdict("CFH: eligible")

    def test_the_cap(self):
        self.p.record("2-lane", n=5)
        self.p.config("shorthand: {max_entries: 2}\n")
        self.verdict("2-lane: not eligible: the cap, 2 ratified")
        self.p.config("shorthand: {max_entries: 3}\n")
        self.verdict("2-lane: eligible")

    def test_the_legibility_floor(self):
        self.p.lexicon(entry("cfg"), entry("2L", "proposed", 0.4))
        self.p.record("2L", n=5)
        self.verdict("2L: not eligible: legibility 0.4, floor 0.5")
        self.p.config("shorthand: {legibility_floor: 0.4}\n")
        self.verdict("2L: eligible")
        self.p.write(".claude/respeak/lexicon.yaml",
                     "entries:\n  - {term: 2L, status: proposed}\n")
        self.verdict("2L: not eligible: legibility none, floor 0.4")

    def test_each_entry_in_file_order_every_reason_in_order(self):
        self.p.lexicon(entry("cfg"), entry("CFH", "proposed", 0.3), entry("IU", "retired"),
                       entry("2-lane", "proposed", 0.6), entry("R1..R7"))
        self.p.record("CFH", "failure")
        self.p.record("CFH", readback=False, n=5)
        self.p.record("2-lane", n=5)
        self.p.config("shorthand: {max_entries: 2, ratification: auto}\n")
        r = self.p.run("ratify")
        self.assertRan(r, 0, "CFH: not eligible: 0 of 5 clean uses with readback; "
                       "1 fidelity failure, 0 allowed; 1 apart from cfg, min 2; "
                       "the cap, 2 ratified; legibility 0.3, floor 0.5\n"
                       "2-lane: not eligible: the cap, 2 ratified\n"
                       "ratify: 2 proposed, 0 eligible; shorthand.ratification: auto\n")

    def test_a_skipped_line_is_named_and_the_verdict_stands(self):
        self.p.record("2-lane", n=5)
        with open(os.path.join(self.p.dir, USES_REL), "a") as f:
            f.write("{oops\n")
        r = self.verdict("2-lane: eligible")
        self.assertIn("%s:6: not JSON; skipped" % USES_REL, r.stderr)

    def test_a_bad_value_exits_2(self):
        for text, key in (("shorthand: {auto: {uses: x}}\n", "shorthand.auto.uses"),
                          ("shorthand: {auto: {fidelity_failures_allowed: -1}}\n",
                           "shorthand.auto.fidelity_failures_allowed"),
                          ("shorthand: {auto: {readback_evidence: 1}}\n",
                           "shorthand.auto.readback_evidence"),
                          ("shorthand: {legibility_floor: 2}\n", "shorthand.legibility_floor"),
                          ("shorthand: {ratification: robot}\n", "shorthand.ratification")):
            for verb in ("ratify", "check"):
                with self.subTest(text=text, verb=verb):
                    self.p.config(text)
                    r = self.p.run(verb)
                    self.assertRan(r, 2, "")
                    self.assertIn(key, r.stderr)
        # a mapping replaced by a scalar is the resolver's merge rule: ignored, with its warning
        self.p.config("shorthand: {auto: 5}\n")
        r = self.p.run("ratify")
        self.assertRan(r, 0, SEED_RATIFY)
        self.assertIn("shorthand.auto is a mapping in a lower layer", r.stderr)


def dated(term, ratified_by="human 2026-10-01", status="ratified", reviewed=None):
    return ('  - term: "%s"\n    status: %s\n    legibility: 0.9\n' % (term, status)
            + ("    ratified_by: %s\n" % ratified_by if ratified_by is not None else "")
            + ("    reviewed: %s\n" % reviewed if reviewed is not None else ""))


SEED_DUE = ("audit: due, never audited, every 30 days; fresh-decoder, sample: cfg, R1..R7\n"
            "due: 0 to retire, 0 to review, the audit due\n")
QUIET = ("audit: not due until 2099-01-31\n"
         "due: 0 to retire, 0 to review, the audit not due until 2099-01-31\n")


class DueClocks(Case):
    """`due`: the retire, review and audit clocks over the ratified entries."""

    def due(self, day, *args, code=0, stdout=None):
        r = self.p.run("due", *args, env=dict(self.p.env, RESPEAK_TODAY=day))
        self.assertRan(r, code, stdout)
        return r

    def lexicon(self, *entries, audited="2099-01-01"):
        # an audit far ahead keeps the audit line out of the clocks under test
        head = "version: 1\n" + ("audited: %s\n" % audited if audited else "")
        self.p.write(".claude/respeak/lexicon.yaml", head + "entries:\n" + "".join(entries))

    def test_the_seed(self):
        before = self.p.tree()
        self.due("2026-10-16", stdout=SEED_DUE)
        r = self.p.run("due", wrapper=True, env=dict(self.p.env, RESPEAK_TODAY="2026-10-16"))
        self.assertRan(r, 0, SEED_DUE)
        self.due("2027-03-01", stdout=(
            "retire: cfg: unused since 2026-08-31 (ratified), 182 days, after 180 days\n"
            "review: cfg: unreviewed since 2026-08-31 (ratified), 182 days, every 90 days\n"
            "retire: R1..R7: unused since 2026-08-31 (ratified), 182 days, after 180 days\n"
            "review: R1..R7: unreviewed since 2026-08-31 (ratified), 182 days, every 90 days\n"
            "audit: due, never audited, every 30 days; fresh-decoder, sample: cfg, R1..R7\n"
            "due: 2 to retire, 2 to review, the audit due\n"))
        self.assertEqual(self.p.tree(), before, "due writes nothing")

    def test_the_keys_are_tagged_due(self):
        with open(SHIPPED) as f:
            lines = f.read().split("\n")
        for key, value in (("retire_after_days_unused", " 180"), ("review_cadence_days", " 90"),
                           ("legibility_audit", "")):
            with self.subTest(key=key):
                line = next(l for l in lines if l.startswith("  %s:" % key))
                self.assertTrue(line.startswith("  %s:%s # [respeak-lexicon.py due]" % (key, value)))
        sh = lex.shorthand(self.p.dir)
        self.assertEqual(sh["legibility_audit"],
                         {"cadence_days": 30, "method": "fresh-decoder", "sample": 10})

    def test_retire_at_n_minus_1_and_n(self):
        self.lexicon(dated("cfg"), dated("IU"))
        self.p.config("shorthand: {retire_after_days_unused: 10, review_cadence_days: 900}\n")
        # cfg: the newest clean use counts; a failure, or an older clean use, does not
        self.p.record("cfg", date="2026-10-02")
        self.p.record("cfg", readback=False, date="2026-10-06")
        self.p.record("cfg", "failure", date="2026-10-12")
        self.p.record("IV", date="2026-10-14")   # another term's use moves nothing
        self.due("2026-10-10", stdout=QUIET)
        self.due("2026-10-11", stdout=(
            "retire: IU: unused since 2026-10-01 (ratified), 10 days, after 10 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 1 to retire, 0 to review, the audit not due until 2099-01-31\n"))
        self.due("2026-10-16", stdout=(
            "retire: cfg: unused since 2026-10-06 (clean use), 10 days, after 10 days\n"
            "retire: IU: unused since 2026-10-01 (ratified), 15 days, after 10 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 2 to retire, 0 to review, the audit not due until 2099-01-31\n"))

    def test_review_at_n_minus_1_and_n(self):
        self.lexicon(dated("cfg", reviewed="2026-10-05"), dated("IU", reviewed='"2026-10-03"'),
                     dated("R1..R7"))
        self.p.config("shorthand: {retire_after_days_unused: 900, review_cadence_days: 5}\n")
        self.due("2026-10-05", stdout=QUIET)
        self.due("2026-10-06", stdout=(
            "review: R1..R7: unreviewed since 2026-10-01 (ratified), 5 days, every 5 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 0 to retire, 1 to review, the audit not due until 2099-01-31\n"))
        self.due("2026-10-10", stdout=(
            "review: cfg: unreviewed since 2026-10-05 (reviewed), 5 days, every 5 days\n"
            "review: IU: unreviewed since 2026-10-03 (reviewed), 7 days, every 5 days\n"
            "review: R1..R7: unreviewed since 2026-10-01 (ratified), 9 days, every 5 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 0 to retire, 3 to review, the audit not due until 2099-01-31\n"))

    def test_both_clocks_in_file_order_and_no_date(self):
        self.lexicon(dated("old", status="retired"), dated("cfg"), dated("new", status="proposed"),
                     dated("IU", ratified_by=None), dated("R1..R7", ratified_by="human"),
                     dated("IV", ratified_by="2026-10-01"))
        self.p.config("shorthand: {retire_after_days_unused: 3, review_cadence_days: 3}\n")
        self.due("2026-10-04", stdout=(
            "retire: cfg: unused since 2026-10-01 (ratified), 3 days, after 3 days\n"
            "review: cfg: unreviewed since 2026-10-01 (ratified), 3 days, every 3 days\n"
            "retire: IU: no date\n"
            "review: IU: no date\n"
            "retire: R1..R7: no date\n"
            "review: R1..R7: no date\n"
            "retire: IV: unused since 2026-10-01 (ratified), 3 days, after 3 days\n"
            "review: IV: unreviewed since 2026-10-01 (ratified), 3 days, every 3 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 4 to retire, 4 to review, the audit not due until 2099-01-31\n"))
        # a clean use, or a review, gives a term with no ratified date its clock
        self.lexicon(dated("IU", ratified_by=None, reviewed="2026-10-03"))
        self.p.record("IU", date="2026-10-02")
        self.due("2026-10-04", stdout=QUIET)

    def test_the_audit(self):
        self.lexicon(dated("cfg"), audited="2026-10-01")
        self.p.config("shorthand: {legibility_audit: {cadence_days: 30}}\n")
        self.due("2026-10-30", stdout=("audit: not due until 2026-10-31\n"
                                       "due: 0 to retire, 0 to review, the audit not due until 2026-10-31\n"))
        self.due("2026-10-31", stdout=(
            "audit: due, audited 2026-10-01, 30 days, every 30 days; fresh-decoder, sample: cfg\n"
            "due: 0 to retire, 0 to review, the audit due\n"))
        self.lexicon(dated("cfg"), audited='"2026-10-01"')
        self.due("2026-10-30", stdout=("audit: not due until 2026-10-31\n"
                                       "due: 0 to retire, 0 to review, the audit not due until 2026-10-31\n"))
        self.lexicon(dated("cfg", status="proposed"), audited=None)
        self.due("2026-10-30", stdout=("audit: due, never audited, every 30 days; fresh-decoder, sample: none\n"
                                       "due: 0 to retire, 0 to review, the audit due\n"))

    def test_the_sample(self):
        terms = ["t%02d" % i for i in range(12)]
        self.lexicon(dated("p", status="proposed"), *[dated(t) for t in terms], audited=None)

        def sampled(day):
            line = self.due(day).stdout.splitlines()[-2]
            return line.split("sample: ")[1].split(", ")

        def expected(day, n):
            rank = sorted(terms, key=lambda t: hashlib.sha256(("%s %s" % (day, t)).encode()).hexdigest())
            return [t for t in terms if t in rank[:n]]

        for day in ("2026-10-02", "2026-10-03"):
            with self.subTest(day=day):
                got = sampled(day)
                self.assertEqual(len(got), 10)
                self.assertEqual(got, expected(day, 10))
                self.assertEqual(got, sorted(got), "printed in file order")
        self.assertNotEqual(sampled("2026-10-02"), sampled("2026-10-03"), "the day moves it")
        self.p.config("shorthand: {legibility_audit: {sample: 3}}\n")
        self.assertEqual(sampled("2026-10-02"), expected("2026-10-02", 3))
        self.p.config("shorthand: {legibility_audit: {sample: 20}}\n")
        self.assertEqual(sampled("2026-10-02"), terms)

    def test_bad_values_exit_2(self):
        for text, key in (
                ("shorthand: {retire_after_days_unused: 0}\n", "shorthand.retire_after_days_unused"),
                ("shorthand: {review_cadence_days: x}\n", "shorthand.review_cadence_days"),
                ("shorthand: {review_cadence_days: true}\n", "shorthand.review_cadence_days"),
                ("shorthand: {legibility_audit: {cadence_days: 1.5}}\n",
                 "shorthand.legibility_audit.cadence_days"),
                ("shorthand: {legibility_audit: {sample: 0}}\n", "shorthand.legibility_audit.sample"),
                ("shorthand: {legibility_audit: {method: guess}}\n",
                 "shorthand.legibility_audit.method must be fresh-decoder")):
            with self.subTest(text=text):
                self.p.config(text)
                r = self.due("2026-10-16", code=2, stdout="")
                self.assertIn(key, r.stderr)
                self.assertEqual(len(r.stderr.splitlines()), 1)
                # checked by due alone
                self.assertRan(self.p.run("check"), 0, SEED_LINE)
        os.remove(os.path.join(self.p.respeak, "config.yaml"))
        for head, entries, why in (
                ("", dated("cfg", reviewed="soon"), "entries[0] (cfg): reviewed must be a YYYY-MM-DD date"),
                ("", dated("cfg", reviewed="2026-10-01T10:00:00"), "reviewed must be"),
                # an entry due ahead of the bad value: nothing printed before the refusal
                ("audited: 2026/10/01\n", dated("cfg", ratified_by="human 2020-01-01"),
                 "audited must be a YYYY-MM-DD date"),
                ("", dated("cfg", ratified_by="human 2020-01-01") + dated("IU", reviewed="soon"),
                 "entries[1] (IU): reviewed must be"),
                ("", dated("cfg", reviewed="2026-13-01"), "unreadable: month must be in 1..12")):
            with self.subTest(entries=entries, head=head):
                self.p.write(".claude/respeak/lexicon.yaml", head + "entries:\n" + entries)
                r = self.due("2026-10-16", code=2, stdout="")
                self.assertIn(why, r.stderr)
        self.lexicon(dated("cfg"))
        r = self.due("2026-10-32", code=2, stdout="")
        self.assertIn("RESPEAK_TODAY", r.stderr)

    def test_a_date_past_9999_exits_2(self):
        # r17 fix round 1, F1: the next audit date past date.max is a refusal, not a traceback
        for audited, cadence in (("9999-12-31", 30), ("2026-10-01", 3000000),
                                 ("2026-10-01", 999999999)):
            with self.subTest(audited=audited, cadence=cadence):
                self.lexicon(dated("cfg"), audited=audited)
                self.p.config("shorthand: {legibility_audit: {cadence_days: %d}}\n" % cadence)
                r = self.due("2026-10-16", code=2, stdout="")
                self.assertEqual(r.stderr.splitlines(), [
                    "respeak-lexicon: %s: audited %s plus shorthand.legibility_audit.cadence_days "
                    "%d is past 9999-12-31" % (LEXICON_REL, audited, cadence)])
        self.p.config("shorthand: {legibility_audit: {cadence_days: 30}}\n")
        self.lexicon(dated("cfg"), audited="9999-11-30")
        self.due("2026-10-16", stdout=("audit: not due until 9999-12-30\n"
                                       "due: 0 to retire, 0 to review, the audit not due until 9999-12-30\n"))

    def test_a_clean_use_before_ratification_does_not_restart_the_clock(self):
        # r17 fix round 1, F2: the later of the newest clean use and the ratified date
        self.lexicon(dated("nw", ratified_by="human 2026-10-15"))
        self.p.config("shorthand: {retire_after_days_unused: 10, review_cadence_days: 900}\n")
        self.p.record("nw", date="2026-01-02")
        self.due("2026-10-24", stdout=QUIET)
        self.due("2026-10-25", stdout=(
            "retire: nw: unused since 2026-10-15 (ratified), 10 days, after 10 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 1 to retire, 0 to review, the audit not due until 2099-01-31\n"))
        self.p.record("nw", date="2026-10-15")   # a use on the day it is ratified is a use
        self.due("2026-10-25", stdout=(
            "retire: nw: unused since 2026-10-15 (clean use), 10 days, after 10 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 1 to retire, 0 to review, the audit not due until 2099-01-31\n"))
        self.p.record("nw", date="2026-10-20")
        self.due("2026-10-29", stdout=QUIET)
        self.due("2026-10-30", stdout=(
            "retire: nw: unused since 2026-10-20 (clean use), 10 days, after 10 days\n"
            "audit: not due until 2099-01-31\n"
            "due: 1 to retire, 0 to review, the audit not due until 2099-01-31\n"))

    def test_nothing_written(self):
        self.lexicon(dated("cfg"), audited=None)
        self.p.record("cfg", date="2026-10-02")
        before = self.p.tree()
        self.due("2027-10-02")
        self.due("2026-10-16")
        self.assertEqual(self.p.tree(), before)


AGENT_MD = os.path.join(PLUGIN, "agents", "respeak.md")
SKILL_MD = os.path.join(PLUGIN, "skills", "respeak", "SKILL.md")
RENDER = os.path.join(PLUGIN, "scripts", "respeak-render.sh")
USE_CALL = ('"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py use \'<term>\' '
            '--outcome <outcome> [--readback] [--for <class>] --source "<source>" '
            '--root "${CLAUDE_PROJECT_DIR}"')
USES_ITEM = re.compile(r"`([^`]+)` (clean|failure)( readback)?(?: for ([a-z0-9]+(?:-[a-z0-9]+)*))?")


def parse_uses(line):
    """The translator's `uses:` line as (term, outcome, readback, class)
    items, as the skill's step 6 reads it; None for a line out of the
    shape."""
    if not line.startswith("uses: "):
        return None
    body = line[len("uses: "):]
    if body == "none":
        return []
    items = []
    for part in body.split("; "):
        m = USES_ITEM.fullmatch(part)
        if not m:
            return None
        items.append((m.group(1), m.group(2), bool(m.group(3)), m.group(4)))
    return items


def flat(text):
    return " ".join(text.split())


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class UseWiring(Case):
    """The writer: the translator names the uses when asked, the skill
    records them through `use`, and the render never asks."""

    def test_the_agent_text(self):
        text = read(AGENT_MD)
        self.assertIn("tools: Read, Grep, Glob, Write", text.split("\n---\n")[0].splitlines(),
                      "the translator gets no Bash")
        self.assertIn("When the caller asks for uses, one more final line, the last: `uses: ` "
                      "then each lexicon term the source used, `` `<term>` clean `` or "
                      "`` `<term>` failure `` (used true to its definition, or not), plus "
                      "` readback` when its receiver used it back, joined by `; `; with none, "
                      "`uses: none`. A use in an item of a class `shorthand.readback_required_for` "
                      "lists is `clean` only with ` readback`, and its item adds ` for <class>`; "
                      "without the readback, the narrative states that item in full, flagged "
                      "`not read back`. The caller records them; you run nothing.", flat(text))

    def test_the_skill_text(self):
        text = read(SKILL_MD)
        body = flat(text.split("\n---\n", 1)[1])
        self.assertEqual(re.findall(r"(?m)^(\d+)\. ", text), [str(n) for n in range(1, 8)])
        ask = "ask it for its `uses:` line"
        drop = ("First drop each reply's last line when it reads `uses: …`: step 6 records it; "
                "it is neither scanned nor relayed.")
        record = ("6. Record the uses, once, from the agent's first `uses:` line; "
                  "`uses: none` records nothing.")
        flags = ("with `--readback` when the item holds ` readback`, `--for <class>` when it "
                 "ends ` for <class>`")
        skip = ("A refusal naming `no .claude/respeak/` means the project keeps no use record: "
                "skip the rest silently. Name any other refusal in one line after the narrative, "
                "and relay there each `decompress:` line `use` prints.")
        for phrase in (ask, drop, record, USE_CALL, flags, skip):
            self.assertIn(phrase, body)
        order = [body.index(p) for p in ("4. Delegate", ask, "5. Verify", drop, "respeak-measure.py",
                                         record, USE_CALL, flags, skip, "7. If the agent reports")]
        self.assertEqual(order, sorted(order))

    def test_the_grant_admits_the_call(self):
        text = read(SKILL_MD)
        front = text.split("\n---\n", 1)[0]
        rules = re.findall(r"Bash\(([^)]*)\)", re.search(r"(?m)^allowed-tools: (.*)$", front).group(1))
        lines = [l.strip().strip("`") for l in text.splitlines()]
        call = next(l for l in lines if "respeak-lexicon.py use" in l)
        self.assertEqual(call, USE_CALL)
        measure = next(l for l in lines if l.startswith('"') and "respeak-measure.py" in l)
        for each in (call, measure):
            with self.subTest(call=each[:40]):
                # the plugin root substituted as Claude Code does on load, the shell's words
                argv = shlex.split(each.replace("[--readback]", "--readback")
                                   .replace("[--for <class>]", "--for x").split(" <<")[0])
                command = " ".join(argv).replace("${CLAUDE_PLUGIN_ROOT}", "/p")
                self.assertTrue(any(fnmatch.fnmatchcase(command, r.replace("${CLAUDE_PLUGIN_ROOT}", "/p"))
                                    for r in rules), (command, rules))
        self.assertEqual(call.split(" ")[0], measure.split(" ")[0], "step 5's grant, step 6's call")

    def test_the_render_never_asks(self):
        self.assertIsNone(re.search(r"\buses\b", read(RENDER)))

    def test_a_line_in_the_shape_gives_its_records(self):
        self.p.lexicon(entry("cfg"), entry("R1..R7"), entry("2-lane", "proposed", 0.6))
        reply = ("\U0001f4e3 respeak · bluf\n\nThe narrative.\nlexicon: 0 proposals written\n"
                 "uses: `cfg` clean readback; `2-lane` failure; `R1..R7` clean; "
                 "`cfg` clean readback for irreversible-actions")
        *narrative, last = reply.splitlines()
        self.assertNotIn("uses:", "\n".join(narrative), "the narrative scanned and relayed")
        items = parse_uses(last)
        self.assertEqual(items, [("cfg", "clean", True, None), ("2-lane", "failure", False, None),
                                 ("R1..R7", "clean", False, None),
                                 ("cfg", "clean", True, "irreversible-actions")])
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")
        for term, outcome, readback, cls in items:
            argv = (["use", term, "--outcome", outcome] + (["--readback"] if readback else [])
                    + (["--for", cls] if cls else []) + ["--source", "session s1"])
            self.assertRan(self.p.run(*argv, env=env, wrapper=True), 0)
        rec = {"date": "2026-10-16", "source": "session s1"}
        self.assertEqual(lex.uses(self.p.dir), [
            dict(rec, term="cfg", outcome="clean", readback=True),
            dict(rec, term="2-lane", outcome="failure", readback=False),
            dict(rec, term="R1..R7", outcome="clean", readback=False),
            dict(rec, term="cfg", outcome="clean", readback=True, **{"for": "irreversible-actions"})])
        self.assertRan(self.p.run("ratify"), 0,
                       "2-lane: not eligible: 0 of 5 clean uses with readback; "
                       "1 fidelity failure, 0 allowed\n"
                       "ratify: 1 proposed, 0 eligible; shorthand.ratification: human\n")
        # none records nothing; a line out of the shape is not read
        self.assertEqual(parse_uses("uses: none"), [])
        for bad in ("uses: cfg clean", "uses: `cfg` fine", "uses: `cfg` clean, `R1..R7` clean",
                    "uses: `cfg` clean for", "uses: `cfg` clean for Bad Class",
                    "uses: `cfg` clean for x readback",
                    "lexicon: 0 proposals written", "uses: `a`b` clean", "uses: `x; y` clean",
                    "uses: `cfg` clean; `x; y` failure"):
            self.assertIsNone(parse_uses(bad), bad)
        # the refusal the skill skips on is the one `use` gives
        shutil.rmtree(self.p.respeak)
        r = self.p.run("use", "cfg", "--outcome", "clean", env=env, wrapper=True)
        self.assertRan(r, 2, "")
        self.assertIn("no .claude/respeak/", r.stderr)


ATTRIBUTES_REL = os.path.join(".claude", "respeak", ".gitattributes")


class UnionMerge(Case):
    """`use` writes .claude/respeak/.gitattributes (`uses.jsonl merge=union`,
    `audits.jsonl merge=union`) whenever there is none: two branches that
    each append merge with both lines."""

    def setUp(self):
        super().setUp()
        self.env = dict(self.p.env, RESPEAK_TODAY="2026-10-16", GIT_AUTHOR_NAME="t",
                        GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                        GIT_COMMITTER_EMAIL="t@example.invalid")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.p.dir, env=self.env, capture_output=True,
                              text=True, stdin=subprocess.DEVNULL, timeout=60)

    def commit(self, message):
        self.assertEqual(self.git("add", "-A", ".claude").returncode, 0)
        r = self.git("commit", "-q", "-m", message)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def use(self, term, source):
        self.assertRan(self.p.run("use", term, "--outcome", "clean", "--source", source,
                                  env=self.env), 0)

    def branches(self, base, left, right):
        """left and right, each off base with one use appended; then left merges right."""
        for name, term in ((left, "cfg"), (right, "R1..R7")):
            self.assertEqual(self.git("checkout", "-q", "-b", name, base).returncode, 0)
            self.use(term, name)
            self.commit(name)
        self.assertEqual(self.git("checkout", "-q", left).returncode, 0)
        return self.git("merge", "-q", "--no-edit", right)

    def test_two_branches_merge_with_both_lines(self):
        self.use("cfg", "main")
        with open(os.path.join(self.p.dir, ATTRIBUTES_REL), "rb") as f:
            self.assertEqual(f.read(), b"uses.jsonl merge=union\naudits.jsonl merge=union\n")
        self.commit("first use")
        self.assertEqual(self.git("branch", "-M", "main").returncode, 0)
        r = self.branches("main", "left", "right")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([u["source"] for u in lex.uses(self.p.dir)], ["main", "left", "right"])
        # the control: without the attribute the same appends conflict (r18: `use` writes
        # an absent file again, so the control keeps one without the line, never edited)
        self.assertEqual(self.git("checkout", "-q", "-b", "plain", "main").returncode, 0)
        self.p.write(ATTRIBUTES_REL, "# no merge driver\n")
        self.commit("no attributes")
        r = self.branches("plain", "left2", "right2")
        self.assertNotEqual(r.returncode, 0, "without merge=union the appends conflict")
        self.git("merge", "--abort")

    def test_one_that_is_there_is_never_edited(self):
        attributes = os.path.join(self.p.dir, ATTRIBUTES_REL)
        self.p.write(ATTRIBUTES_REL, "*.jsonl -diff\n")
        self.use("cfg", "s")
        with open(attributes) as f:
            self.assertEqual(f.read(), "*.jsonl -diff\n")
        # a symlink is not followed
        os.remove(attributes)
        os.remove(os.path.join(self.p.dir, USES_REL))
        target = self.p.write("elsewhere", "")
        os.symlink(target, attributes)
        self.use("cfg", "s")
        with open(target) as f:
            self.assertEqual(f.read(), "")
        # written whenever absent (r18): a removed one comes back beside an old record
        os.remove(attributes)
        self.use("cfg", "s")
        with open(attributes, "rb") as f:
            self.assertEqual(f.read(), b"uses.jsonl merge=union\naudits.jsonl merge=union\n")

    def test_a_refusal_writes_neither(self):
        r = self.p.run("use", "nope", "--outcome", "clean", env=self.env)
        self.assertRan(r, 2, "")
        self.assertEqual(os.listdir(self.p.respeak), [])


class DefaultRoot(Case):
    """With --root absent: the top of the git work tree holding the current
    directory, else the current directory; in every verb."""

    def bare(self, cwd, *args, env=None):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, env=env or self.p.env,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60)

    def test_a_subdirectory_reads_the_project(self):
        self.p.config("shorthand: {max_entries: 2}\n")
        sub = os.path.join(self.p.dir, "docs", "deep")
        os.makedirs(sub)
        self.assertRan(self.bare(sub, "check"), 0,
                       "lexicon: ok, 2 ratified of 2, the nearest two 6 apart (min 2)\n")
        self.p.lexicon(entry("cfg"), entry("IU", "proposed"))
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")
        r = self.bare(sub, "use", "IU", "--outcome", "clean", env=env)
        self.assertRan(r, 0)
        self.assertEqual([u["term"] for u in lex.uses(self.p.dir)], ["IU"])
        self.assertFalse(os.path.lexists(os.path.join(sub, ".claude")))
        self.assertRan(self.bare(sub, "ratify"), 0,
                       "IU: not eligible: 0 of 5 clean uses with readback\n"
                       "ratify: 1 proposed, 0 eligible; shorthand.ratification: human\n")
        self.assertRan(self.bare(sub, "due", env=env), 0,
                       "retire: cfg: no date\nreview: cfg: no date\n"
                       "audit: due, never audited, every 30 days; fresh-decoder, sample: cfg\n"
                       "due: 1 to retire, 1 to review, the audit due\n")

    def test_outside_git_the_current_directory(self):
        out = os.path.join(self.p.root, "outside")
        os.makedirs(os.path.join(out, ".claude", "respeak"))
        with open(os.path.join(out, LEXICON_REL), "w") as f:
            f.write("entries:\n" + entry("IU") + entry("IV"))
        env = dict(self.p.env, GIT_CEILING_DIRECTORIES=self.p.root, RESPEAK_TODAY="2026-10-16")
        self.assertRan(self.bare(out, "check", env=env), 1,
                       "too near: IU and IV, 1 apart (min 2)\n"
                       "lexicon: 1 problem, 2 ratified of 150, the nearest two 1 apart (min 2)\n")
        self.assertRan(self.bare(out, "use", "IU", "--outcome", "failure", env=env), 0)
        self.assertEqual([u["term"] for u in lex.uses(out)], ["IU"])
        # and --root, given, still wins
        r = self.bare(out, "check", "--root", self.p.dir, env=env)
        self.assertRan(r, 0, SEED_LINE)


REPAIR = ("The repair channel: `shorthand.reserved_metawords` (CORRECTION, SAY-AGAIN, UNVERIFIED by "
          "default) is the words of `never_compress`'s `reserved-metawords` class. Each passes "
          "verbatim, never expanded, never proposed. After CORRECTION only the corrected claim "
          "stands: render it, not the claim it replaces. SAY-AGAIN is an open question: list it "
          "with the open questions. UNVERIFIED marks an unverified claim: flag it as rendering "
          "step 5 says.")
MARKER = ("When `shorthand.register_marker` is `required`, a narrative keeping a ratified term "
          "unexpanded ends its marker line ` · shorthand`.")


def key_comment(key):
    """A shipped shorthand key's line, from the key, and its continuation
    comment lines, without their `#`, flattened."""
    lines = read(SHIPPED).splitlines()
    i = next(n for n, l in enumerate(lines) if l.startswith("  %s:" % key))
    out = [lines[i].strip()]
    for l in lines[i + 1:]:
        if not re.match(r"^ +# ", l):
            break
        out.append(l.strip()[2:])
    return flat(" ".join(out))


def shipped_shorthand():
    with open(SHIPPED, encoding="utf-8") as f:
        return lex.yaml.safe_load(f)["shorthand"]


class ReservedWords(Case):
    """shorthand.reserved_metawords, the repair channel: check holds each
    ratified term min_token_edit_distance from each word, ratify each
    proposed one; both check the key."""

    def test_the_seed_is_ok(self):
        words = shipped_shorthand()["reserved_metawords"]
        self.assertEqual(words, ["CORRECTION", "SAY-AGAIN", "UNVERIFIED"])
        self.assertRan(self.p.run("check"), 0, SEED_LINE)
        near = min(lex.distance(t, w) for t in ("cfg", "R1..R7", "2-lane") for w in words)
        self.assertGreaterEqual(near, 7)

    def test_m_minus_1_is_a_problem_and_m_is_not(self):
        self.p.lexicon(entry("CORRECTIO"), entry("cfg"))
        near = lex.distance("CORRECTIO", "cfg")
        self.assertRan(self.p.run("check"), 1,
                       "reserved: CORRECTIO is 1 from CORRECTION (min 2)\n"
                       "lexicon: 1 problem, 2 ratified of 150, the nearest two %d apart (min 2)\n"
                       % near)
        self.p.lexicon(entry("CORRECTI"), entry("say-agai"), entry("cfg"))
        r = self.p.run("check")
        self.assertRan(r, 1)
        self.assertEqual(r.stdout.splitlines()[:-1], ["reserved: say-agai is 1 from SAY-AGAIN (min 2)"],
                         "case-folded; CORRECTI, 2 from CORRECTION, stands")
        self.p.config("shorthand: {min_token_edit_distance: 3}\n")
        self.assertIn("reserved: CORRECTI is 2 from CORRECTION (min 3)\n", self.p.run("check").stdout)

    def test_retired_and_proposed_terms_are_not_checked(self):
        self.p.lexicon(entry("cfg"), entry("CORRECTIO", "retired"), entry("UNVERIFIE", "proposed"))
        self.assertRan(self.p.run("check"), 0,
                       "lexicon: ok, 1 ratified of 150, no two to compare (min 2)\n")

    def test_ratify_names_the_reserved_word_after_the_distances(self):
        self.p.lexicon(entry("unverifi"), entry("unverifid", "proposed"))
        self.assertRan(self.p.run("ratify"), 0,
                       "unverifid: not eligible: 0 of 5 clean uses with readback; "
                       "1 apart from unverifi, min 2; 1 from the reserved UNVERIFIED, min 2\n"
                       "ratify: 1 proposed, 0 eligible; shorthand.ratification: human\n")

    def test_a_project_list(self):
        self.p.config("shorthand: {reserved_metawords: [ROGER]}\n")
        self.p.lexicon(entry("ROGR"), entry("CORRECTIO"))
        r = self.p.run("check")
        self.assertRan(r, 1)
        self.assertEqual(r.stdout.splitlines()[0], "reserved: ROGR is 1 from ROGER (min 2)")

    def test_a_bad_value_exits_2_in_check_and_ratify(self):
        for value in ("CORRECTION", "[SAY AGAIN]", "['A;B']", "['']", "[1]", "{a: 1}",
                      "['a$b']", "[\"it's\"]"):
            self.p.config("shorthand: {reserved_metawords: %s}\n" % value)
            for verb in ("check", "ratify"):
                with self.subTest(value=value, verb=verb):
                    r = self.p.run(verb)
                    self.assertRan(r, 2, "")
                    self.assertIn("shorthand.reserved_metawords must be a list of words", r.stderr)
            # due reads it not, so does not check it
            env = dict(self.p.env, RESPEAK_TODAY="2026-10-17")
            self.assertRan(self.p.run("due", env=env), 0)

    def test_the_texts(self):
        self.assertIn(REPAIR, flat(read(AGENT_MD)))
        text = read(SHIPPED)
        self.assertIn("# reserved-metawords is the list shorthand.reserved_metawords names.", text)
        self.assertIn("{ class: reserved-metawords,", text)
        self.assertEqual(key_comment("reserved_metawords"),
                         "reserved_metawords: [CORRECTION, SAY-AGAIN, UNVERIFIED] # "
                         "[respeak-lexicon.py check, ratify] the repair channel, never_compress's "
                         "reserved-metawords: words with no whitespace or shell character; a "
                         "ratified term nearer one than min_token_edit_distance is a problem, a "
                         "proposed one not eligible. [instruction-only] the agent passes each "
                         "verbatim")


class RegisterMarker(Case):
    """shorthand.register_marker: the translator's ` · shorthand`; check
    holds it to required or optional."""

    def test_the_shipped_value_and_both_values_pass(self):
        self.assertEqual(shipped_shorthand()["register_marker"], "required")
        for value in ("required", "optional"):
            with self.subTest(value=value):
                self.p.config("shorthand: {register_marker: %s}\n" % value)
                self.assertRan(self.p.run("check"), 0, SEED_LINE)

    def test_a_bad_value_exits_2_in_check_alone(self):
        for value in ('"~"', "always", "true", "[required]", "Required"):
            self.p.config("shorthand: {register_marker: %s}\n" % value)
            with self.subTest(value=value):
                r = self.p.run("check")
                self.assertRan(r, 2, "")
                self.assertIn("shorthand.register_marker must be required or optional", r.stderr)
                # ratify reads it not
                self.assertRan(self.p.run("ratify"), 0)

    def test_the_texts(self):
        self.assertIn(MARKER, flat(read(AGENT_MD)))
        self.assertEqual(key_comment("register_marker"),
                         "register_marker: required # required | optional. [instruction-only] when "
                         "required, a narrative keeping a ratified term unexpanded ends its marker "
                         "line ` · shorthand`; [respeak-lexicon.py check] a value outside the two "
                         "exits 2")


DECOMPRESS_TEXT = ("Decompress, whatever `lexicon_access` says, in each case `shorthand.decompress_on` "
                   "lists: every term when the narrative asks a person to decide or act "
                   "(`escalation-to-human`), when the context is an incident (`incident`), or when "
                   "no profile applied (`new-partner`); and a term a `decompress:` line names "
                   "(`repeated-fidelity-failure`).")


class ReadbackFor(Case):
    """shorthand.readback_required_for, read and checked by `use` each call:
    `--for CLASS` refuses a class not listed, or a clean use without
    --readback; the record gains `for`."""

    def setUp(self):
        super().setUp()
        self.env = dict(self.p.env, RESPEAK_TODAY="2026-10-17")

    def use(self, *args):
        return self.p.run("use", "cfg", *args, env=self.env)

    def test_the_shipped_classes(self):
        self.assertEqual(shipped_shorthand()["readback_required_for"],
                         ["irreversible-actions", "security-findings", "escalations-to-human"])

    def test_a_listed_class_with_readback_is_clean(self):
        self.assertRan(self.use("--outcome", "clean", "--readback", "--for", "security-findings"), 0,
                       "use: cfg clean with readback for security-findings on 2026-10-17, "
                       "recorded in %s\n" % USES_REL)
        self.assertRan(self.use("--outcome", "failure", "--for", "irreversible-actions"), 0)
        self.assertEqual([(u["outcome"], u["readback"], u["for"]) for u in lex.uses(self.p.dir)],
                         [("clean", True, "security-findings"),
                          ("failure", False, "irreversible-actions")])
        # without --for, no key
        self.assertRan(self.use("--outcome", "clean"), 0)
        self.assertNotIn("for", lex.uses(self.p.dir)[-1])

    def test_clean_without_readback_or_an_unlisted_class_exits_2(self):
        for args, why in ((("--outcome", "clean", "--for", "security-findings"),
                           "a clean use for security-findings needs --readback"),
                          (("--outcome", "clean", "--readback", "--for", "deploys"),
                           "deploys is not in shorthand.readback_required_for"),
                          (("--outcome", "failure", "--for", "incident"),
                           "incident is not in shorthand.readback_required_for")):
            with self.subTest(args=args):
                r = self.use(*args)
                self.assertRan(r, 2, "")
                self.assertIn(why, r.stderr)
        self.assertFalse(os.path.lexists(os.path.join(self.p.dir, USES_REL)), "nothing written")
        # a project's own list
        self.p.config("shorthand: {readback_required_for: [deploys]}\n")
        self.assertRan(self.use("--outcome", "clean", "--readback", "--for", "deploys"), 0)

    def test_a_bad_value_exits_2_each_call(self):
        for value in ("irreversible-actions", "[Bad Slug]", "['']", "[1]", "[a--b]", "[-a]"):
            with self.subTest(value=value):
                self.p.config("shorthand: {readback_required_for: %s}\n" % value)
                r = self.use("--outcome", "clean")
                self.assertRan(r, 2, "")
                self.assertIn("shorthand.readback_required_for must be a list of slugs", r.stderr)
        # check and ratify read it not
        self.assertRan(self.p.run("check"), 0, SEED_LINE)

    def test_a_record_whose_for_is_not_a_string_is_skipped(self):
        self.p.record("cfg")
        with open(os.path.join(self.p.dir, USES_REL), "a") as f:
            f.write(json.dumps({"term": "cfg", "date": "2026-10-16", "outcome": "clean",
                                "readback": True, "for": 1}) + "\n")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(len(lex.uses(self.p.dir)), 1)
        self.assertIn("uses.jsonl:2: for is not a string; skipped", err.getvalue())


class DecompressOn(Case):
    """shorthand.decompress_on, read and checked by `use` each call; with
    repeated-fidelity-failure, a term with 2 failure uses gets its
    `decompress:` line. The translator expands every term in a listed case."""

    def setUp(self):
        super().setUp()
        self.env = dict(self.p.env, RESPEAK_TODAY="2026-10-17")

    def test_the_shipped_cases(self):
        self.assertEqual(shipped_shorthand()["decompress_on"],
                         ["escalation-to-human", "incident", "repeated-fidelity-failure",
                          "new-partner"])

    def test_two_failure_uses_name_the_term(self):
        line = "decompress: cfg: %d failure uses (shorthand.decompress_on)\n"
        r = self.p.run("use", "cfg", "--outcome", "failure", env=self.env)
        self.assertRan(r, 0)
        self.assertNotIn("decompress:", r.stdout)
        r = self.p.run("use", "cfg", "--outcome", "failure", env=self.env)
        self.assertRan(r, 0)
        self.assertTrue(r.stdout.endswith(line % 2), r.stdout)
        # a later use of the term, clean too, names it again; another term not
        r = self.p.run("use", "cfg", "--outcome", "clean", env=self.env)
        self.assertTrue(r.stdout.endswith(line % 2), r.stdout)
        r = self.p.run("use", "R1..R7", "--outcome", "failure", env=self.env)
        self.assertNotIn("decompress:", r.stdout)
        # unlisted, no line
        self.p.config("shorthand: {decompress_on: [incident, new-partner]}\n")
        r = self.p.run("use", "cfg", "--outcome", "failure", env=self.env)
        self.assertRan(r, 0)
        self.assertNotIn("decompress:", r.stdout)

    def test_a_bad_value_exits_2_each_call(self):
        for value in ("incident", "[panic]", "[Incident]", "[1]", "{a: 1}"):
            with self.subTest(value=value):
                self.p.config("shorthand: {decompress_on: %s}\n" % value)
                r = self.p.run("use", "cfg", "--outcome", "clean", env=self.env)
                self.assertRan(r, 2, "")
                self.assertIn("shorthand.decompress_on must be a list of escalation-to-human, "
                              "incident, repeated-fidelity-failure, new-partner", r.stderr)
        self.assertFalse(os.path.lexists(os.path.join(self.p.dir, USES_REL)), "nothing written")
        self.assertRan(self.p.run("ratify"), 0)

    def test_the_texts(self):
        self.assertIn(DECOMPRESS_TEXT, flat(read(AGENT_MD)))
        self.assertEqual(key_comment("decompress_on"),
                         "decompress_on: [escalation-to-human, incident, repeated-fidelity-failure, "
                         "new-partner] # [respeak-lexicon.py use] only these four, checked each call; "
                         "with repeated-fidelity-failure, `use` names a term with 2 failure uses. "
                         "[instruction-only] the agent expands every term in a listed case, whatever "
                         "narrative.lexicon_access says")
        self.assertEqual(key_comment("readback_required_for"),
                         "readback_required_for: [irreversible-actions, security-findings, "
                         "escalations-to-human] # [respeak-lexicon.py use] slugs, checked each call; "
                         "`use --for CLASS` refuses a class not listed, or a clean use without "
                         "--readback. [instruction-only] a use in an item of a listed class is clean "
                         "only with readback, its item adding ` for <class>`")


AUDIT_MD = os.path.join(PLUGIN, "skills", "audit", "SKILL.md")
AUDITS_REL = os.path.join(".claude", "respeak", "audits.jsonl")
AUDIT_LEX = ('version: 1\n# kept, byte for byte\nentries:\n'
             '  - term: "cfg"\n    expansion: "configuration"\n    status: ratified\n'
             '    ratified_by: human 2026-08-31\n'
             '  - term: "R1..R7"\n    expansion: "research dimension 1-7"\n    status: ratified\n'
             '    ratified_by: human 2026-08-31\n'
             '  - term: "IU"\n    expansion: "in use"\n    status: proposed\n')
UNION = b"uses.jsonl merge=union\naudits.jsonl merge=union\n"


class DecoderAudit(Case):
    """`audit` reads a fresh decoder's `<term>: <decoding>` lines for today's
    sample, appends audits.jsonl and sets the lexicon's `audited:`; and
    the skill /respeak:audit that feeds it."""

    def setUp(self):
        super().setUp()
        self.lex = self.p.write(LEXICON_REL, AUDIT_LEX)

    def audit(self, text, day="2026-10-17", root=None):
        env = dict(self.p.env, RESPEAK_TODAY=day)
        return subprocess.run([sys.executable, SCRIPT, "audit", "--root", root or self.p.dir],
                              input=text, env=env, cwd=self.p.root, capture_output=True,
                              text=True, timeout=60)

    def audits(self):
        with open(os.path.join(self.p.dir, AUDITS_REL), encoding="utf-8") as f:
            return [json.loads(l) for l in f]

    def lexicon_bytes(self):
        with open(self.lex, "rb") as f:
            return f.read()

    def test_decoded_missed_and_the_writes(self):
        r = self.audit("cfg: configuration\nR1..R7: rules 1 through 7\n")
        self.assertRan(r, 0, 'audit: cfg: decoded\naudit: R1..R7: missed, read as "rules 1 through 7"\n'
                             "audit: 1 of 2 decoded, audited 2026-10-17\n")
        rec = {"date": "2026-10-17", "method": "fresh-decoder"}
        self.assertEqual(self.audits(), [
            dict(rec, term="cfg", decoding="configuration", decoded=True),
            dict(rec, term="R1..R7", decoding="rules 1 through 7", decoded=False)])
        self.assertEqual(list(self.audits()[0]), ["term", "date", "method", "decoding", "decoded"])
        self.assertFalse(os.path.lexists(os.path.join(self.p.dir, USES_REL)), "a decoding is no use")
        self.assertEqual(self.lexicon_bytes(),
                         AUDIT_LEX.replace("version: 1\n", "version: 1\naudited: 2026-10-17\n").encode())
        self.assertEqual(lex.lexicon_file(self.p.dir)[0]["audited"], datetime.date(2026, 10, 17))
        with open(os.path.join(self.p.dir, ATTRIBUTES_REL), "rb") as f:
            self.assertEqual(f.read(), UNION)
        r = self.p.run("due", env=dict(self.p.env, RESPEAK_TODAY="2026-10-17"))
        self.assertRan(r, 0)
        self.assertIn("audit: not due until 2026-11-16", r.stdout.splitlines())
        # a later audit replaces the line and appends; the brief's other reading decodes
        r = self.audit("R1..R7: Research dimensions 1 to 7\ncfg: config file\n", day="2026-11-20")
        self.assertRan(r, 0)
        self.assertEqual(r.stdout.splitlines(), ["audit: cfg: missed, read as \"config file\"",
                                                 "audit: R1..R7: decoded",
                                                 "audit: 1 of 2 decoded, audited 2026-11-20"])
        self.assertEqual(len(self.audits()), 4)
        self.assertEqual(self.lexicon_bytes(),
                         AUDIT_LEX.replace("version: 1\n", "version: 1\naudited: 2026-11-20\n").encode())

    def test_the_rule(self):
        for expansion, decoding, ok in (("configuration", "Configuration!", True),
                                        ("research dimension 1-7", "research dimensions 1 to 7", True),
                                        ("research dimension 1-7", "rules 1 through 7", False),
                                        ("two-lane architecture", "the 2 lane arch", False),
                                        ("two-lane architecture", "two lanes, architectures", True),
                                        ("configuration", "", False)):
            with self.subTest(decoding=decoding):
                self.assertEqual(lex.decodes(expansion, decoding), ok)

    def test_a_term_with_no_line_is_missed_and_nothing_decoded_exits_0(self):
        r = self.audit("cfg: a cat\n")
        self.assertRan(r, 0, 'audit: cfg: missed, read as "a cat"\naudit: R1..R7: missed, read as ""\n'
                             "audit: 0 of 2 decoded, audited 2026-10-17\n")

    def test_an_empty_decoding_is_missed_not_refused(self):
        # F1: `cfg: ` and a bare `cfg:` are empty decodings, scored and recorded; a term with
        # a colon of its own still splits at `: `; a line with no colon stays refused
        for text, reading in (("cfg: \nR1..R7: research dimensions 1 to 7\n", "research dimensions 1 to 7"),
                              ("R1..R7:research dimension 1 7\ncfg:\n", "research dimension 1 7")):
            with self.subTest(text=text):
                os.remove(self.lex)
                self.p.write(LEXICON_REL, AUDIT_LEX)
                before = len(self.audits()) if os.path.exists(os.path.join(self.p.dir, AUDITS_REL)) else 0
                r = self.audit(text)
                self.assertRan(r, 0)
                self.assertEqual(r.stdout.splitlines()[:2], ['audit: cfg: missed, read as ""',
                                                             "audit: R1..R7: decoded"])
                self.assertEqual([(a["term"], a["decoding"], a["decoded"])
                                  for a in self.audits()[before:]],
                                 [("cfg", "", False), ("R1..R7", reading, True)])
        self.p.write(LEXICON_REL, AUDIT_LEX.replace('"cfg"', '"c:fg"'))
        r = self.audit("c:fg: configuration\nR1..R7:\n")
        self.assertRan(r, 0)
        self.assertEqual(r.stdout.splitlines()[:2], ["audit: c:fg: decoded",
                                                     'audit: R1..R7: missed, read as ""'])
        r = self.audit("cfg configuration\n")
        self.assertRan(r, 2, "")
        self.assertIn("stdin line 1 is not `<term>: <decoding>`", r.stderr)

    def test_a_failure_before_the_stamp_writes_nothing(self):
        # F2: the stamp (a rename in .claude/respeak/) goes first, the records after, so a
        # directory that refuses the rename leaves neither, a writable record there included
        record = self.p.write(AUDITS_REL, "")
        os.chmod(self.p.respeak, 0o555)
        self.addCleanup(os.chmod, self.p.respeak, 0o755)
        before = self.lexicon_bytes()
        r = self.audit("cfg: configuration\n")
        self.assertRan(r, 2, "")
        with open(record, "rb") as f:
            self.assertEqual(f.read(), b"", "no record")
        self.assertEqual(self.lexicon_bytes(), before, "no stamp")
        help_text = " ".join(self.p.run("audit", "--help").stdout.split())
        self.assertIn("a failure between the two leaves the stamp set and no records", help_text)
        self.assertIn("A failure between the two leaves the stamp set and no records",
                      flat(read(AUDIT_MD)))

    def test_inserted_before_entries_without_version_and_a_line_replaced(self):
        text = AUDIT_LEX.replace("version: 1\n", "")
        self.p.write(LEXICON_REL, text)
        self.assertRan(self.audit("cfg: configuration\n"), 0)
        self.assertEqual(self.lexicon_bytes(),
                         text.replace("entries:\n", "audited: 2026-10-17\nentries:\n").encode())
        text = AUDIT_LEX.replace("version: 1\n", "version: 1\naudited: 2026-01-01 # old\n")
        self.p.write(LEXICON_REL, text)
        self.assertRan(self.audit("cfg: configuration\n"), 0)
        self.assertEqual(self.lexicon_bytes(),
                         text.replace("audited: 2026-01-01 # old", "audited: 2026-10-17").encode())

    def test_refusals_exit_2_and_write_nothing(self):
        sample = "today's sample (cfg, R1..R7)"
        for text, why in (("IU: in use\n", "not in %s: IU" % sample),
                          ("cfg: configuration\nnope: x\nIU: y\n", "not in %s: nope, IU" % sample),
                          ("cfg: configuration\ncfg: again\n", "cfg twice"),
                          ("cfg configuration\n", "stdin line 1 is not `<term>: <decoding>`")):
            with self.subTest(text=text):
                before = self.p.tree()
                r = self.audit(text)
                self.assertRan(r, 2, "")
                self.assertIn(why, r.stderr)
                self.assertEqual(self.p.tree(), before)
        # the sample is today's pick: with sample 1, the other term is refused
        self.p.config("shorthand: {legibility_audit: {sample: 1}}\n")
        chosen = lex.pick(["cfg", "R1..R7"], 1, "2026-10-17")
        other = ({"cfg", "R1..R7"} - set(chosen)).pop()
        r = self.audit("%s: x\n" % other)
        self.assertRan(r, 2, "")
        self.assertIn("not in today's sample (%s): %s" % (chosen[0], other), r.stderr)

    def test_never_the_seed_nor_a_symlink(self):
        os.remove(self.lex)
        r = self.audit("cfg: configuration\n")
        self.assertRan(r, 2, "")
        self.assertIn("never the seed", r.stderr)
        target = self.p.write("elsewhere.yaml", AUDIT_LEX)
        os.symlink(target, self.lex)
        r = self.audit("cfg: configuration\n")
        self.assertRan(r, 2, "")
        self.assertIn("lexicon.yaml is a symlink", r.stderr)
        os.remove(self.lex)
        self.p.write(LEXICON_REL, AUDIT_LEX)
        os.symlink(target, os.path.join(self.p.dir, AUDITS_REL))
        before = self.p.tree()
        r = self.audit("cfg: configuration\n")
        self.assertRan(r, 2, "")
        self.assertIn("audits.jsonl is a symlink", r.stderr)
        self.assertEqual(self.p.tree(), before)

    def test_the_skill(self):
        text = read(AUDIT_MD)
        front, body = text.split("\n---\n", 1)
        self.assertIn("disable-model-invocation: true", front.splitlines())
        self.assertIn("allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/scripts/py respeak-lexicon.py *)",
                      front.splitlines())
        body = flat(body)
        due = ('"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py due '
               '--root "${CLAUDE_PROJECT_DIR}"')
        stop = "Stop unless a line begins `audit: due`"
        agent = "a fresh `general-purpose` agent"
        prompt = '"Read no file. Write `<term>: <meaning>` for each"'
        fresh = ("It counts as fresh though it loads the project's CLAUDE.md, a lexicon digest "
                 "that file imports included")
        call = ('"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py audit '
                '--root "${CLAUDE_PROJECT_DIR}" <<\'RESPEAK_EOF\'')
        order = [body.index(p) for p in (due, stop, agent, prompt, fresh, call)]
        self.assertEqual(order, sorted(order))
        rule = "/p/scripts/py respeak-lexicon.py *"
        for each in (due, call):
            argv = shlex.split(each.split(" <<")[0])
            self.assertTrue(fnmatch.fnmatchcase(" ".join(argv).replace("${CLAUDE_PLUGIN_ROOT}", "/p"),
                                                rule), each)


class R17Seams(Case):
    """r17's three seams: an empty --root is refused; .gitattributes is
    written whenever absent; `due` reads `reviewed:` on ratified entries
    only."""

    def test_an_empty_root_exits_2_in_every_verb(self):
        for argv in (["check"], ["use", "cfg", "--outcome", "clean"], ["ratify"], ["due"], ["audit"]):
            with self.subTest(verb=argv[0]):
                r = subprocess.run([sys.executable, SCRIPT, *argv, "--root", ""], cwd=self.p.dir,
                                   env=self.p.env, capture_output=True, text=True, input="",
                                   timeout=60)
                self.assertRan(r, 2, "")
                self.assertIn("--root is empty; refused", r.stderr)
        self.assertEqual(os.listdir(self.p.respeak), [])

    def test_gitattributes_whenever_absent(self):
        # a 0.9.0 project: a record and no .gitattributes
        self.p.record("cfg")
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-17")
        self.assertRan(self.p.run("use", "cfg", "--outcome", "clean", env=env), 0)
        with open(os.path.join(self.p.dir, ATTRIBUTES_REL), "rb") as f:
            self.assertEqual(f.read(), UNION)

    def test_due_reads_reviewed_on_ratified_entries_only(self):
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-17")
        self.p.write(LEXICON_REL, "entries:\n" + dated("cfg", status="proposed", reviewed="soon")
                     + dated("IU", status="retired", reviewed="5") + dated("R1..R7"))
        self.assertRan(self.p.run("due", env=env), 0)
        self.p.write(LEXICON_REL, "entries:\n" + dated("cfg", reviewed="soon"))
        r = self.p.run("due", env=env)
        self.assertRan(r, 2, "")
        self.assertIn("entries[0] (cfg): reviewed must be a YYYY-MM-DD date", r.stderr)


if __name__ == "__main__":
    unittest.main()
