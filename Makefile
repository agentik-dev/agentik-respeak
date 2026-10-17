# agentik-respeak: the repo's checks (conventions section 5).
# PYTHON is the pyenv virtualenv .python-version declares; override on the command line. When
# its python3 exists it is found by path, with no process: the pyenv shim takes a lock that
# stalled every make under load (review R6, T2). `lint` checks the first name against
# .python-version's first line. Its second line, VENV_OLD, is the venv's name before agentik-r1
# (c10): used while `make venv` has not yet built the new one; r2 removes it.
PYENV_ROOT ?= $(HOME)/.pyenv
VENV = agentik-respeak
VENV_OLD = claude-code-respeak
VENV_PYTHON = $(firstword $(wildcard $(foreach v,$(VENV) $(VENV_OLD),$(PYENV_ROOT)/versions/$(v)/bin/python3)))
ifeq ($(origin PYTHON),undefined)
PYTHON := $(or $(VENV_PYTHON),$(shell python3 -c 'import sys; print(sys.executable)'))
endif
export PYTHON
# Its bin dir first on PATH, so every recipe, and every hook a suite runs, skips the shim.
export PATH := $(patsubst %/,%,$(dir $(PYTHON))):$(PATH)
# The claude CLI `install` and `validate` run; the install suite passes a fake here.
CLAUDE ?= claude

.PHONY: check check-unlocked test lint doclint hygiene readme readme-fresh validate doctor install

# check runs under scripts/bounded, vendored from agentik-commons (conventions section 5,
# its sum in scripts/vendored.sha256): one per tree by the lock .check.lock, an 840 s wall, held off above load 4 x cores.
# make check exits 0, or 2 for any failure: make reads every failure as 2, so the exit alone does
# not tell a refusal from a red suite. A `bounded: stop: lock|load|wall` line means the suite did
# not run to its end: unrun, never red (section 5). The relay's gate reads the last such line
# anywhere in stderr, because make prints its own `Error 2` line after it (review ADV11-3). make
# readme is read the same way: its account failure is the `respeak-render: account failure` line
# in stderr, never the exit, which make turns from the renderer's 4 into 2.
check:
	$(PYTHON) scripts/bounded --lock .check.lock --wall 840 --load 4 -- $(MAKE) check-unlocked

check-unlocked: test lint doclint hygiene plugin-version-check readme-fresh validate

# Every spawn here is bounded: respeak-deadline.sh runs it in its own process group and kills
# the group at the wall clock (exit 124), so a hung suite or a slow claude fails the target.
DEADLINE = bash plugin/scripts/respeak-deadline.sh

# The bash suites run the hooks, which find `python3` on PATH: the export above puts $(PYTHON) first.
test:
	$(DEADLINE) 120 $(PYTHON) -m unittest discover tests </dev/null
	@set -e; for t in tests/*.sh; do echo "== $$t"; $(DEADLINE) 120 bash "$$t" </dev/null; done

lint:
	$(PYTHON) -m compileall -q scripts plugin/scripts tests
	$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 12)'
	@[ "$$(head -n 1 .python-version)" = "$(VENV)" ] || { echo "lint: .python-version's first line is not $(VENV); update VENV in the Makefile"; exit 2; }

doclint:
	$(PYTHON) scripts/doclint
	bash plugin/scripts/respeak-check.sh

# scripts/{agentik,hygiene,bounded} are vendored from agentik-commons by its `scripts/sync`
# (agentik-r1 7.3), which writes their sums to scripts/vendored.sha256; a re-sync moves the
# files and that file together. scripts/doclint stays pinned here until r2 makes it one copy.
# hygiene reads the private terms from the private list (`$AGENTIK_HYGIENE_PRIVATE`, else the XDG
# config path), never the repo. Its exits: 0 clean, 1 a hit, 2 usage.
DOCLINT_SHA = 26eaf2c84aadb822f8d63a0257b063afcc0ba6d9bbcf1d2d856abe4c6388341f

hygiene:
	@shasum -a 256 -c --status scripts/vendored.sha256 || { echo "hygiene: scripts/agentik, scripts/hygiene or scripts/bounded differ from scripts/vendored.sha256; re-run agentik-commons scripts/sync"; exit 2; }
	@printf '%s  %s\n' $(DOCLINT_SHA) scripts/doclint | shasum -a 256 -c --status || { echo "hygiene: scripts/doclint differs from its pinned copy"; exit 2; }
	$(PYTHON) scripts/hygiene

## plugin-version-check: red when a file under plugin/ changed after the commit that last moved plugin.json's version (conventions section 7); exits 0, 1, 2
plugin-version-check:
	$(PYTHON) scripts/plugin-version-check

# README.md is rendered from design/readme/source.md (conventions section 6); edit the source.
# The render is an editorial pass, not a summary: design/readme/contract.txt is its contract, and
# scripts/readme-render.sh moves it over README.md only after respeak-verify-edit.py passes.
readme:
	bash scripts/readme-render.sh

readme-fresh:
	bash scripts/readme-fresh.sh

validate:
	@if command -v $(CLAUDE) >/dev/null 2>&1; then $(DEADLINE) 60 $(CLAUDE) plugin validate plugin/ </dev/null; \
	else echo "validate: skipped, no $(CLAUDE) on PATH"; fi

# One line per check: python, claude, marketplace, plugin, provider, config (conventions section 3).
doctor:
	bash plugin/scripts/respeak-doctor.sh

# Install the plugin from the `agentik` marketplace (agentik-r1 5.2, conventions section 2). It never
# adds or removes a marketplace: with `agentik` known it installs respeak@agentik, or updates it when
# listed; without it, it prints the line that adds the marketplace and exits 2. respeak puts no
# command on PATH in r1 (agentik-r1 D4).
install:
	@command -v $(CLAUDE) >/dev/null 2>&1 || { echo "install: no claude CLI at CLAUDE=$(CLAUDE); set CLAUDE=/path/to/claude"; exit 2; }
	@mkts="$$($(CLAUDE) plugin marketplace list --json)" || exit 2; \
	known="$$(printf '%s' "$$mkts" | $(PYTHON) -c 'import json,sys; print(any(m.get("name")=="agentik" for m in json.load(sys.stdin)))')" || exit 2; \
	if [ "$$known" != True ]; then \
	  echo "install: the agentik marketplace is not known to claude; add it, then run make install again:"; \
	  echo "  claude plugin marketplace add agentik-dev/agentik-commons"; \
	  exit 2; \
	fi; \
	listed="$$($(CLAUDE) plugin list --json | $(PYTHON) -c 'import json,sys; print(any(p.get("id")=="respeak@agentik" for p in json.load(sys.stdin)))')" || exit 2; \
	if [ "$$listed" = True ]; then \
	  $(CLAUDE) plugin update respeak@agentik; \
	else \
	  $(CLAUDE) plugin install respeak@agentik; \
	fi
