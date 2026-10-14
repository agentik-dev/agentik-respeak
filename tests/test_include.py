"""Tests for /respeak:include: plugin/scripts/respeak-include.py and its template.

The script renders a repo's static include file from the plugin defaults and
the repo's tracked .claude/respeak/config.yaml only (design/include-r1.md).
Each case copies the fixture examples/layered/project/ into a temp git repo
and runs the script there. Exits: `write` 0 written, 2 usage or over the cap;
`check` 0 current, 1 drift, 2 usage.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(REPO, "plugin")
SCRIPT = os.path.join(PLUGIN, "scripts", "respeak-include.py")
PY_WRAPPER = os.path.join(PLUGIN, "scripts", "py")
OLD_WRAPPER = os.path.join(PLUGIN, "scripts", "respeak-py.sh")
TEMPLATE = os.path.join(PLUGIN, "config", "include.md.tmpl")
SKILL = os.path.join(PLUGIN, "skills", "respeak", "SKILL.md")
INIT_SKILL = os.path.join(PLUGIN, "skills", "init", "SKILL.md")
AGENT = os.path.join(PLUGIN, "agents", "respeak.md")
FIXTURE = os.path.join(REPO, "examples", "layered", "project")
HYGIENE = os.path.join(REPO, "scripts", "hygiene")
OUT_REL = os.path.join(".claude", "respeak", "include.md")
CFG_REL = os.path.join(".claude", "respeak", "config.yaml")
LEX_REL = os.path.join(".claude", "respeak", "lexicon-active.md")
CAP = 1500
STAMP_RE = re.compile(r"^<!-- respeak include v[0-9]+, inputs [0-9a-f]{8}; "
                      r"regenerate with /respeak:include, do not edit -->$")


def flat(data):
    """The text with every run of whitespace one space: the render wraps at 76."""
    return " ".join(data.decode("utf-8").split())


def template_modes():
    with open(TEMPLATE) as f:
        return [m.group(1) for m in re.finditer(r"^@@ mode (\S+)\s*$", f.read(), re.M)]


def init_step(n):
    """The text of /respeak:init's numbered step n."""
    with open(INIT_SKILL) as f:
        m = re.search(r"^%d\. (.*?)(?=^\d+\. |\Z)" % n, f.read(), re.M | re.S)
    return m.group(1) if m else ""


def skill_modes():
    with open(SKILL) as f:
        hint = re.search(r'^argument-hint: "\[([^\]]+)\]', f.read(), re.M)
    return hint.group(1).split("|") if hint else []


class Repo:
    """The fixture copied into a temp git repo, its project config tracked,
    under a temp HOME whose personal layers say eli5."""

    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="respeak-include-"))
        self.home = os.path.join(self.root, "home")
        self.repo = os.path.join(self.root, "repo")
        shutil.copytree(FIXTURE, self.repo)
        os.makedirs(os.path.join(self.home, ".claude", "respeak"))
        with open(os.path.join(self.home, ".claude", "respeak", "config.yaml"), "w") as f:
            f.write("narrative: { default_mode: eli5, profile: exec }\n")
        env_cfg = os.path.join(self.root, "env.yaml")
        with open(env_cfg, "w") as f:
            f.write("narrative: { default_mode: bluf }\n")
        self.env = dict(os.environ)
        self.env.update({
            "HOME": self.home,
            "CLAUDE_CONFIG_DIR": os.path.join(self.home, ".claude"),
            "RESPEAK_CONFIG": env_cfg,
            "CLAUDE_PLUGIN_OPTION_DEFAULT_MODE": "eli5",
            "GIT_CONFIG_NOSYSTEM": "1",
        })
        self.git("init", "-q")
        self.git("add", CFG_REL)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env=self.env, check=True,
                       stdout=subprocess.DEVNULL)

    def run(self, *args, cwd=None, wrapper=False):
        argv = ([PY_WRAPPER, "respeak-include.py"] if wrapper
                else [sys.executable, SCRIPT]) + list(args)
        return subprocess.run(argv, cwd=cwd or self.repo, env=self.env, text=True,
                              capture_output=True, stdin=subprocess.DEVNULL, timeout=60)

    def path(self, rel):
        return os.path.join(self.repo, rel)

    def read(self, rel=OUT_REL):
        with open(self.path(rel), "rb") as f:
            return f.read()

    def commit(self):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                        "commit", "-q", "-m", "fixture"], cwd=self.repo, env=self.env,
                       check=True, stdout=subprocess.DEVNULL)

    def set_config(self, text, track=True):
        with open(self.path(CFG_REL), "w") as f:
            f.write(text)
        if track:
            self.git("add", CFG_REL)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.r = Repo()
        self.addCleanup(self.r.cleanup)

    def assertExit(self, proc, code):
        self.assertEqual(proc.returncode, code,
                         "exit %d, want %d\nstdout: %s\nstderr: %s"
                         % (proc.returncode, code, proc.stdout, proc.stderr))


class TemplateAgainstSkill(unittest.TestCase):
    def test_template_modes_are_the_skill_modes(self):
        # §4: the template's mode names equal the argument-hint modes
        self.assertTrue(os.path.isfile(TEMPLATE), "no template at plugin/config/include.md.tmpl")
        self.assertEqual(sorted(template_modes()), sorted(skill_modes()))
        self.assertEqual(sorted(skill_modes()), ["bluf", "eli5", "technical"])


class WriteAndCheck(Base):
    def test_fixture_renders_under_cap_with_stamp(self):
        p = self.r.run("write", wrapper=True)
        self.assertExit(p, 0)
        data = self.r.read()
        self.assertLessEqual(len(data), CAP)
        self.assertRegex(data.decode("utf-8").splitlines()[0], STAMP_RE)
        text = flat(data)
        self.assertIn("# How to write in this repo", text)
        self.assertIn("`**/*.md`", text)  # gate.include names the human lane

    def test_write_then_check_is_current_and_gate_include_edit_drifts(self):
        self.assertExit(self.r.run("write"), 0)
        self.assertExit(self.r.run("check", wrapper=True), 0)
        self.r.set_config("version: 3\nnarrative: { default_mode: technical }\n"
                          "gate: { include: [README.md, docs/] }\n")
        p = self.r.run("check")
        self.assertExit(p, 1)
        self.assertIn("stale", p.stdout + p.stderr)
        self.assertExit(self.r.run("write"), 0)
        text = flat(self.r.read())
        self.assertIn("`README.md` and `docs/`", text)
        self.assertExit(self.r.run("check"), 0)

    def test_hand_edit_is_told_from_stale(self):
        self.assertExit(self.r.run("write"), 0)
        with open(self.r.path(OUT_REL), "ab") as f:
            f.write(b"one more rule\n")
        p = self.r.run("check")
        self.assertExit(p, 1)
        self.assertIn("hand-edited", p.stdout + p.stderr)

    def test_absent_file_is_drift(self):
        p = self.r.run("check")
        self.assertExit(p, 1)
        self.assertFalse(os.path.exists(self.r.path(OUT_REL)))

    def test_over_cap_write_exits_2_and_writes_nothing(self):
        many = ", ".join("docs/section-%03d/very/long/path/name/" % i for i in range(60))
        self.r.set_config("version: 3\ngate: { include: [%s] }\n" % many)
        p = self.r.run("write")
        self.assertExit(p, 2)
        self.assertIn("1,500", p.stdout + p.stderr)
        self.assertFalse(os.path.exists(self.r.path(OUT_REL)))
        self.assertExit(self.r.run("check"), 2)

    def test_out_outside_git_root_exits_2(self):
        outside = os.path.join(self.r.root, "elsewhere.md")
        for verb in ("write", "check"):
            p = self.r.run(verb, "--out", outside)
            self.assertExit(p, 2)
            self.assertIn("outside the git root", p.stderr)
        p = self.r.run("write", "--out", os.path.join("..", "up.md"))
        self.assertExit(p, 2)
        self.assertFalse(os.path.exists(outside))
        self.assertFalse(os.path.exists(os.path.join(self.r.root, "up.md")))

    def test_out_inside_root_is_the_authors_choice(self):
        os.makedirs(self.r.path("plugin"))
        self.assertExit(self.r.run("write", "--out", "plugin/include.md"), 0)
        self.assertExit(self.r.run("check", "--out", "plugin/include.md"), 0)
        self.assertFalse(os.path.exists(self.r.path(OUT_REL)))

    def test_outside_a_git_work_tree_exits_2(self):
        bare = os.path.join(self.r.root, "plain")
        os.makedirs(bare)
        for verb in ("check", "write"):
            p = self.r.run(verb, cwd=bare)
            self.assertExit(p, 2)
            self.assertIn("not inside a git work tree", p.stderr)

    def test_usage_errors_exit_2(self):
        for args in ((), ("render",), ("write", "--out")):
            p = self.r.run(*args)
            self.assertExit(p, 2)
            self.assertIn("usage:", p.stderr)


class OutRefusals(Base):
    """`--out` never reaches a `.git` or `~/.claude`, in any spelling: a
    case-insensitive disk reads `.GIT` as `.git`, `.CLAUDE` as `.claude`."""

    def git_init(self, where):
        subprocess.run(["git", "init", "-q"], cwd=where, env=self.r.env, check=True,
                       stdout=subprocess.DEVNULL)

    def test_git_dir_in_any_case_and_at_any_depth_is_refused(self):
        nested = self.r.path("sub")
        os.makedirs(nested)
        self.git_init(nested)
        for cfg, outs in ((self.r.path(os.path.join(".git", "config")),
                           (".GIT/config", ".Git/config", ".git/config")),
                          (os.path.join(nested, ".git", "config"),
                           ("sub/.git/config", "sub/.GIT/config"))):
            with open(cfg, "rb") as f:
                before = f.read()
            for out in outs:
                for verb in ("write", "check"):
                    p = self.r.run(verb, "--out", out)
                    self.assertExit(p, 2)
                    self.assertIn("inside .git", p.stderr)
                with open(cfg, "rb") as f:
                    self.assertEqual(f.read(), before, out)
        # A nested repo whose `.git` is a symlink to a sibling directory: the
        # resolved path holds no `.git` part, the path as given does.
        linked = self.r.path("sub2")
        os.makedirs(linked)
        self.git_init(linked)
        os.rename(os.path.join(linked, ".git"), self.r.path("gitdata"))
        os.symlink(os.path.join("..", "gitdata"), os.path.join(linked, ".git"))
        cfg = self.r.path(os.path.join("gitdata", "config"))
        with open(cfg, "rb") as f:
            before = f.read()
        for out in ("sub2/.git/config", "sub2/.GIT/config"):
            for verb in ("write", "check"):
                p = self.r.run(verb, "--out", out)
                self.assertExit(p, 2)
                self.assertIn("inside .git", p.stderr)
            with open(cfg, "rb") as f:
                self.assertEqual(f.read(), before, out)

    def home_repo(self):
        """HOME a git work tree, with a CLAUDE.md under its ~/.claude."""
        self.git_init(self.r.home)
        target = os.path.join(self.r.home, ".claude", "CLAUDE.md")
        with open(target, "w") as f:
            f.write("keep\n")
        return target

    def test_claude_home_in_any_spelling_is_refused(self):
        target = self.home_repo()
        for out in (".claude/CLAUDE.md", ".CLAUDE/CLAUDE.md", ".Claude/respeak/include.md",
                    "x/../.CLAUDE/new.md"):
            for verb in ("write", "check"):
                p = self.r.run(verb, "--out", out, cwd=self.r.home)
                self.assertExit(p, 2)
                self.assertIn("under ~/.claude", p.stderr)
        with open(target) as f:
            self.assertEqual(f.read(), "keep\n")
        for name in ("new.md", os.path.join("respeak", "include.md")):
            self.assertFalse(os.path.exists(os.path.join(self.r.home, ".claude", name)))

    def test_default_path_refusal_names_the_path(self):
        # in HOME's repo the default output is ~/.claude/respeak/include.md
        self.home_repo()
        default = os.path.join(self.r.home, OUT_REL)
        for verb in ("write", "check"):
            p = self.r.run(verb, cwd=self.r.home)
            self.assertExit(p, 2)
            self.assertNotIn("None", p.stderr)
            self.assertIn("output %s is under ~/.claude" % default, p.stderr)
        self.assertFalse(os.path.exists(default))


class OsErrors(Base):
    """An OS error means the task could not run: one line, exit 2, no
    traceback, and never check's 1, which means drift (portfolio entry 25)."""

    def assertOneLine2(self, p):
        self.assertExit(p, 2)
        self.assertNotIn("Traceback", p.stderr)
        self.assertEqual(len(p.stderr.strip().splitlines()), 1, p.stderr)

    def test_write_under_a_file_exits_2(self):
        self.assertOneLine2(self.r.run("write", "--out", "README.md/x.md"))
        self.assertTrue(os.path.isfile(self.r.path("README.md")))

    @unittest.skipIf(os.geteuid() == 0, "root reads a mode-000 file")
    def test_check_of_an_unreadable_file_exits_2(self):
        self.assertExit(self.r.run("write"), 0)
        os.chmod(self.r.path(OUT_REL), 0)
        self.addCleanup(os.chmod, self.r.path(OUT_REL), 0o644)
        self.assertOneLine2(self.r.run("check"))


class OnlyTrackedLayers(Base):
    def test_personal_layers_never_reach_the_file(self):
        # the temp HOME, RESPEAK_CONFIG, userConfig and config.local.yaml all
        # move the mode; the shipped file keeps the tracked config's technical
        with open(self.r.path(os.path.join(".claude", "respeak", "config.local.yaml")), "w") as f:
            f.write("narrative: { default_mode: eli5 }\n")
        self.assertExit(self.r.run("write"), 0)
        text = flat(self.r.read())
        self.assertIn("in technical mode", text)
        self.assertNotIn("in eli5 mode", text)
        self.assertNotIn("in bluf mode", text)

    def test_tracked_mode_and_profile_are_read(self):
        self.r.set_config("version: 3\nnarrative: { profile: exec }\n")
        self.assertExit(self.r.run("write"), 0)
        text = flat(self.r.read())
        self.assertIn("in bluf mode", text)
        self.assertIn("- technical (", text)
        self.assertIn("- eli5 (", text)
        self.assertNotIn("- bluf (", text)

    def test_untracked_config_is_not_read(self):
        self.r.git("rm", "-q", "--cached", CFG_REL)
        self.r.set_config("version: 3\nnarrative: { default_mode: bluf }\n", track=False)
        p = self.r.run("write")
        self.assertExit(p, 0)
        self.assertIn("not tracked", p.stderr)
        self.assertIn("in technical mode", flat(self.r.read()))

    def test_tracked_symlink_config_is_refused(self):
        # committed as a symlink (mode 120000) to the user layer, which says eli5
        user = os.path.join(self.r.home, ".claude", "respeak", "config.yaml")
        os.unlink(self.r.path(CFG_REL))
        os.symlink(user, self.r.path(CFG_REL))
        self.r.git("add", CFG_REL)
        for verb in ("write", "check"):
            p = self.r.run(verb)
            self.assertExit(p, 2)
            self.assertIn("symlink", p.stderr)
        self.assertFalse(os.path.exists(self.r.path(OUT_REL)))

    def test_config_reached_through_a_symlinked_dir_is_refused(self):
        # the index holds a regular file, but the work tree's directory
        # is a symlink to the user layer's
        shutil.rmtree(self.r.path(os.path.join(".claude", "respeak")))
        os.symlink(os.path.join(self.r.home, ".claude", "respeak"),
                   self.r.path(os.path.join(".claude", "respeak")))
        for verb in ("write", "check"):
            p = self.r.run(verb, "--out", "include.md")
            self.assertExit(p, 2)
            self.assertIn("outside the git root", p.stderr)
        self.assertFalse(os.path.exists(self.r.path("include.md")))

    def test_lexicon_counts_only_when_tracked(self):
        self.assertExit(self.r.run("write"), 0)
        self.assertNotIn("lexicon-active.md", flat(self.r.read()))
        lex = ".claude/respeak/lexicon-active.md"
        with open(self.r.path(lex), "w") as f:
            f.write("# digest\n")
        # untracked, then gitignored: consumers never get it, so it counts for nothing
        self.assertExit(self.r.run("check"), 0)
        with open(self.r.path(".gitignore"), "a") as f:
            f.write("/%s\n" % lex)
        self.assertExit(self.r.run("check"), 0)
        self.r.git("add", "-f", lex)
        self.assertExit(self.r.run("check"), 1)
        self.assertExit(self.r.run("write"), 0)
        self.assertIn("`.claude/respeak/lexicon-active.md`", flat(self.r.read()))


class Hygiene(Base):
    def test_rendered_fixture_has_no_hit_outside_the_allowlist(self):
        self.assertExit(self.r.run("write"), 0)
        scan = os.path.join(self.r.root, "scan")
        os.makedirs(os.path.join(scan, ".claude", "respeak"))
        shutil.copy(self.r.path(OUT_REL), os.path.join(scan, OUT_REL))
        subprocess.run(["git", "init", "-q"], cwd=scan, env=self.r.env, check=True)
        allow = os.path.join(self.r.root, "allow")
        with open(allow, "w") as f:
            f.write(".claude/respeak/include.md: sibling\n")  # §3: the consumer's line
        p = subprocess.run([sys.executable, HYGIENE, "--repo", scan, "--allow", allow],
                           env=self.r.env, text=True, capture_output=True, timeout=60)
        self.assertExit(p, 0)


class DoneClaimRule(Base):
    """r2: in the human lane, a claim that work is done, fixed, passing or green
    is fact only beside the tool result that shows it; else it reads as claimed
    and not verified, with what would verify it. The study behind the rule is
    cited in research/synthesis/design-principles.md, never in the prompt."""

    def test_the_translator_carries_the_rule(self):
        with open(AGENT, encoding="utf-8") as f:
            text = flat(f.read().encode("utf-8"))
        for phrase in ("done, fixed, passing or green", "tool result",
                       "a test count, an exit code, a gate line, a commit",
                       "claimed and not verified", "what would verify it"):
            self.assertTrue(phrase in text, "plugin/agents/respeak.md lacks %r" % phrase)
        # an editorial pass names the claim; it never rewords the record
        self.assertTrue("editorial pass, leave the claim as written" in text,
                        "plugin/agents/respeak.md lets an editorial pass reword the claim")
        cite = re.search(r"(?i)advani|arxiv|75\.8", text)
        self.assertIsNone(cite and cite.group(0), "the study is cited in the prompt")

    def test_the_rendered_include_carries_the_rule(self):
        self.assertExit(self.r.run("write"), 0)
        data = self.r.read()
        self.assertLessEqual(len(data), CAP)
        text = flat(data)
        rule = ("Done, fixed, passing or green needs a tool result that shows it; "
                "else say claimed, not verified, and what would verify it.")
        self.assertTrue(rule in text, "the include lacks the rule:\n" + text)


class Propose(unittest.TestCase):
    """`propose [--root R]` prints the gate.include list built from the
    human-lane files present at R, one YAML flow list on one line."""

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="respeak-propose-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True,
                       stdout=subprocess.DEVNULL)

    def touch(self, rel):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("# t\n")

    def propose(self, *args, cwd=None):
        return subprocess.run([sys.executable, SCRIPT, "propose"] + list(args),
                              cwd=cwd or self.repo, text=True, capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=60)

    def assertList(self, p, want):
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(len(p.stdout.splitlines()), 1, p.stdout)
        import yaml
        self.assertEqual(yaml.safe_load(p.stdout), want)

    def test_propose_lists_present_human_lane(self):
        for rel in ("DECISIONS.md", "docs/a.md", "README.md", "notes.md", "design/x.md",
                    "design/readme/source.txt"):
            self.touch(rel)
        os.makedirs(os.path.join(self.repo, "plugin", "docs"))  # empty: its glob matches nothing
        self.assertList(self.propose(), ["README.md", "DECISIONS.md", "docs/**/*.md"])

    def test_propose_lists_every_entry_in_order(self):
        rels = ["HANDOFF.md", "plugin/docs/p/q.md", "OPEN-QUESTIONS.md", "design/readme/source.md",
                "NICE_TO_HAVE.md", "DESIGN.md", "docs/a.md", "DECISIONS.md", "CHANGELOG.md",
                "README.md"]
        for rel in rels:
            self.touch(rel)
        self.assertList(self.propose(), [
            "README.md", "CHANGELOG.md", "DECISIONS.md", "DESIGN.md", "NICE_TO_HAVE.md",
            "OPEN-QUESTIONS.md", "HANDOFF.md", "docs/**/*.md", "design/readme/**/*.md",
            "plugin/docs/**/*.md"])

    def test_propose_counts_names_as_spelled_on_disk(self):
        # B2: on a case-insensitive disk `Docs/` answers to `docs/`, but the gate's
        # globs are case-sensitive; presence is the name os.listdir returns
        for rel in ("Docs/a.md", "readme.md", "Design/readme/x.md", "design/Readme/y.md",
                    "plugin/Docs/z.md"):
            self.touch(rel)
        self.assertList(self.propose(), ["**/*.md"])
        self.touch("docs/b.md")  # a second, lower-case docs/ only where the disk allows it
        names = os.listdir(self.repo)
        want = ["docs/**/*.md"] if "docs" in names else ["**/*.md"]
        self.assertList(self.propose(), want)

    def test_propose_empty_falls_back(self):
        self.touch("src/readme.txt")
        p = self.propose()
        self.assertList(p, ["**/*.md"])
        self.assertEqual(p.stdout.strip(), '["**/*.md"]')

    def test_propose_root_flag_and_outside_git(self):
        self.touch("README.md")
        self.assertList(self.propose("--root", self.repo, cwd=self.root), ["README.md"])
        plain = os.path.join(self.root, "plain")
        os.makedirs(plain)
        p = self.propose("--root", plain)
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("not inside a git work tree", p.stderr)
        self.assertEqual(p.stdout, "")


class UncommittedSources(Base):
    """`write` names each tracked source it rendered from that differs from
    HEAD on stderr, and still exits 0."""

    def note(self, rel):
        return ("respeak-include: %s has uncommitted changes; commit it with the include, "
                "or check reports stale" % rel)

    def test_write_warns_uncommitted_config(self):
        self.r.commit()
        with open(self.r.path(CFG_REL), "a") as f:
            f.write("# an edit not yet committed\n")
        p = self.r.run("write")
        self.assertExit(p, 0)
        self.assertIn(self.note(".claude/respeak/config.yaml"), p.stderr.splitlines())
        self.assertNotIn("lexicon-active.md", p.stderr)

    def test_write_warns_staged_only_config_and_uncommitted_lexicon(self):
        # the setUp stages the config and never commits: it differs from HEAD
        with open(self.r.path(LEX_REL), "w") as f:
            f.write("# digest\n")
        self.r.git("add", "-f", LEX_REL)
        p = self.r.run("write")
        self.assertExit(p, 0)
        lines = p.stderr.splitlines()
        self.assertIn(self.note(".claude/respeak/config.yaml"), lines)
        self.assertIn(self.note(".claude/respeak/lexicon-active.md"), lines)

    def test_write_quiet_when_committed(self):
        with open(self.r.path(LEX_REL), "w") as f:
            f.write("# digest\n")
        self.r.git("add", "-f", LEX_REL)
        self.r.commit()
        p = self.r.run("write")
        self.assertExit(p, 0)
        self.assertNotIn("uncommitted", p.stderr)
        # an untracked config is not a source: the existing note names it, this one does not
        self.r.git("rm", "-q", "--cached", CFG_REL)
        p = self.r.run("write")
        self.assertExit(p, 0)
        self.assertNotIn("uncommitted", p.stderr)

    def test_check_never_warns(self):
        with open(self.r.path(CFG_REL), "a") as f:
            f.write("# an edit not yet committed\n")
        self.assertNotIn("uncommitted", self.r.run("check").stderr)


class InitSkill(Base):
    """/respeak:init's step 6, run the way the skill says, in the fixture."""

    def test_init_stages_the_digest_with_the_config(self):
        # B1: step 3 always writes the digest; the include must render from what
        # the author commits, so init's staging command adds it with the config
        step = init_step(6)
        adds = re.findall(r"`(git add [^`]+)`", step)
        self.assertEqual(len(adds), 1, step)
        with open(self.r.path(LEX_REL), "w") as f:
            f.write("# digest\n")
        self.r.git(*adds[0].split()[1:])
        self.assertExit(self.r.run("write"), 0)
        self.r.git("add", CFG_REL, LEX_REL, OUT_REL)  # the author commits what init made
        self.r.commit()
        self.assertExit(self.r.run("check"), 0)
        self.assertIn("`.claude/respeak/lexicon-active.md`", flat(self.r.read()))

    def test_init_writes_the_include_only_at_the_git_toplevel(self):
        # B3: write reads and writes at the git root, so in a project below it
        # the include would land beside the root's config and the offered
        # @.claude/respeak/include.md would point at nothing
        nested = self.r.path("pkg")
        os.makedirs(os.path.join(nested, ".claude", "respeak"))
        self.assertExit(self.r.run("write", cwd=nested), 0)
        self.assertTrue(os.path.isfile(self.r.path(OUT_REL)))
        self.assertFalse(os.path.exists(os.path.join(nested, OUT_REL)))
        step = flat(init_step(6).encode("utf-8"))
        self.assertIn("`git rev-parse --show-toplevel`", step)
        self.assertRegex(step, r"[Ss]kip both")
        self.assertIn("@.claude/respeak/include.md", step)


class Wrapper(unittest.TestCase):
    """scripts/py is the wrapper's name (portfolio entry 26); respeak-py.sh
    stays for callers outside this repo."""

    def test_py_is_executable(self):
        self.assertTrue(os.path.isfile(PY_WRAPPER), "no plugin/scripts/py")
        self.assertTrue(os.access(PY_WRAPPER, os.X_OK), "plugin/scripts/py is not executable")

    def test_respeak_py_sh_still_runs_a_script(self):
        p = subprocess.run(["bash", OLD_WRAPPER, "respeak-measure.py", "--help"], text=True,
                           capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_respeak_py_sh_needs_no_bash_on_path(self):
        # N6: it execs py by its path, so a PATH without bash still runs it; RESPEAK_PYTHON
        # names this interpreter, since /usr/bin's python3 has no PyYAML under a temp HOME
        env = dict(os.environ, PATH="/usr/bin", RESPEAK_PYTHON=sys.executable)
        p = subprocess.run(["/bin/bash", OLD_WRAPPER, "respeak-measure.py", "--help"], env=env,
                           text=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        p = subprocess.run(["/bin/bash", OLD_WRAPPER], env=env, text=True, capture_output=True,
                           stdin=subprocess.DEVNULL, timeout=60)
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn("usage: respeak-py.sh ", p.stderr)

    def test_respeak_py_sh_is_one_exec_of_py(self):
        with open(OLD_WRAPPER) as f:
            code = [l for l in f.read().splitlines() if l.strip() and not l.lstrip().startswith("#")]
        self.assertEqual(len(code), 1, code)
        self.assertIn("exec ", code[0])
        self.assertIn("/py", code[0])
        self.assertNotIn("exec bash", code[0])


if __name__ == "__main__":
    unittest.main()
