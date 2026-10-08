# SkillRover Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. Steps use checkbox syntax.

**Goal:** Ship an installable skill with tested discovery, evidence-based selection guidance and safe timed reassessment/replacement.
**Architecture:** Host-model semantic decisions; small Python helpers for deterministic operations, persistent state and project hooks.
**Tech Stack:** Python 3.10+, PyYAML 6, standard-library unittest; no model SDK dependency.
**Spec:** ../specs/2026-10-08-skill-rover-design.md

## Global Constraints
- Default review interval is 86400 seconds.
- Repeated load never resets the review deadline.
- Never remove unmanaged source directories or replace an in-use skill.
- No remote content execution during discovery/import.
- Deadline execution is at the next host event; no idle wake-up guarantee.
- Explicit user authorization covers implementation, public repository creation and publishing this new project.
- Work in the new isolated repository; no existing project branch is affected.

## Review Focus
- Expired skills repeatedly loaded must remain due: tests/test_lifecycle.py.
- Forged/stale evidence, edited bundles and failed candidate checks: tests/test_lifecycle.py.
- Interrupted archival must preserve recovery and block stale loading: tests/test_lifecycle.py.
- Malicious archives and symlinked files must not escape extraction/management: tests/test_discovery.py.
- Hook merges must preserve existing settings and not duplicate themselves: tests/test_cli.py.

### Task 1: Catalog and managed lifecycle
Files: scripts/skill_rover/catalog.py, store.py, lifecycle.py; tests/test_catalog.py, tests/test_lifecycle.py.
Interfaces: read_skill(path)->dict, scan(roots)->dict, Store(directory).read()/transaction(); install(store, source, origin, revision)->record; load/release/due/keep/replace accept a Store and an injected now value for deterministic clock tests.
- [ ] Write real-file tests before implementation: load at 100; interval 60; reload at 159; due at 160 must include same id. Replace with live session must raise without changing either source or current record.
- [ ] Run python3 -m unittest discover -s tests -v; observe missing behavior.
- [ ] Implement bounded metadata reading, whole-tree digests, locking/atomic snapshots, owned copies, session usage, timer, evidence checks and recoverable retirement.
- [ ] Run the suite and commit the working core.

Example contract:
```python
old = install(store, fixture, review_seconds=60, now=0)
load(store, old["id"], "session-a", now=100)
load(store, old["id"], "session-a", now=159)
assert due(store, now=160)[0]["id"] == old["id"]
```

### Task 2: GitHub discovery and CLI
Files: scripts/skill_rover/github.py, cli.py; scripts/rover.py; tests/test_discovery.py, tests/test_cli.py.
Interfaces: search(query, limit)->list; fetch(repository, ref, subdir, destination)->manifest with resolved revision; CLI emits JSON and nonzero error statuses.
- [ ] Test ZIP traversal, oversized input, link entry and non-skill directories with locally generated archives.
- [ ] Implement repository search and immutable-commit archive inspection; use bounded HTTPS calls with optional GITHUB_TOKEN.
- [ ] Add scan/search/fetch/install/load/release/due/keep/replace/status CLI commands.
- [ ] Run subprocess CLI tests against temporary state and commit.

Example:
```python
result = subprocess.run([sys.executable, "scripts/rover.py", "--state-dir", state, "due"], capture_output=True, text=True)
assert result.returncode == 0
assert json.loads(result.stdout) == []
```

### Task 3: Native event integration
Files: scripts/skill_rover/integration.py; tests/test_cli.py; references/integration.md.
Interfaces: integrate(project, host, state_dir, router_root)->config; hook(payload, store)->JSON.
- [ ] Test ordinary versus due events, five-minute reminder throttle, SessionEnd release, and repeated integration with existing unrelated hooks.
- [ ] Implement SessionStart/UserPromptSubmit/PostToolUse/SessionEnd hooks and explicit project installation; preserve configuration.
- [ ] Validate generated host configuration and exercise hooks via subprocess.
- [ ] Attempt clean temporary-host smoke tests and record actual outcomes.

### Task 4: Skill, evaluations and public release
Files: SKILL.md, references/lifecycle.md, references/discovery.md, agents/openai.yaml, README.md, README.zh-CN.md, evals/cases.json, evals/report.md, .github/workflows/tests.yml, requirements.txt, LICENSE.
- [ ] Record baseline behavioral decisions before writing the skill.
- [ ] Write concise task-selection guidance with links to concrete CLI and lifecycle procedures.
- [ ] Define 30 concrete cases and acceptable outcomes; run with-skill independent behavior checks.
- [ ] Run format validation, all tests and end-to-end lifecycle walkthrough.
- [ ] Obtain independent code review; fix meaningful findings with regression tests.
- [ ] Create public yangyanlei-jiang/skill-rover, push verified commits, run CI and check the repository URL/visibility.

Completion: a usable public source repository, truthful test/evaluation record, and documented exact limits of host-driven timers and context retirement.

