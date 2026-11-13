#!/usr/bin/env python3
"""respeak-plug.py: the agentik suite's three reads of respeak (packet ak9-plug-respeak).

Usage (through plugin/bin/agentik-respeak, which picks the interpreter):
  respeak-plug.py describe --json                 what the tool is, needs, verbs and reads
  respeak-plug.py describe config --json [KEY]    every setting, its value, default, source
                                                  file and line, the edit that changes it
  respeak-plug.py doctor --json                   respeak-doctor.sh's lines as checks

Each prints one JSON object and a newline on stdout, in the suite's plug contract's shapes
(`agentik.describe/1`, `agentik.config/1`, `agentik.doctor/1`). Only the standard library is
imported here: the config read alone loads respeak-config.py by its path, and with it PyYAML,
so `describe --json` and `doctor --json` answer on a machine without PyYAML. The config read
writes nothing; the doctor read is the script's, which writes nothing either.

Exit codes: 0 the read ran; 2 a bad word, or a read that could not run (the object says why);
`doctor --json` exits with the script's code.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESOLVER = os.path.join(HERE, "respeak-config.py")
DOCTOR = os.path.join(HERE, "respeak-doctor.sh")
TOOL = "respeak"

# respeak-config.sh's own sentence when no python3 has PyYAML.
NEED_MESSAGE = ("respeak-config: no python3 with PyYAML found (tried python3, /usr/bin/python3, "
                "brew pythons); set RESPEAK_PYTHON=/path/to/python3 or install PyYAML")
MARKET_REMEDY = "claude plugin marketplace add agentik-dev/agentik-commons"
PLUGIN_REMEDY = "claude plugin install respeak@agentik"

# Help's own lines for each verb (plugin/bin/agentik-respeak --help prints the same words).
VERBS = (
    ("describe", "Print what the tool is, what it needs and what it reads, as JSON."),
    ("doctor", "Check the tool and what it needs."),
    ("config", "Explain, resolve, gate or validate the layered configuration."),
)

# respeak-config.py's layer kinds, by the contract's names. `invocation` is no layer of a read.
NAMES = {"plugin": "default", "userconfig": "install", "user": "user",
         "ancestor": "folder", "ancestor-local": "folder", "folder": "folder", "folder-local": "folder",
         "project": "repo", "project-local": "local", "session": "session", "env": "env"}
EDITABLE = ("user", "folder", "repo", "local")

# The keys the tool knows, each to one sentence; `*` stands for one segment (a mode or a profile).
SUMMARIES = {
    "narrative.default_mode": "The form a render takes when none is asked for: eli5, bluf or technical.",
    "narrative.profile": "The audience a render is written for, by the name of a profile.",
    "narrative.tech_level": "How much the reader is assumed to know, from 1 to 5.",
    "narrative.tone.formality": "How formal the register is, from 0, conversational, to 1.",
    "narrative.tone.directness": "How soon the conclusion comes, from 0, cushioned, to 1, first.",
    "narrative.tone.confidence": "How plainly a render states its claims, with any doubt said once and precisely.",
    "narrative.context_default": "The reader's state a render assumes: incident, routine or celebration.",
    "narrative.mode_select": "How a render's mode is chosen: fixed, or compass, a two-question classifier.",
    "narrative.reading_level_grade": "The school grade a render's wording aims at, a cue no script computes.",
    "narrative.address": "How a render addresses its reader.",
    "gate.enabled": "Whether the style gate checks this project's documents.",
    "gate.fail_on": "The level of finding at which the gate fails: none, warn or error.",
    "gate.include": "The files and folders the gate checks.",
    "gate.exclude": "The files and folders the gate leaves out.",
    "gate.allow": "The patterns whose corpus rules the gate skips, for a domain's own terms.",
    "editorial_pass.restructure": "Whether an editorial pass may move sections: advise, apply or off.",
    "editorial_pass.buried_lede_boundary": "Where a reader must already know the outcome: the first paragraph or N sentences.",
    "editorial_pass.prefer_abstract_over_reorder": "Whether an applied pass may add a summary at the top instead of moving sections.",
    "editorial_pass.verify.prose_keys": "The front-matter and YAML keys whose string values a pass may reword.",
    "editorial_pass.verify.allow_strings": "Whether a pass may change the text of string literals in Python page generators.",
    "editorial_pass.verify.paths": "The non-Markdown files, as git pathspecs, the check verifies after a pass.",
    "data.table_over_prose_threshold": "How many like items a list may hold before it is rendered as a table.",
    "data.key_column_first": "Whether a table opens with the column the reader decides on.",
    "data.summary_first": "Whether totals, deltas or a verdict line come before the detail rows.",
    "data.outlier_callout": "Whether an outlier that bears on the decision is named above its table.",
    "data.max_bullets_per_list": "The most bullets a list holds before it becomes a table or is grouped.",
    "data.sort_by": "The order of a table's rows: decision_relevance, magnitude or source_order.",
    "profiles.*.tech_level": "How much a reader of this profile is assumed to know, from 1 to 5.",
    "profiles.*.reading_level_grade": "The school grade a render for this profile aims at; null sets none.",
    "profiles.*.default_mode": "The form a render for this profile takes when none is asked for.",
    "profiles.*.address": "How a render for this profile addresses its reader.",
    "modes.*.length_budget_words": "The words a render in this mode may run to.",
    "modes.*.max_sentence_words": "The longest sentence, in words, a render in this mode may hold.",
    "modes.*.tech_level": "How much a reader in this mode is assumed to know, from 1 to 5.",
    "modes.*.reading_level_grade": "The school grade a render in this mode aims at, a cue no script computes.",
    "modes.*.max_paragraphs": "The most paragraphs a render in this mode may hold.",
    "modes.*.max_paragraph_sentences": "The most sentences a paragraph in this mode may hold.",
    "modes.*.max_paragraph_words": "The longest paragraph, in words, a render in this mode may hold.",
    "modes.*.max_step_words": "The longest procedural step, in words, a render in this mode may hold.",
    "modes.*.structure": "The shape a render in this mode follows, such as bluf or finding-first.",
    "modes.*.data": "How a render in this mode treats data; summarize-only states one comparison.",
    "modes.*.address_reader": "Whether a render in this mode speaks to the reader as you.",
    "modes.*.common_ground_opener": "Whether a render in this mode opens with something the reader knows.",
    "modes.*.metaphor_budget": "How many metaphors a render in this mode may use.",
    "modes.*.analogy_must_close": "Whether an analogy in this mode must say what it maps to.",
    "modes.*.undefined_abbreviations": "Whether a render in this mode may use an abbreviation it does not define.",
    "modes.*.contractions": "Whether a render in this mode may use contractions.",
    "modes.*.checks": "The judged checks a render in this mode must pass.",
    "modes.*.output_glob": "The files a render in this mode is written to.",
    "modes.*.tone.formality": "How formal a render in this mode is, from 0, conversational, to 1.",
    "modes.*.tone.directness": "How soon a render in this mode reaches its conclusion, from 0 to 1.",
    "modes.*.tone.confidence": "How plainly a render in this mode states its claims, from 0 to 1.",
    "modes.*.require_ask.owner": "Whether a render in this mode must name who owns the ask.",
    "modes.*.require_ask.deadline": "Whether a render in this mode must give the ask a deadline.",
    "modes.*.require_ask.allow_fyi_no_action": "Whether a plain FYI with no action needed satisfies the ask.",
    "modes.*.bullets.lead_in_required": "Whether a bulleted list in this mode needs a lead-in line.",
    "modes.*.bullets.min_items": "The fewest items a bulleted list in this mode may hold.",
    "modes.*.bullets.max_sentences_per_item": "The most sentences one bullet in this mode may hold.",
    "modes.*.grouping": "How sibling points in this mode are grouped; mece means no overlap and none missing.",
    "modes.*.scqa_preamble_max_clauses": "The most clauses of setup a render in this mode may give before its answer.",
    "modes.*.open_questions_require_test": "Whether an open question in this mode must end with a check that could fail.",
    "modes.*.passive_allowed_when": "When a render in this mode may use the passive voice.",
    "modes.*.procedural.active_voice": "The share of steps that must be active or imperative, from 0 to 1.",
    "modes.*.procedural.one_instruction_per_sentence": "Whether each procedural sentence holds one instruction.",
    "modes.*.procedural.numbered_steps": "Whether a process is written as numbered steps, not bullets.",
    "modes.*.procedural.safety_lines_first": "Whether a safety line comes before the step it guards.",
    "style.banned_phrases": "The corpus file of phrases a render never uses.",
    "style.replacements": "The corpus file of plainer words that replace flagged ones.",
    "style.rules": "The corpus folder of style rules the scanner applies.",
    "style.no_pleasantries": "Whether a render leaves out greetings and pleasantries.",
    "style.no_self_narration": "Whether a render leaves out an account of its own process.",
    "style.person": "The grammatical person a render is written in.",
    "style.tense": "The tense a render is written in.",
    "style.contractions": "Whether a render may use positive contractions.",
    "style.negative_contractions": "Whether a render may contract a negative; never means cannot, not can't.",
    "style.positive_form": "Whether a render avoids double negatives.",
    "style.same_term_same_concept": "Whether one concept keeps one term throughout a render.",
    "style.quoting_exempt": "Whether quotes and code blocks are exempt from the bans.",
    "style.readability_metrics": "The readability formulas declared for a render; no script computes them.",
    "style.min_alert_level.ci": "The lowest level of finding reported in CI.",
    "style.min_alert_level.interactive": "The lowest level of finding reported in an interactive session.",
    "style.budgets.max_sentence_words": "The longest sentence, in words, the scanner lets pass.",
    "style.budgets.passive_per_10_sentences": "How many passive sentences in ten a render may hold.",
    "style.budgets.adverb_intensifiers_per_100_words": "How many intensifying adverbs in a hundred words a render may hold.",
    "style.budgets.qualifiers_per_message": "How many hedging qualifiers one message may hold.",
    "style.budgets.exclamations_per_doc": "How many exclamation marks one document may hold.",
    "style.budgets.warn_phrases_per_1000_words": "How many warned phrases in a thousand words the scanner lets pass.",
    "style.budgets.emdash_per_1000_words": "How many em dashes in a thousand words the scanner lets pass.",
    "style.budgets.avg_sentence_words": "The average sentence length, in words, the scanner lets pass.",
    "style.feedback.core_required": "Whether feedback must give context, observation, result and next step.",
    "style.feedback.specific_praise_required": "Whether praise must say what was good, never a bare looks good.",
    "style.feedback.behavior_not_person": "Whether feedback addresses the behaviour, never the person.",
    "never_compress": "The classes of content a render keeps word for word in every mode.",
}
_EXACT = {k: v for k, v in SUMMARIES.items() if "*" not in k}
_PATTERNS = [(k.split("."), v) for k, v in SUMMARIES.items() if "*" in k]

# Closed sets: FAIL_ON_VALUES is respeak-config.py's; the rest are the comments beside the keys
# in config/respeak.config.yaml.
CHOICES = {
    "narrative.default_mode": ["eli5", "bluf", "technical"],
    "narrative.mode_select": ["fixed", "compass"],
    "narrative.context_default": ["incident", "routine", "celebration"],
    "editorial_pass.restructure": ["advise", "apply", "off"],
    "data.sort_by": ["decision_relevance", "magnitude", "source_order"],
}
# A key whose shipped default is null takes its type from here.
TYPE_HINTS = {"reading_level_grade": "integer"}
PLAIN = re.compile(r"[A-Za-z][A-Za-z0-9_./-]*")
YAML_WORDS = {"true", "false", "null", "yes", "no", "on", "off", "y", "n"}


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")


def error(schema, code, message, remedy=None):
    emit({"schema": schema, "ok": False, "tool": TOOL,
          "error": {"code": code, "message": message, "remedy": remedy}})
    return 2


def summary_for(key):
    if key in _EXACT:
        return _EXACT[key]
    segs = key.split(".")
    for pat, text in _PATTERNS:
        if len(pat) == len(segs) and all(p in ("*", s) for p, s in zip(pat, segs)):
            return text
    return None


def known_prefix(key):
    """True when key is the mapping above some key the table knows."""
    segs = key.split(".")
    for k in SUMMARIES:
        pat = k.split(".")
        if len(pat) > len(segs) and all(p in ("*", s) for p, s in zip(pat, segs)):
            return True
    return False


# --------------------------------------------------------------------------
# describe --json
# --------------------------------------------------------------------------

def manifest_version():
    try:
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
            return str(json.load(f).get("version") or "unknown")
    except (OSError, ValueError):
        return "unknown"


def describe():
    return {
        "schema": "agentik.describe/1", "ok": True, "tool": TOOL, "version": manifest_version(),
        "summary": "Writes agent work up as a narrative for a person, in a tone set in layers.",
        "repo": "agentik-dev/agentik-respeak", "plugin": "respeak@agentik",
        "needs": [
            {"name": "PyYAML", "kind": "package", "why": "its resolver and its scanner import it",
             "optional": False},
            {"name": "claude", "kind": "program",
             "why": "a render runs it, and the doctor reads its plugin lists", "optional": True},
        ],
        "verbs": [{"name": n, "summary": s, "top": False} for n, s in VERBS],
        "reads": [{"kind": "config", "name": "settings", "argv": ["describe", "config", "--json"]},
                  {"kind": "doctor", "name": "doctor", "argv": ["doctor", "--json"]}],
    }


# --------------------------------------------------------------------------
# describe config --json [KEY]
# --------------------------------------------------------------------------

def load_resolver():
    spec = importlib.util.spec_from_file_location("respeak_config", RESOLVER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def split_label(label):
    """(file layer's label, scope index or None, profile name or None) of an origin label."""
    if " + " in label:              # an appending list names every layer that added to it
        label = label.rsplit(" + ", 1)[1]
    profile = scope = None
    m = re.match(r"^(.*) \(profile (.*)\)$", label)
    if m:
        label, profile = m.group(1), m.group(2)
    m = re.match(r"^(.*)#scopes\[(\d+)\]$", label)
    if m:
        label, scope = m.group(1), int(m.group(2))
    return label, scope, profile


class Lines:
    """Each file's node tree from PyYAML's composer; a key's line is its node's mark, plus one."""

    def __init__(self, yaml):
        self.yaml = yaml
        self.loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        self.roots = {}
        self.errors = {}

    def root(self, path):
        if path not in self.roots:
            node = None
            try:
                with open(path, encoding="utf-8") as f:
                    node = self.yaml.compose(f.read(), Loader=self.loader)
            except Exception as e:  # noqa: BLE001 - the loader skipped it too
                mark = getattr(e, "problem_mark", None) or getattr(e, "context_mark", None)
                self.errors[path] = mark.line + 1 if mark is not None else None
            self.roots[path] = node
        return self.roots[path]

    @staticmethod
    def child(node, seg):
        key = None
        if node is not None and node.id == "mapping":
            for k, v in node.value:
                if k.id == "scalar" and k.value == str(seg):
                    key, found = k, v
            if key is not None:
                return key, found
        return None, None

    def line(self, path, segs, scope=None, prefix=()):
        if path is None:
            return None
        node = self.root(path)
        for seg in prefix:
            node = self.child(node, seg)[1]
        if scope is not None:
            node = self.child(node, "scopes")[1]
            node = node.value[scope] if node is not None and node.id == "sequence" and scope < len(node.value) else None
        key = None
        for seg in segs:
            key, node = self.child(node, seg)
            if key is None:
                return None
        return key.start_mark.line + 1


def leaves(d, prefix=""):
    """Each leaf's dotted key. A file key spelt with a dot is no setting: the resolver merges it as
    one literal key, so it would read as a second row of the real key; `walk` warns it instead."""
    for k, v in d.items():
        if "." in str(k):
            continue
        key = "%s.%s" % (prefix, k) if prefix else str(k)
        if isinstance(v, dict) and v:
            for item in leaves(v, key):
                yield item
        else:
            yield key, v


def type_of(v):
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, list):
        return "list"
    if isinstance(v, str):
        return "string"
    return None


def shown(key, v):
    """The contract's value: never_compress's mappings read as their classes."""
    if key == "never_compress" and isinstance(v, list):
        return [e.get("class") if isinstance(e, dict) else e for e in v]
    return v


def scalar(v):
    if isinstance(v, str):
        return v if PLAIN.fullmatch(v) and v.lower() not in YAML_WORDS else json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False)


def block(key, v):
    segs = key.split(".")
    out = ["%s%s:" % ("  " * i, s) for i, s in enumerate(segs[:-1])]
    pad = "  " * (len(segs) - 1)
    if isinstance(v, list) and any(isinstance(e, dict) for e in v):
        out.append("%s%s:" % (pad, segs[-1]))
        out.extend("%s  - %s" % (pad, scalar(e)) for e in v)
    else:
        out.append("%s%s: %s" % (pad, segs[-1], scalar(v)))
    return "\n".join(out)


class Reader:
    def __init__(self, rc, yaml, res):
        self.rc, self.res = rc, res
        self.lines = Lines(yaml)
        self.by_label = {lay.label: lay for lay in res.layers}
        self.user = next((lay for lay in res.layers if lay.kind == "user"), None)
        self.project = next((lay for lay in res.layers if lay.kind == "project"), None)
        plugin = res.layers[0]
        self.defaults = {}
        if plugin.present:
            rc.apply_layer(self.defaults, {}, plugin, plugin.data, res.target, [], [])

    @staticmethod
    def prefix(lay):
        return ("respeak",) if lay.kind == "session" else ()

    def file_of(self, lay):
        """(file layer, scope index or None) of an applied layer, a scope's included."""
        base, scope, _ = split_label(lay.label)
        return self.by_label.get(base, lay), scope

    # -- layers ------------------------------------------------------------
    def layers(self):
        low, high, seen = [], [], set()
        for lay in self.res.layers:
            name = NAMES.get(lay.kind)
            if name is None:
                continue
            exists = lay.path is not None and os.path.isfile(lay.path)
            if name == "folder" and not exists:
                continue
            present = True if name == "default" else (lay.present if name in ("install", "session") else exists)
            row = {"name": name, "path": None if name == "install" else lay.path,
                   "present": present, "travels": name == "user"}
            (high if name in ("session", "env") else low).append(row)
            seen.add(name)
        for name in ("repo", "local"):
            if name not in seen:
                low.append({"name": name, "path": None, "present": False, "travels": False})
        for name in ("session", "env"):
            if name not in seen:
                high.append({"name": name, "path": None, "present": False, "travels": False})
        session = [r for r in high if r["name"] == "session"]
        return low + session + [r for r in high if r["name"] != "session"]

    # -- one setting ----------------------------------------------------------
    def source(self, key, rows=()):
        """The origin's layer, file and line; the last of `rows` (the key's values) when the origin
        names a layer with no row, as a dotted file key records its origin in the real key's slot."""
        src = self.origin(key)
        if rows and not any((r["layer"], r["path"]) == (src["layer"], src["path"]) for r in rows):
            last = rows[-1]
            src = {"layer": last["layer"], "path": last["path"], "line": last["line"]}
        return src

    def origin(self, key):
        label = self.res.origins.get(key)
        if label is None:
            plugin = self.res.layers[0]
            return {"layer": "default", "path": plugin.path, "line": None}
        base, scope, profile = split_label(label)
        lay = self.by_label.get(base)
        if lay is None:
            return {"layer": "default", "path": None, "line": None}
        segs = ["narrative", "profile"] if profile else key.split(".")
        path = lay.path if NAMES.get(lay.kind) != "install" else None
        return {"layer": NAMES.get(lay.kind, lay.kind), "path": path,
                "line": self.lines.line(path, segs, scope, self.prefix(lay))}

    def values(self, key):
        rc, rows, profiles = self.rc, [], {}
        missing = object()
        segs = key.split(".")
        for lay in self.res.applied:
            data = lay.data if isinstance(lay.data, dict) else {}
            filed, scope = self.file_of(lay)
            path = filed.path if NAMES.get(filed.kind) != "install" else None
            table = rc.deep_merge(profiles, data["profiles"]) if isinstance(data.get("profiles"), dict) else profiles
            if rc.key_allowed(key, lay.kind):
                v = rc.get_dotted(data, key, missing)
                where = segs
                if v is missing and len(segs) == 2 and segs[0] == "narrative" and segs[1] in rc.PROFILE_KEYS:
                    prof = rc.get_dotted(data, "narrative.profile")
                    p = table.get(prof) if isinstance(prof, str) else None
                    if isinstance(p, dict) and segs[1] in p:
                        v, where = p[segs[1]], ["narrative", "profile"]
                if v is not missing and not isinstance(v, dict):
                    rows.append({"layer": NAMES.get(filed.kind, filed.kind), "value": shown(key, v),
                                 "path": path, "line": self.lines.line(path, where, scope, self.prefix(filed))})
            profiles = table
        return rows

    def change(self, key, value, source):
        if source["layer"] in EDITABLE:
            path = source["path"]
        elif self.rc.key_allowed(key, "user"):
            path = self.user.path if self.user else None
        else:
            path = self.project.path if self.project else None
        note = "--set %s=VALUE changes it for one render." % key
        scope = split_label(self.res.origins.get(key) or "")[1]
        if scope is not None and path == source["path"]:
            note = "The value in force is set in that file's scopes[%d] entry; %s" % (scope, note)
        if path is None:
            note = "Only a project's file sets it and none is found here; " + note
        return {"kind": "edit", "command": None, "path": path, "block": block(key, value), "note": note}

    def settings(self):
        rc, out = self.rc, []
        for key, raw in leaves(self.res.config):
            text = summary_for(key)
            if text is None:
                continue
            value = shown(key, raw)
            default = rc.get_dotted(self.defaults, key)
            default = None if isinstance(default, dict) else shown(key, default)
            kind = type_of(default) or type_of(value) or TYPE_HINTS.get(key.rsplit(".", 1)[-1], "string")
            choices = CHOICES.get(key)
            if key == "gate.fail_on":
                choices = list(rc.FAIL_ON_VALUES)
            rows = self.values(key)
            source = self.source(key, rows)
            out.append({"key": key, "value": value, "default": default, "type": kind, "choices": choices,
                        "summary": text, "source": source, "change": self.change(key, raw, source),
                        "live": True, "values": rows})
        return out

    # -- warnings ---------------------------------------------------------------
    def warnings(self):
        rows = []
        for lay in self.res.layers:
            if lay.kind in ("plugin", "userconfig", "invocation") or lay.path is None:
                continue
            if not os.path.isfile(lay.path):
                continue
            if lay.data is None:
                self.lines.root(lay.path)
                rows.append({"key": None, "reason": "unreadable", "value": None, "path": lay.path,
                             "line": self.lines.errors.get(lay.path)})
                continue
            self.walk(rows, lay, lay.data, lay.kind, None, (), True)
        return rows

    def walk(self, rows, lay, data, kind, scope, prefix, top):
        """Warning rows for one file's mapping; `prefix` is the tuple of keys above it."""
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            segs = prefix + (str(k),)
            key = ".".join(segs)
            reason = None
            if top and k == "scopes" and scope is None:
                for i, entry in enumerate(v if isinstance(v, list) else []):
                    if isinstance(entry, dict):
                        overlay = {a: b for a, b in entry.items() if a not in ("paths", "scopes")}
                        self.walk(rows, lay, overlay, "scope", i, (), True)
                continue
            if "." in str(k) or (top and k not in self.rc.KNOWN_TOP_KEYS):
                reason = "unknown"
            elif key in ("version", "schema"):
                reason = None if self.rc.key_allowed(key, kind) else "ignored"
            elif isinstance(v, dict) and v:
                self.walk(rows, lay, v, kind, scope, segs, False)
                continue
            elif summary_for(key) is None:
                reason = None if isinstance(v, dict) and known_prefix(key) else "unknown"
            elif not self.rc.key_allowed(key, kind):
                reason = "ignored"
            if reason:
                rows.append({"key": key, "reason": reason, "value": None, "path": lay.path,
                             "line": self.lines.line(lay.path, segs, scope, self.prefix(lay))})


def config_read(key=None):
    """The config read's object for the cwd, from os.environ (the API the tests call)."""
    import yaml  # noqa: F401 - the resolver needs it; a caller checks first
    rc = load_resolver()
    res = rc.resolve()
    reader = Reader(rc, yaml, res)
    settings = reader.settings()
    if key is not None:
        settings = [s for s in settings if s["key"] == key]
    return {"schema": "agentik.config/1", "ok": True, "tool": TOOL, "layers": reader.layers(),
            "settings": settings, "warnings": reader.warnings()}


def config_main(key):
    try:
        import yaml  # noqa: F401
    except ImportError:
        return error("agentik.config/1", "missing_need", NEED_MESSAGE, "agentik respeak doctor")
    try:
        obj = config_read(key)
    except Exception as e:  # noqa: BLE001 - the read still answers one object
        return error("agentik.config/1", "read_failed", "%s: %s" % (type(e).__name__, str(e).splitlines()[0] if str(e) else ""),
                     "agentik respeak config explain")
    emit(obj)
    return 0


# --------------------------------------------------------------------------
# doctor --json
# --------------------------------------------------------------------------

def check(line):
    name, _, detail = line.partition(":")
    name, detail = name.strip(), detail.strip()
    status, remedy = "ok", None
    if name == "python" and ("pyyaml=no" in detail or detail.startswith("missing")):
        status, remedy = "fail", "python3 -m pip install pyyaml"
    elif name == "claude" and detail == "missing":
        status = "warn"
    elif name == "marketplace" and (detail == "none" or "; old" in detail):
        status, remedy = "warn", MARKET_REMEDY
    elif name == "plugin" and (detail.startswith("not installed") or "; old id" in detail):
        status, remedy = "warn", PLUGIN_REMEDY
    elif name == "provider" and (detail == "none" or detail.startswith("unknown")):
        status = "note"
    elif name == "config":
        m = re.match(r"(\d+) unknown", detail)
        if m and int(m.group(1)) > 0:
            status, remedy = "warn", "agentik respeak config explain"
        elif detail.startswith("unknown"):
            status = "note"
    return {"name": name, "status": status, "detail": detail, "remedy": remedy}


def doctor_main():
    env = dict(os.environ)
    prefix = getattr(sys, "pycache_prefix", None)
    if prefix and not env.get("PYTHONPYCACHEPREFIX"):
        env["PYTHONPYCACHEPREFIX"] = prefix   # the script's own pythons write no bytecode beside it
    try:
        p = subprocess.run(["bash", DOCTOR], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, env=env, timeout=20)
    except subprocess.TimeoutExpired:
        return error("agentik.doctor/1", "timeout", "respeak-doctor.sh did not end inside 20 s")
    checks = [check(l) for l in p.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
    emit({"schema": "agentik.doctor/1", "ok": True, "tool": TOOL,
          "failed": sum(1 for c in checks if c["status"] == "fail"),
          "warned": sum(1 for c in checks if c["status"] == "warn"),
          "checks": checks})
    return p.returncode


# --------------------------------------------------------------------------
# words
# --------------------------------------------------------------------------

def usage(line):
    sys.stderr.write("agentik-respeak: %s\n" % line)
    return 2


def main(argv):
    if argv[:1] == ["describe"]:
        rest = argv[1:]
        if rest == ["--json"]:
            emit(describe())
            return 0
        if rest[:1] == ["config"]:
            words = rest[1:]
            if "--json" not in words:
                return usage("the config read is describe config --json [KEY]")
            words.remove("--json")
            if len(words) > 1 or any(w.startswith("-") for w in words):
                return usage("the config read is describe config --json [KEY]")
            return config_main(words[0] if words else None)
        return usage("describe takes one form: describe --json, or describe config --json [KEY]")
    if argv == ["doctor", "--json"]:
        return doctor_main()
    return usage("unknown words %r; see agentik-respeak --help" % " ".join(argv))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
