"""Tests for plugin/scripts/respeak-lexicon.py: the lexicon's static rules and
its use record.

The script reads R/.claude/respeak/lexicon.yaml, else the plugin's seed, and
`shorthand` from the plugin defaults with R/.claude/respeak/config.yaml over
them; no user, folder or local layer. `use` appends to
R/.claude/respeak/uses.jsonl. Each case builds a project under a temp HOME
(CLAUDE_CONFIG_DIR inside it) and runs the script with --root.
Exits: check 0 ok, 1 a problem; use 0; each 2 on a bad value, a bad lexicon
or a refusal.
"""
import contextlib
import datetime
import importlib.util
import io
import json
import os
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
    """A project under a temp HOME, with a .claude/respeak/ directory."""

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
                         "RESPEAK_PYTHON": sys.executable})
        for k in ("RESPEAK_CONFIG", "RESPEAK_TODAY", "CLAUDE_PLUGIN_ROOT"):
            self.env.pop(k, None)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.dir, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(textwrap.dedent(text))
        return path

    def config(self, text):
        return self.write(".claude/respeak/config.yaml", text)

    def lexicon(self, *entries):
        return self.write(".claude/respeak/lexicon.yaml", "version: 1\nentries:\n" + "".join(entries))

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


if __name__ == "__main__":
    unittest.main()
