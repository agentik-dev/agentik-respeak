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
        answer = " ".join(read(SKILL).split("**The answer.**", 1)[1].split())
        for word in ("marker line", "`gate:`", "`config:`", "report"):
            self.assertIn(word, answer)
        self.assertIn("A file holds the narrative alone", answer)
        contract = " ".join(read(AGENT).split("## Output contract", 1)[1].split())
        self.assertIn("A file the caller asks for holds the narrative alone", contract)
        for word in ("marker line", "`gate:`", "`config:`"):
            self.assertIn(word, contract)
        script = read(os.path.join(PLUGIN, "scripts", "respeak-render.sh"))
        self.assertIn("config: approximated from files (no resolved block)", " ".join(read(AGENT).split()))
        self.assertIn(r"config: approximated from files \(no resolved block\)", script)

    def test_a_contracts_render_names_the_agent(self):
        # 0.11.0 handed the render to the agent and passed under agentik-relay's
        # `--allowedTools 'Read Write' --max-turns 8`, whose cap a subagent's turns do not
        # spend; working inline hit it at 9 turns (r19 amendment 3).
        page = " ".join(read(SKILL).split())
        render = page.split("**The render.**", 1)[1].split("**The check.**", 1)[0]
        handed, refused = render.split("Only where the Agent tool is refused", 1)
        self.assertIn("Hand every render to the `respeak:respeak` agent, a contract's too", handed)
        for word in ("the source", "the contract text", "the path it names", "The agent writes that file"):
            self.assertIn(word, handed)
        self.assertNotIn("no try at the agent", page)
        self.assertNotIn("seven turns", page)
        # a denied tool costs one turn, never a second
        self.assertIn("A denied tool is never retried", page)

    def test_a_refused_agent_takes_the_short_read_and_write_path(self):
        page = " ".join(read(SKILL).split())
        path = page.split("Only where the Agent tool is refused", 1)[1].split("**The check.**", 1)[0]
        self.assertEqual(re.findall(r"\((\d)\) ", path), ["1", "2", "3"])
        self.assertIn("in one message, Read the source, the file the contract names", path)
        for name in ("agents/respeak.md", "config/respeak.config.yaml", "corpus/banned-phrases.yaml",
                     "corpus/replacements.yaml", "corpus/style/tone-mapping.md"):
            self.assertIn(name, path)
            self.assertTrue(os.path.isfile(os.path.join(PLUGIN, name)), name)
        for rule in ("read nothing after it", "Write the file once", "one short line",
                     "no second rewrite", "no measure and no verifier"):
            self.assertIn(rule, path)

    def test_nothing_ships_the_lane_that_left(self):
        words = re.compile(r"lexicon|shorthand|digest|machine lane|swarm", re.I)
        for path in (SKILL, AGENT, os.path.join(PLUGIN, "config", "include.md.tmpl"),
                     os.path.join(PLUGIN, "config", "respeak.config.yaml")):
            hit = words.search(read(path))
            self.assertIsNone(hit and hit.group(0), path)


if __name__ == "__main__":
    unittest.main()
