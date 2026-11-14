"""Tests for plugin/bin/agentik-respeak and plugin/scripts/respeak-plug.py (packet ak9-plug-respeak).

The launcher is the suite's way in: `describe --json`, `describe config --json [KEY]` and
`doctor --json` print one JSON object each, in the shapes of the suite's plug contract. Every
test runs the worktree's launcher in a temp HOME (the XDG folders under it, CLAUDE_CONFIG_DIR
unset) with a temp folder as the cwd, and RESPEAK_PYTHON naming this interpreter, which has
PyYAML. No test reads the live state or runs the real `claude`.

Run: python3 -m unittest tests.test_plug -v
"""
import contextlib
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
PLUGIN = os.path.join(REPO, "plugin")
LAUNCHER = os.path.join(PLUGIN, "bin", "agentik-respeak")
PLUG = os.path.join(PLUGIN, "scripts", "respeak-plug.py")
RESOLVER = os.path.join(PLUGIN, "scripts", "respeak-config.py")
WRAPPER = os.path.join(PLUGIN, "scripts", "respeak-config.sh")
DOCTOR = os.path.join(PLUGIN, "scripts", "respeak-doctor.sh")
SHIPPED = os.path.realpath(os.path.join(PLUGIN, "config", "respeak.config.yaml"))
MANIFEST = os.path.join(PLUGIN, ".claude-plugin", "plugin.json")
PY = sys.executable

DESCRIBE_KEYS = {"schema", "ok", "tool", "version", "summary", "repo", "plugin", "needs", "verbs", "reads"}
SETTING_KEYS = {"key", "value", "default", "type", "choices", "summary", "source", "change", "live", "values"}
CHANGE_KEYS = {"kind", "command", "path", "block", "note"}
WARNING_KEYS = {"key", "reason", "value", "path", "line"}
LAYER_KEYS = {"name", "path", "present", "travels"}
MARKET_REMEDY = "claude plugin marketplace add agentik-dev/agentik-commons"

STUB = """#!/bin/sh
case "$*" in
  "--version") echo "9.9.9 (Claude Code)" ;;
  "plugin marketplace list --json") echo '%s' ;;
  "plugin list --json") echo '%s' ;;
  *) exit 1 ;;
esac
"""
KNOWN_MARKET = '[{"name":"agentik","source":"github","repo":"agentik-dev/agentik-commons"}]'
KNOWN_PLUGINS = '[{"id":"respeak@agentik","version":"0.6.0","scope":"user"}]'
# A fork's install of this very folder, from the made-up marketplace acme-tools.
FORK_PLUGINS = ('[{"id":"respeak@acme-tools","version":"0.12.6-acme.1","scope":"user","installPath":"%s"}]'
                % PLUGIN)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = old
    return mod


def leaves(d, prefix=""):
    for k, v in d.items():
        key = "%s.%s" % (prefix, k) if prefix else str(k)
        if isinstance(v, dict) and v:
            yield from leaves(v, key)
        else:
            yield key, v


class Box:
    """A temp HOME, its XDG folders, a project folder as the cwd."""

    def __init__(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="respeak-plug-"))
        self.home = os.path.join(self.root, "home")
        self.proj = os.path.join(self.root, "proj")
        self.bin = os.path.join(self.root, "bin")
        for d in (self.home, self.proj, self.bin):
            os.makedirs(d)
        self.cache = os.path.join(self.home, ".cache")
        self.user_file = os.path.join(self.home, ".claude", "respeak", "config.yaml")
        self.project_file = os.path.join(self.proj, ".claude", "respeak", "config.yaml")

    def env(self, **extra):
        e = {"HOME": self.home, "PATH": "/usr/bin:/bin", "TERM": "dumb", "RESPEAK_PYTHON": PY,
             "XDG_CACHE_HOME": self.cache,
             "XDG_CONFIG_HOME": os.path.join(self.home, ".config"),
             "XDG_STATE_HOME": os.path.join(self.home, ".local", "state"),
             "XDG_DATA_HOME": os.path.join(self.home, ".local", "share")}
        e.update(extra)
        return e

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(text)
        return path

    def stub(self, market=KNOWN_MARKET, plugins=KNOWN_PLUGINS):
        path = os.path.join(self.bin, "claude")
        with open(path, "w") as f:
            f.write(STUB % (market, plugins))
        os.chmod(path, 0o755)
        return self.bin + ":/usr/bin:/bin"

    def run(self, *args, cwd=None, **extra):
        return subprocess.run([LAUNCHER] + list(args), cwd=cwd or self.proj, env=self.env(**extra),
                              stdin=subprocess.DEVNULL, capture_output=True, timeout=60)

    def json(self, *args, cwd=None, **extra):
        p = self.run(*args, cwd=cwd, **extra)
        return p, json.loads(p.stdout.decode("utf-8"))

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class Case(unittest.TestCase):
    def setUp(self):
        self.box = Box()
        self.addCleanup(self.box.cleanup)

    def config(self, *more, cwd=None):
        p, obj = self.box.json("describe", "config", "--json", *more, cwd=cwd)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(obj["schema"], "agentik.config/1")
        self.assertIs(obj["ok"], True)
        return obj

    def setting(self, obj, key):
        rows = [s for s in obj["settings"] if s["key"] == key]
        self.assertEqual(len(rows), 1, key)
        return rows[0]

    def held(self, obj):
        """The contract's section 7, line 3: every key, every layer named."""
        names = {lay["name"] for lay in obj["layers"]}
        for lay in obj["layers"]:
            self.assertEqual(set(lay), LAYER_KEYS)
        for s in obj["settings"]:
            self.assertEqual(set(s), SETTING_KEYS, s["key"])
            self.assertEqual(set(s["change"]), CHANGE_KEYS, s["key"])
            self.assertEqual(s["change"]["kind"], "edit")
            self.assertIs(s["live"], True)
            self.assertIn(s["source"]["layer"], names, s["key"])
            for v in s["values"]:
                self.assertIn(v["layer"], names, s["key"])
        for w in obj["warnings"]:
            self.assertEqual(set(w), WARNING_KEYS)


class Describe(Case):
    """A1: describe --json, the bad words, --version and --help."""

    def test_describe_answers_every_key(self):
        p, obj = self.box.json("describe", "--json")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn(b"\x1b", p.stdout)
        self.assertEqual(set(obj), DESCRIBE_KEYS)
        self.assertEqual((obj["schema"], obj["ok"], obj["tool"]), ("agentik.describe/1", True, "respeak"))
        with open(MANIFEST) as f:
            self.assertEqual(obj["version"], json.load(f)["version"])
        self.assertLess(len(obj["summary"]), 80)
        self.assertIn({"name": "PyYAML", "kind": "package", "optional": False},
                      [{k: n[k] for k in ("name", "kind", "optional")} for n in obj["needs"]])
        self.assertIn(("claude", "program", True), [(n["name"], n["kind"], n["optional"]) for n in obj["needs"]])
        self.assertEqual([v["name"] for v in obj["verbs"]], ["describe", "doctor", "config"])
        self.assertFalse(any(v["top"] for v in obj["verbs"]))
        self.assertEqual(obj["reads"], [
            {"kind": "config", "name": "settings", "argv": ["describe", "config", "--json"]},
            {"kind": "doctor", "name": "doctor", "argv": ["doctor", "--json"]}])
        help_text = self.box.run("--help").stdout.decode()
        for v in obj["verbs"]:
            self.assertIn(v["summary"], help_text, v["name"])

    def test_describe_is_fast_once_cached(self):
        self.box.run("describe", "--json")
        t = time.monotonic()
        p = self.box.run("describe", "--json")
        self.assertEqual(p.returncode, 0)
        self.assertLess(time.monotonic() - t, 1.0)

    def test_bad_words_exit_2(self):
        for words in ([], ["nosuch"], ["describe"], ["describe", "nosuch", "--json"], ["doctor", "nosuch"]):
            p = self.box.run(*words)
            self.assertEqual(p.returncode, 2, words)
            self.assertEqual(p.stdout, b"", words)
            self.assertTrue(p.stderr, words)
        self.assertIn(b"describe --json", self.box.run("describe").stderr)

    def test_version_and_help(self):
        with open(MANIFEST) as f:
            version = json.load(f)["version"]
        p = self.box.run("--version")
        self.assertEqual((p.returncode, p.stdout.decode()), (0, "agentik-respeak %s\n" % version))
        for word in ("--help", "-h"):
            p = self.box.run(word)
            self.assertEqual(p.returncode, 0)
            self.assertIn("describe config --json", p.stdout.decode())


class Config(Case):
    """A2 to A7: the config read, its layers, sources, lines, changes and warnings."""

    def test_shipped_file_alone(self):
        obj = self.config()
        self.held(obj)
        rc = load("respeak_config_t", RESOLVER)
        with mock.patch.dict(os.environ, self.box.env(), clear=True):
            res = rc.resolve(target=self.box.proj)
        want = [k for k, _ in leaves(res.config) if k not in ("version", "schema")]
        self.assertEqual(sorted(s["key"] for s in obj["settings"]), sorted(want))
        self.assertEqual(len(obj["settings"]), 117)
        for s in obj["settings"]:
            self.assertEqual(s["value"], s["default"], s["key"])
            self.assertEqual(s["source"]["layer"], "default", s["key"])
            self.assertEqual(s["source"]["path"], SHIPPED, s["key"])
            self.assertIsInstance(s["source"]["line"], int, s["key"])
            self.assertFalse(s["source"]["path"].startswith(self.box.home + os.sep))
            self.assertLess(len(s["summary"]), 100, s["key"])
            self.assertTrue(s["summary"].endswith(".") and ". " not in s["summary"], s["key"])
            self.assertFalse(s["summary"].startswith("This setting"), s["key"])
        self.assertEqual(len({s["key"] for s in obj["settings"]}), len(obj["settings"]))
        mode = self.setting(obj, "narrative.default_mode")
        with open(SHIPPED) as f:
            line = next(i for i, l in enumerate(f, 1) if l.lstrip().startswith("default_mode: technical"))
        self.assertEqual((mode["value"], mode["source"]["line"]), ("technical", line))
        self.assertEqual(mode["choices"], ["eli5", "bluf", "technical"])
        self.assertEqual(self.setting(obj, "gate.fail_on")["choices"], ["none", "warn", "error"])
        self.assertEqual(obj["layers"][0], {"name": "default", "path": SHIPPED, "present": True, "travels": False})
        self.assertIn({"name": "install", "path": None, "present": False, "travels": False}, obj["layers"])
        self.assertIn({"name": "user", "path": self.box.user_file, "present": False, "travels": True}, obj["layers"])
        self.assertEqual(obj["warnings"], [])

    def test_user_file_at_line_2(self):
        self.box.write(self.box.user_file, "narrative:\n  tech_level: 2\n")
        obj = self.config()
        self.held(obj)
        s = self.setting(obj, "narrative.tech_level")
        self.assertEqual(s["value"], 2)
        self.assertEqual(s["source"], {"layer": "user", "path": self.box.user_file, "line": 2})
        self.assertEqual([v["layer"] for v in s["values"]], ["default", "user"])
        self.assertEqual(s["values"][-1]["value"], 2)
        self.assertEqual(s["change"]["path"], self.box.user_file)
        self.assertEqual(s["change"]["block"], "narrative:\n  tech_level: 2")
        self.assertIn("--set narrative.tech_level=VALUE", s["change"]["note"])
        user = [lay for lay in obj["layers"] if lay["name"] == "user"]
        self.assertEqual(user, [{"name": "user", "path": self.box.user_file, "present": True, "travels": True}])
        keyed = self.config("narrative.tech_level")
        self.assertEqual(keyed["settings"], [s])

    def test_project_profile_at_line_3(self):
        self.box.write(self.box.project_file, "# the project's tone\nnarrative:\n  profile: exec\n")
        obj = self.config()
        self.held(obj)
        s = self.setting(obj, "narrative.default_mode")
        self.assertEqual(s["value"], "bluf")
        self.assertEqual(s["source"], {"layer": "repo", "path": self.box.project_file, "line": 3})
        self.assertEqual(s["change"]["path"], self.box.project_file)
        self.assertIn({"name": "repo", "path": self.box.project_file, "present": True, "travels": False},
                      obj["layers"])

    def test_project_and_folder(self):
        self.box.write(self.box.project_file, "gate:\n  fail_on: warn\n")
        folder = self.box.write(os.path.join(self.box.proj, "docs", ".respeak.yaml"), "narrative:\n  tech_level: 1\n")
        obj = self.config(cwd=os.path.join(self.box.proj, "docs"))
        self.held(obj)
        fail_on = self.setting(obj, "gate.fail_on")
        self.assertEqual((fail_on["value"], fail_on["source"]),
                         ("warn", {"layer": "repo", "path": self.box.project_file, "line": 2}))
        tech = self.setting(obj, "narrative.tech_level")
        self.assertEqual((tech["value"], tech["source"]), (1, {"layer": "folder", "path": folder, "line": 2}))
        self.assertEqual(tech["values"][-1], {"layer": "folder", "value": 1, "path": folder, "line": 2})
        self.assertEqual(tech["change"]["path"], folder)
        folders = [lay for lay in obj["layers"] if lay["name"] == "folder"]
        self.assertEqual(folders, [{"name": "folder", "path": folder, "present": True, "travels": False}])

    def test_project_only_key_in_the_user_file(self):
        self.box.write(self.box.project_file, "narrative:\n  tone:\n    formality: 0.5\n")
        self.box.write(self.box.user_file, "gate:\n  enabled: true\n")
        obj = self.config()
        self.held(obj)
        s = self.setting(obj, "gate.enabled")
        self.assertIs(s["value"], False)
        self.assertEqual(s["source"]["layer"], "default")
        self.assertEqual(s["change"]["path"], self.box.project_file)
        self.assertEqual([v["layer"] for v in s["values"]], ["default"])
        self.assertEqual(obj["warnings"], [{"key": "gate.enabled", "reason": "ignored", "value": None,
                                            "path": self.box.user_file, "line": 2}])

    def test_keyed_reads_and_warnings(self):
        obj = self.config("narrative.tech_level")
        self.assertEqual([s["key"] for s in obj["settings"]], ["narrative.tech_level"])
        self.assertEqual(self.config("nosuch")["settings"], [])
        self.assertEqual(self.config("narrative")["settings"], [])
        self.box.write(self.box.user_file, "# mine\nnarative:\n  tech_level: 2\n")
        obj = self.config()
        self.assertEqual(obj["warnings"], [{"key": "narative", "reason": "unknown", "value": None,
                                            "path": self.box.user_file, "line": 2}])
        self.assertFalse([s for s in obj["settings"] if s["key"].startswith("narative")])
        self.box.write(self.box.user_file, "narrative:\n  tehc_level: 2\n")
        obj = self.config()
        self.assertEqual(obj["warnings"], [{"key": "narrative.tehc_level", "reason": "unknown", "value": None,
                                            "path": self.box.user_file, "line": 2}])
        self.assertFalse([s for s in obj["settings"] if s["key"] == "narrative.tehc_level"])
        self.box.write(self.box.user_file, "narrative: {tech_level: 2\n")
        p, obj = self.box.json("describe", "config", "--json")
        self.assertEqual(p.returncode, 0)
        self.assertIs(obj["ok"], True)
        rows = [w for w in obj["warnings"] if w["reason"] == "unreadable"]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["key"], rows[0]["path"]), (None, self.box.user_file))
        self.assertIn({"name": "user", "path": self.box.user_file, "present": True, "travels": True},
                      obj["layers"])


class Dotted(Case):
    """R1-F2: a file key spelt with a dot is unknown: no second setting, the real one sourced where
    its value comes from, and one `unknown` warning at the dotted key's own line."""

    COUNT = 117

    def dotted(self, files, key, value, source, warning):
        for name, text in files.items():
            self.box.write(self.box.user_file if name == "user" else self.box.project_file, text)
        obj = self.config()
        self.held(obj)
        keys = [s["key"] for s in obj["settings"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len(keys), self.COUNT)
        s = self.setting(obj, key)
        self.assertEqual(s["value"], value)
        last = s["values"][-1]
        self.assertEqual(s["source"], source)
        self.assertEqual((last["layer"], last["path"], last["line"]),
                         (source["layer"], source["path"], source["line"]))
        self.assertEqual(self.config(key)["settings"], [s])
        self.assertEqual([(w["key"], w["reason"], w["path"], w["line"]) for w in obj["warnings"]], [warning])

    def default(self, key):
        p = subprocess.run(["grep", "-n", "^ *%s:" % key.rsplit(".", 1)[-1], SHIPPED], capture_output=True)
        line = int(p.stdout.decode().split(":", 1)[0])
        return {"layer": "default", "path": SHIPPED, "line": line}

    def test_the_reviews_nested_dotted_key(self):
        self.dotted({"user": "narrative:\n  tone.formality: 0.2\n"}, "narrative.tone.formality", 0.4,
                    self.default("narrative.tone.formality"),
                    ("narrative.tone.formality", "unknown", self.box.user_file, 2))

    def test_a_top_level_dotted_key(self):
        self.dotted({"user": '"narrative.tech_level": 4\n'}, "narrative.tech_level", 3,
                    self.default("narrative.tech_level"),
                    ("narrative.tech_level", "unknown", self.box.user_file, 1))

    def test_a_key_with_two_dots(self):
        self.dotted({"user": "# tone\nnarrative.tone.formality: 0.2\n"}, "narrative.tone.formality", 0.4,
                    self.default("narrative.tone.formality"),
                    ("narrative.tone.formality", "unknown", self.box.user_file, 2))

    def test_a_trailing_dot(self):
        self.dotted({"user": "narrative:\n  tech_level.: 4\n"}, "narrative.tech_level", 3,
                    self.default("narrative.tech_level"),
                    ("narrative.tech_level.", "unknown", self.box.user_file, 2))

    def test_a_leading_dot(self):
        self.dotted({"user": "narrative:\n  .tech_level: 4\n"}, "narrative.tech_level", 3,
                    self.default("narrative.tech_level"),
                    ("narrative..tech_level", "unknown", self.box.user_file, 2))

    def test_dotted_beside_the_real_nested_key(self):
        user = {"layer": "user", "path": self.box.user_file, "line": 3}
        self.dotted({"user": "narrative:\n  tone:\n    formality: 0.3\n  tone.formality: 0.2\n"},
                    "narrative.tone.formality", 0.3, user,
                    ("narrative.tone.formality", "unknown", self.box.user_file, 4))

    def test_dotted_above_the_real_nested_key(self):
        user = {"layer": "user", "path": self.box.user_file, "line": 3}
        self.dotted({"user": "narrative:\n  tone:\n    formality: 0.3\n",
                     "project": "narrative:\n  tone.formality: 0.2\n"},
                    "narrative.tone.formality", 0.3, user,
                    ("narrative.tone.formality", "unknown", self.box.project_file, 2))


class InProcess(Case):
    """A8: every setting's value is resolve's leaf, for the fixtures of A2 to A6."""

    FIXTURES = (
        {},
        {"user": "narrative:\n  tech_level: 2\n"},
        {"project": "# the project's tone\nnarrative:\n  profile: exec\n"},
        {"project": "gate:\n  fail_on: warn\n", "docs": "narrative:\n  tech_level: 1\n"},
        {"project": "narrative:\n  tone:\n    formality: 0.5\n", "user": "gate:\n  enabled: true\n"},
    )

    def test_values_are_resolves(self):
        plug = load("respeak_plug_t", PLUG)
        rc = load("respeak_config_t2", RESOLVER)
        for fx in self.FIXTURES:
            box = Box()
            self.addCleanup(box.cleanup)
            cwd = box.proj
            if "user" in fx:
                box.write(box.user_file, fx["user"])
            if "project" in fx:
                box.write(box.project_file, fx["project"])
            if "docs" in fx:
                box.write(os.path.join(box.proj, "docs", ".respeak.yaml"), fx["docs"])
                cwd = os.path.join(box.proj, "docs")
            with mock.patch.dict(os.environ, box.env(), clear=True), chdir(cwd):
                obj = plug.config_read(None)
                res = rc.resolve()
            self.assertTrue(obj["settings"], fx)
            for s in obj["settings"]:
                want = rc.get_dotted(res.config, s["key"])
                if s["key"] == "never_compress":
                    want = [e["class"] for e in want]
                self.assertEqual(s["value"], want, (fx, s["key"]))


@contextlib.contextmanager
def chdir(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class Bare(Case):
    """A9: with no PyYAML the describe read answers and the config read says what it needs."""

    def test_no_pyyaml(self):
        env = self.box.env()
        p = subprocess.run([PY, "-S", PLUG, "describe", "--json"], cwd=self.box.proj, env=env,
                           capture_output=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["tool"], "respeak")
        p = subprocess.run([PY, "-S", PLUG, "describe", "config", "--json"], cwd=self.box.proj, env=env,
                           capture_output=True, timeout=30)
        self.assertEqual(p.returncode, 2)
        obj = json.loads(p.stdout)
        self.assertIs(obj["ok"], False)
        self.assertEqual(obj["error"]["code"], "missing_need")
        self.assertEqual(obj["error"]["remedy"], "agentik respeak doctor")
        self.assertIn("PyYAML", obj["error"]["message"])

    def test_config_explain_is_the_wrappers(self):
        self.box.write(self.box.user_file, "narrative:\n  tech_level: 2\n")
        mine = self.box.run("config", "explain")
        theirs = subprocess.run(["bash", WRAPPER, "explain"], cwd=self.box.proj, env=self.box.env(),
                                capture_output=True, timeout=30)
        self.assertEqual(mine.returncode, 0, mine.stderr)
        self.assertEqual(mine.stdout, theirs.stdout)
        self.assertEqual(mine.returncode, theirs.returncode)


class Doctor(Case):
    """A10: doctor --json from the script's own lines; doctor prints them."""

    def test_doctor_json(self):
        path = self.box.stub()
        p, obj = self.box.json("doctor", "--json", PATH=path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((obj["schema"], obj["ok"], obj["tool"]), ("agentik.doctor/1", True, "respeak"))
        self.assertEqual([c["name"] for c in obj["checks"]],
                         ["python", "claude", "marketplace", "plugin", "provider", "config"])
        for c in obj["checks"]:
            self.assertEqual(set(c) >= {"name", "status", "detail", "remedy"}, True, c)
            self.assertIn(c["status"], ("ok", "note", "warn", "fail"))
        status = {c["name"]: c["status"] for c in obj["checks"]}
        self.assertEqual(status["python"], "ok")
        self.assertEqual(status["marketplace"], "ok")
        self.assertEqual(status["provider"], "note")
        self.assertEqual(obj["failed"], 0)
        self.assertEqual(obj["warned"], sum(1 for c in obj["checks"] if c["status"] == "warn"))

    def test_doctor_json_without_the_marketplace(self):
        path = self.box.stub(market="[]")
        p, obj = self.box.json("doctor", "--json", PATH=path)
        self.assertEqual(p.returncode, 0, p.stderr)
        mkt = [c for c in obj["checks"] if c["name"] == "marketplace"][0]
        self.assertEqual((mkt["status"], mkt["detail"], mkt["remedy"]), ("warn", "none", MARKET_REMEDY))

    def test_doctor_json_from_a_forks_install(self):
        path = self.box.stub(plugins=FORK_PLUGINS)
        p, obj = self.box.json("doctor", "--json", PATH=path)
        self.assertEqual(p.returncode, 0, p.stderr)
        plug = [c for c in obj["checks"] if c["name"] == "plugin"][0]
        self.assertEqual((plug["status"], plug["remedy"]), ("ok", None))
        manifest = json.load(open(MANIFEST))["version"]
        self.assertEqual(plug["detail"], "installed from another source 0.12.6, manifest %s" % manifest)
        self.assertEqual(plug["source"], {"id": "respeak@acme-tools", "marketplace": "acme-tools",
                                          "folder": PLUGIN, "version": "0.12.6-acme.1"})
        for key in ("name", "detail", "remedy"):
            self.assertNotIn("acme", str(plug[key]), key)
        self.assertEqual([c for c in obj["checks"] if "source" in c], [plug])

    def test_doctor_json_the_suites_ids_keep_their_detail(self):
        path = self.box.stub()
        p, obj = self.box.json("doctor", "--json", PATH=path)
        plug = [c for c in obj["checks"] if c["name"] == "plugin"][0]
        self.assertTrue(plug["detail"].startswith("respeak@agentik 0.6.0, manifest "), plug)
        self.assertNotIn("source", plug)

    def test_doctor_text_from_a_forks_install_prints_its_id(self):
        path = self.box.stub(plugins=FORK_PLUGINS)
        p = self.box.run("doctor", PATH=path)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertTrue(p.stdout.decode().splitlines()[3].startswith("plugin: respeak@acme-tools 0.12.6-acme.1, "))

    def test_doctor_text_is_the_scripts(self):
        path = self.box.stub()
        mine = self.box.run("doctor", PATH=path)
        theirs = subprocess.run(["bash", DOCTOR], cwd=self.box.proj, env=self.box.env(PATH=path),
                                capture_output=True, timeout=30)
        self.assertEqual(mine.returncode, theirs.returncode)
        self.assertEqual(mine.stdout, theirs.stdout)
        self.assertEqual(len(mine.stdout.decode().splitlines()), 6)


class Writes(Case):
    """A11: the reads write nothing outside $XDG_CACHE_HOME/agentik/, and no bytecode beside the code."""

    def snapshot(self):
        keep = os.path.join(self.box.cache, "agentik")
        out = {}
        for top in (self.box.home, self.box.proj):
            for dirpath, dirs, files in os.walk(top):
                if dirpath == keep or dirpath.startswith(keep + os.sep):
                    continue
                if dirpath != self.box.cache:   # the parent of agentik/, made to hold it
                    out[dirpath] = None
                for name in files:
                    path = os.path.join(dirpath, name)
                    with open(path, "rb") as f:
                        out[path] = hashlib.sha256(f.read()).hexdigest()
        return out

    def bytecode(self):
        out = set()
        for dirpath, _, files in os.walk(os.path.join(PLUGIN, "scripts")):
            out.update(os.path.join(dirpath, f) for f in files if f.endswith((".pyc", ".pyo")))
        return out

    maxDiff = None

    def test_nothing_written(self):
        self.box.write(self.box.user_file, "narrative:\n  tech_level: 2\ngate:\n  enabled: true\n")
        self.box.write(self.box.project_file, "narrative:\n  profile: exec\n")
        self.box.write(os.path.join(self.box.proj, "docs", ".respeak.yaml"), "narrative:\n  tech_level: 1\n")
        path = self.box.stub()
        before, pyc = self.snapshot(), self.bytecode()
        for words in (["describe", "--json"], ["describe", "config", "--json"],
                      ["describe", "config", "--json", "narrative.tech_level"], ["doctor", "--json"]):
            p = self.box.run(*words, PATH=path)
            self.assertEqual(p.returncode, 0, (words, p.stderr))
        p = self.box.run("describe", "config", "--json", cwd=os.path.join(self.box.proj, "docs"), PATH=path)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.bytecode(), pyc)


VERBS = (["describe", "--json"], ["describe", "config", "--json"],
         ["describe", "config", "--json", "narrative.tech_level"], ["doctor", "--json"],
         ["config", "explain"], ["doctor"], ["--version"], ["--help"])


class WritesUnpinned(unittest.TestCase):
    """R1-F1: with RESPEAK_PYTHON unset, each verb in a new temp HOME and a temp cache root writes
    nothing outside $XDG_CACHE_HOME/agentik/, under Apple's /usr/bin/python3 and under a newer one."""

    maxDiff = None

    def created(self, words, first=None):
        root = os.path.realpath(tempfile.mkdtemp(prefix="respeak-unpinned-"))
        self.addCleanup(shutil.rmtree, root, True)
        home, cache, proj, bin_ = (os.path.join(root, d) for d in ("home", "cache", "proj", "bin"))
        for d in (home, cache, proj, bin_):
            os.makedirs(d)
        with open(os.path.join(bin_, "claude"), "w") as f:
            f.write(STUB % (KNOWN_MARKET, KNOWN_PLUGINS))
        os.chmod(os.path.join(bin_, "claude"), 0o755)
        path = ":".join(([first] if first else []) + [bin_, "/usr/bin", "/bin"])
        env = {"HOME": home, "PATH": path, "TERM": "dumb", "XDG_CACHE_HOME": cache,
               "XDG_CONFIG_HOME": os.path.join(home, ".config"),
               "XDG_STATE_HOME": os.path.join(home, ".local", "state"),
               "XDG_DATA_HOME": os.path.join(home, ".local", "share")}
        p = subprocess.run([LAUNCHER] + words, cwd=proj, env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, timeout=60)
        self.assertIn(p.returncode, (0, 1, 2), (words, p.stderr))
        if "--json" in words:
            self.assertIn("schema", json.loads(p.stdout.decode("utf-8")), words)
        keep = os.path.join(cache, "agentik")
        out = []
        for top in (home, cache, proj):
            for dirpath, _, files in os.walk(top):
                if dirpath == keep or dirpath.startswith(keep + os.sep):
                    continue
                out.extend(os.path.relpath(os.path.join(dirpath, f), root) for f in files)
        return sorted(out)

    def each_verb(self, first=None):
        for words in VERBS:
            with self.subTest(words=" ".join(words)):
                self.assertEqual(self.created(list(words), first), [])

    @unittest.skipUnless(os.path.isfile("/usr/bin/python3"), "no /usr/bin/python3")
    def test_system_python(self):
        p = subprocess.run(["/usr/bin/python3", "-B", "-c", "import sys; print(sys.version_info >= (3, 8))"],
                           capture_output=True, timeout=30)
        if p.stdout.strip() != b"True":
            self.skipTest("/usr/bin/python3 is older than 3.8")
        self.each_verb()

    def test_newer_python(self):
        d = tempfile.mkdtemp(prefix="respeak-py-")
        self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, "python3"), "w") as f:
            f.write('#!/bin/sh\nexec "%s" "$@"\n' % PY)
        os.chmod(os.path.join(d, "python3"), 0o755)
        self.each_verb(first=d)


if __name__ == "__main__":
    unittest.main()
