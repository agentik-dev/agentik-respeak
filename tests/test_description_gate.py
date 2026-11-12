"""Packet p1-description-gate (hq design/09 §2, §9 step 4): the plugin's loaded descriptions
stay at or under 1,024 B, measured by agentik-commons' vendored scripts/plugin-description-bytes
in `make check`; the include skill stays hidden, and every counted description is non-empty."""
import hashlib
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
SCRIPT = os.path.join(ROOT, "scripts", "plugin-description-bytes")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    return re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1)


class DescriptionGate(unittest.TestCase):
    def test_g1_the_sum_is_under_the_ceiling(self):
        p = subprocess.run([sys.executable, "-B", SCRIPT, PLUGIN], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stderr), (0, ""))
        self.assertEqual(p.stdout.splitlines(), ["hidden  skill  include", "189  skill  respeak",
                                                 "385  agent  respeak", "total 574 of 1024 B"])

    def test_g2_include_hidden_and_counted_descriptions_non_empty(self):
        head = frontmatter(read(os.path.join(PLUGIN, "skills", "include", "SKILL.md")))
        self.assertIn("\ndisable-model-invocation: true\n", "\n" + head + "\n")
        for rel in (("skills", "respeak", "SKILL.md"), ("agents", "respeak.md")):
            head = frontmatter(read(os.path.join(PLUGIN, *rel)))
            m = re.search(r"(?ms)^description: >\n((?:  .*\n?)+)", head)
            text = " ".join(line.strip() for line in m.group(1).splitlines())
            self.assertTrue(text, rel)
            if rel[0] == "skills":
                self.assertLess(len(text), 201, rel)

    def test_g3_the_vendored_copy_is_listed(self):
        with open(SCRIPT, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        rows = read(os.path.join(ROOT, "scripts", "vendored.sha256")).splitlines()
        self.assertIn("%s  scripts/plugin-description-bytes" % digest, rows)

    def test_g4_the_check_runs_it(self):
        make = read(os.path.join(ROOT, "Makefile"))
        line = re.search(r"(?m)^check-unlocked:(.*)$", make).group(1).split()
        self.assertIn("descriptions", line)
        self.assertIn("\t$(PYTHON) scripts/plugin-description-bytes plugin\n", make)


if __name__ == "__main__":
    unittest.main()
