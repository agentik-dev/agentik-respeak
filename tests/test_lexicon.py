"""Tests for plugin/scripts/respeak-lexicon.py: the lexicon's static rules, its
use record, the ratification verdict, and its clocks; and the writer's
wiring, the translator's `uses:` line and the skill's step 6 that records it.

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
                ("", dated("cfg", status="proposed", reviewed="5"), "reviewed must be"),
                ("", dated("cfg", reviewed="2026-10-01T10:00:00"), "reviewed must be"),
                ("audited: 2026/10/01\n", dated("cfg"), "audited must be a YYYY-MM-DD date"),
                ("", dated("cfg", reviewed="2026-13-01"), "unreadable: month must be in 1..12")):
            with self.subTest(entries=entries, head=head):
                self.p.write(".claude/respeak/lexicon.yaml", head + "entries:\n" + entries)
                r = self.due("2026-10-16", code=2, stdout="")
                self.assertIn(why, r.stderr)
        self.lexicon(dated("cfg"))
        r = self.due("2026-10-32", code=2, stdout="")
        self.assertIn("RESPEAK_TODAY", r.stderr)

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
USE_CALL = ('"${CLAUDE_PLUGIN_ROOT}/scripts/py" respeak-lexicon.py use "<term>" '
            '--outcome <outcome> [--readback] --source "<source>" --root "${CLAUDE_PROJECT_DIR}"')
USES_ITEM = re.compile(r"`([^`]+)` (clean|failure)( readback)?")


def parse_uses(line):
    """The translator's `uses:` line as (term, outcome, readback) items, as
    the skill's step 6 reads it; None for a line out of the shape."""
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
        items.append((m.group(1), m.group(2), bool(m.group(3))))
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
                      "`uses: none`. The caller records them; you run nothing.", flat(text))

    def test_the_skill_text(self):
        text = read(SKILL_MD)
        body = flat(text.split("\n---\n", 1)[1])
        self.assertEqual(re.findall(r"(?m)^(\d+)\. ", text), [str(n) for n in range(1, 8)])
        ask = "ask it for its `uses:` line"
        drop = ("First drop each reply's last line when it reads `uses: …`: step 6 records it; "
                "it is neither scanned nor relayed.")
        record = ("6. Record the uses, once, from the agent's first `uses:` line; "
                  "`uses: none` records nothing.")
        skip = ("A refusal naming `no .claude/respeak/` means the project keeps no use record: "
                "skip the rest silently. Name any other refusal in one line after the narrative.")
        for phrase in (ask, drop, record, USE_CALL, skip):
            self.assertIn(phrase, body)
        order = [body.index(p) for p in ("4. Delegate", ask, "5. Verify", drop, "respeak-measure.py",
                                         record, USE_CALL, skip, "7. If the agent reports")]
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
                argv = shlex.split(each.replace("[--readback]", "--readback").split(" <<")[0])
                command = " ".join(argv).replace("${CLAUDE_PLUGIN_ROOT}", "/p")
                self.assertTrue(any(fnmatch.fnmatchcase(command, r.replace("${CLAUDE_PLUGIN_ROOT}", "/p"))
                                    for r in rules), (command, rules))
        self.assertEqual(call.split(" ")[0], measure.split(" ")[0], "step 5's grant, step 6's call")

    def test_the_render_never_asks(self):
        self.assertIsNone(re.search(r"\buses\b", read(RENDER)))

    def test_a_line_in_the_shape_gives_its_records(self):
        self.p.lexicon(entry("cfg"), entry("R1..R7"), entry("2-lane", "proposed", 0.6))
        reply = ("\U0001f4e3 respeak · bluf\n\nThe narrative.\nlexicon: 0 proposals written\n"
                 "uses: `cfg` clean readback; `2-lane` failure; `R1..R7` clean")
        *narrative, last = reply.splitlines()
        self.assertNotIn("uses:", "\n".join(narrative), "the narrative scanned and relayed")
        items = parse_uses(last)
        self.assertEqual(items, [("cfg", "clean", True), ("2-lane", "failure", False),
                                 ("R1..R7", "clean", False)])
        env = dict(self.p.env, RESPEAK_TODAY="2026-10-16")
        for term, outcome, readback in items:
            argv = (["use", term, "--outcome", outcome] + (["--readback"] if readback else [])
                    + ["--source", "session s1"])
            self.assertRan(self.p.run(*argv, env=env, wrapper=True), 0)
        rec = {"date": "2026-10-16", "source": "session s1"}
        self.assertEqual(lex.uses(self.p.dir), [
            dict(rec, term="cfg", outcome="clean", readback=True),
            dict(rec, term="2-lane", outcome="failure", readback=False),
            dict(rec, term="R1..R7", outcome="clean", readback=False)])
        self.assertRan(self.p.run("ratify"), 0,
                       "2-lane: not eligible: 0 of 5 clean uses with readback; "
                       "1 fidelity failure, 0 allowed\n"
                       "ratify: 1 proposed, 0 eligible; shorthand.ratification: human\n")
        # none records nothing; a line out of the shape is not read
        self.assertEqual(parse_uses("uses: none"), [])
        for bad in ("uses: cfg clean", "uses: `cfg` fine", "uses: `cfg` clean, `R1..R7` clean",
                    "lexicon: 0 proposals written"):
            self.assertIsNone(parse_uses(bad), bad)
        # the refusal the skill skips on is the one `use` gives
        shutil.rmtree(self.p.respeak)
        r = self.p.run("use", "cfg", "--outcome", "clean", env=env, wrapper=True)
        self.assertRan(r, 2, "")
        self.assertIn("no .claude/respeak/", r.stderr)


if __name__ == "__main__":
    unittest.main()
