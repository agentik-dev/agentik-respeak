"""Tests for plugin/scripts/respeak-lexicon.py: the lexicon's static rules.

The script reads R/.claude/respeak/lexicon.yaml, else the plugin's seed, and
`shorthand` from the plugin defaults with R/.claude/respeak/config.yaml over
them; no user, folder or local layer. Each case builds a project under a
temp HOME (CLAUDE_CONFIG_DIR inside it) and runs the script with --root.
Exits: check 0 ok, 1 a problem, 2 a bad value or lexicon.
"""
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


if __name__ == "__main__":
    unittest.main()
