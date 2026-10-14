"""Tests for scripts/hygiene's private list (packet public-r1, Act 1).

The private terms live outside the repo, in `$AGENTIK_HYGIENE_PRIVATE` or
`${XDG_CONFIG_HOME:-$HOME/.config}/agentik/hygiene-private.tsv`. Every term here is
invented (`zorblax`, `quuxfrob`), so this file names nothing private. Each case
builds a throwaway git repo and runs the script with `--repo`.
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HYGIENE = os.path.join(ROOT, "scripts", "hygiene")
ABSENT_LINE = "hygiene: no private list at %s; generic groups only"


class PrivateListTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.config = os.path.join(self.tmp.name, "config")
        os.makedirs(os.path.join(self.config, "agentik"))
        self.listfile = os.path.join(self.tmp.name, "private.tsv")

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def run_hygiene(self, *args, listfile="unset", xdg=None):
        env = {k: v for k, v in os.environ.items()
               if k not in ("AGENTIK_HYGIENE_PRIVATE", "XDG_CONFIG_HOME")}
        env["HOME"] = self.tmp.name
        if listfile != "unset":
            env["AGENTIK_HYGIENE_PRIVATE"] = listfile
        if xdg:
            env["XDG_CONFIG_HOME"] = xdg
        return subprocess.run([sys.executable, HYGIENE, "--repo", self.repo, *args],
                              capture_output=True, text=True, env=env, timeout=60)

    def test_a_private_group_hit_counts_and_never_prints_its_regex(self):
        with open(self.listfile, "w", encoding="utf-8") as fh:
            fh.write("invented\tzorbla[x]\n")
        self.write("notes.md", "a line about Zorblax\n")
        p = self.run_hygiene(listfile=self.listfile)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("notes.md  invented  1", p.stdout)
        self.assertNotIn("zorbla[x]", p.stdout + p.stderr)
        self.assertNotIn("Zorblax", p.stdout + p.stderr)

    def test_the_allowlist_may_name_a_private_group(self):
        with open(self.listfile, "w", encoding="utf-8") as fh:
            fh.write("invented\tzorblax\n")
        self.write("notes.md", "zorblax\n")
        self.write(".hygiene-allow", "notes.md: invented\n")
        self.assertEqual(self.run_hygiene(listfile=self.listfile).returncode, 0)
        # The same allowlist, the list absent: the group name is tolerated, not a usage error.
        p = self.run_hygiene(listfile=os.path.join(self.tmp.name, "gone.tsv"))
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_the_xdg_path_is_read_when_the_env_is_unset(self):
        with open(os.path.join(self.config, "agentik", "hygiene-private.tsv"), "w",
                  encoding="utf-8") as fh:
            fh.write("invented\tquuxfrob\n")
        self.write("notes.md", "quuxfrob\n")
        p = self.run_hygiene(xdg=self.config)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertIn("notes.md  invented  1", p.stdout)

    def test_comments_and_blank_lines_are_skipped(self):
        with open(self.listfile, "w", encoding="utf-8") as fh:
            fh.write("# invented\tzorblax\n\n   \n#quuxfrob\n")
        self.write("notes.md", "zorblax quuxfrob\n")
        p = self.run_hygiene(listfile=self.listfile)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(p.stderr, "")

    def test_an_absent_list_prints_one_line_and_runs_the_generic_groups(self):
        gone = os.path.join(self.tmp.name, "gone.tsv")
        self.write("notes.md", "zorblax\n")
        p = self.run_hygiene(listfile=gone)
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(p.stderr.splitlines(), [ABSENT_LINE % gone])
        self.write("paths.md", "/Users/" + "someone/x\n")  # split: this file stays clean
        p = self.run_hygiene(listfile=gone)
        self.assertEqual(p.returncode, 1, p.stdout)
        self.assertIn("paths.md  home  1", p.stdout)

    def test_require_private_exits_2_on_an_absent_or_unreadable_list(self):
        self.write("notes.md", "clean\n")
        p = self.run_hygiene("--require-private", listfile=os.path.join(self.tmp.name, "gone"))
        self.assertEqual(p.returncode, 2)
        self.assertIn("--require-private", p.stderr)
        p = self.run_hygiene("--require-private", listfile=self.config)  # a directory
        self.assertEqual(p.returncode, 2)
        with open(self.listfile, "w", encoding="utf-8") as fh:
            fh.write("invented\tzorblax\n")
        self.assertEqual(self.run_hygiene("--require-private", listfile=self.listfile).returncode, 0)

    def test_a_bad_line_is_named_by_its_number_never_its_text(self):
        with open(self.listfile, "w", encoding="utf-8") as fh:
            fh.write("# header\ninvented\tzorblax\nno-tab-quuxfrob\ninvented\t(unclosed\n")
        p = self.run_hygiene(listfile=self.listfile)
        self.assertEqual(p.returncode, 2)
        self.assertIn(":3: bad entry", p.stderr)
        self.assertNotIn("quuxfrob", p.stderr)
        self.assertNotIn("zorblax", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
