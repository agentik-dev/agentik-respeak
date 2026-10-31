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

    def test_a_rendered_file_holds_the_narrative_alone(self):
        # The agent's reply carries a marker and closing lines for its caller. A file holds
        # none of them, whether the script, the agent or the skill's own turn writes it. A
        # fake runner pins the script in tests/test_render.sh; these two are prose a model reads.
        answer = read(SKILL).split("**The answer.**", 1)[1]
        for word in ("marker line", "`gate:`", "`config:`", "report"):
            self.assertIn(word, answer)
        self.assertIn("write the narrative alone there", " ".join(answer.split()))
        contract = " ".join(read(AGENT).split("## Output contract", 1)[1].split())
        self.assertIn("A file the caller asks for holds the narrative alone", contract)
        for word in ("marker line", "`gate:`", "`config:`"):
            self.assertIn(word, contract)
        script = read(os.path.join(PLUGIN, "scripts", "respeak-render.sh"))
        self.assertIn("config: approximated from files (no resolved block)", " ".join(read(AGENT).split()))
        self.assertIn(r"config: approximated from files \(no resolved block\)", script)

    def test_the_serial_render_fits_a_callers_max_turns(self):
        # agentik-relay's `make readme` runs the skill under `--allowedTools 'Read Write'
        # --max-turns 8`. The text's own count is what can be pinned; what a model spends
        # needs a real run.
        render = " ".join(read(SKILL).split("**The render.**", 1)[1].split("**The check.**", 1)[0].split())
        self.assertIn("in seven turns", render)
        self.assertIn("in one message", render)
        self.assertIn("with no try at the agent", render)
        turns = []
        for first, last in re.findall(r"\((\d)(?:-(\d))?\) ", render):
            turns += range(int(first), int(last or first) + 1)
        self.assertEqual(turns, list(range(1, 8)))
        self.assertLess(len(turns), 8)
        for name in ("agents/respeak.md", "banned-phrases.yaml", "replacements.yaml", "style/tone-mapping.md"):
            self.assertIn(name, render)
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, name if name.startswith("agents") else "corpus/" + name)), name)

    def test_nothing_ships_the_lane_that_left(self):
        words = re.compile(r"lexicon|shorthand|digest|machine lane|swarm", re.I)
        for path in (SKILL, AGENT, os.path.join(PLUGIN, "config", "include.md.tmpl"),
                     os.path.join(PLUGIN, "config", "respeak.config.yaml")):
            hit = words.search(read(path))
            self.assertIsNone(hit and hit.group(0), path)


if __name__ == "__main__":
    unittest.main()
