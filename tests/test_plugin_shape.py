"""What the plugin ships after r19: one narrator, its agent, and what callers run.

Callers outside this repo run the render and the verifier from the installed plugin,
ask for the agent by name, and call the skill as
`/respeak:respeak technical design/readme/source.md; <contract>`, so a cut that drops
one of them breaks a README render elsewhere.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
SKILL = os.path.join(PLUGIN, "skills", "respeak", "SKILL.md")
AGENT = os.path.join(PLUGIN, "agents", "respeak.md")
MODES = ("eli5", "bluf", "technical")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    return re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1)


class Shape(unittest.TestCase):
    def test_no_hook_ships(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "hooks")))
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["name"], "respeak")
        self.assertNotIn("hooks", manifest)
        self.assertEqual(sorted(manifest["userConfig"]), ["default_mode", "tech_level"])

    def test_skills_are_the_narrator_and_the_include(self):
        self.assertEqual(sorted(os.listdir(os.path.join(PLUGIN, "skills"))), ["include", "respeak"])

    def test_what_callers_run_ships(self):
        for name in ("respeak-render.sh", "respeak-verify-edit.py", "respeak-deadline.sh",
                     "respeak-measure.py", "respeak-config.py", "respeak-config.sh",
                     "respeak-check.sh", "respeak-include.py", "py"):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "scripts", name)), name)
        for name in ("banned-phrases.yaml", "replacements.yaml"):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "corpus", name)), name)


class Narrator(unittest.TestCase):
    def test_the_skill_keeps_its_invocation(self):
        text = read(SKILL)
        head = frontmatter(text)
        self.assertIn("name: respeak\n", head)
        self.assertIn("arguments: [mode, source]\n", head)
        self.assertIn('argument-hint: "[eli5|bluf|technical] ', head)
        body = text[len(head):]
        self.assertIn("$ARGUMENTS", body)
        self.assertIn("$mode", body)
        self.assertIn("$source", body)
        self.assertIn("/respeak:respeak technical design/readme/source.md; <contract>", body)

    def test_the_skill_is_a_page(self):
        self.assertLessEqual(read(SKILL).count("\n"), 60)

    def test_the_skill_names_only_what_ships(self):
        for name in re.findall(r"respeak-[a-z-]+\.(?:sh|py)", read(SKILL)):
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, "scripts", name)), name)

    def test_the_agent_is_named_and_holds_each_mode(self):
        text = read(AGENT)
        self.assertIn("name: respeak\n", frontmatter(text))
        for mode in MODES:
            self.assertIn("- **%s**:" % mode, text)
            self.assertIn(mode, read(SKILL))

    def test_nothing_ships_the_lane_that_left(self):
        words = re.compile(r"lexicon|shorthand|digest|machine lane|swarm", re.I)
        for path in (SKILL, AGENT, os.path.join(PLUGIN, "config", "include.md.tmpl"),
                     os.path.join(PLUGIN, "config", "respeak.config.yaml")):
            hit = words.search(read(path))
            self.assertIsNone(hit and hit.group(0), path)


if __name__ == "__main__":
    unittest.main()
