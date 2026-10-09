# SkillRover

**Find suitable skills. Reassess them as your work changes.**

[中文](README.zh-CN.md) · [Lifecycle](references/lifecycle.md) · [Integration](references/integration.md) · [Evaluation](evals/README.md)

SkillRover is an installable **Agent Skill that helps agents choose and use other skills**. It works with Codex and Claude Code: prefer installed capabilities, inspect external candidates when needed, load only relevant instructions, and verify the task's result.

Its optional Python helpers add persistent review deadlines and safe replacement of managed skills. The host agent makes semantic judgments; the helper enforces identities, ownership, integrity and active-use checks.

## Quick start

Python **3.10+** and Git are required for this setup.

```bash
git clone https://github.com/yangyanlei-jiang/skill-rover.git
cd skill-rover
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/rover.py integrate --project /absolute/path/to/your-project --host both
```

On Windows use `.venv\Scripts\python.exe`; creating skill symlinks requires Developer Mode or equivalent permission. Keep the cloned checkout and its virtual environment: the generated hooks refer to those paths. Windows hook commands are generated, but native Windows host execution has not been verified.

Use `--host codex` or `--host claude` for a single host. This explicit command installs the router and appends project hooks, preserving unrelated settings. Review and trust the hooks in your host; restart the host if changes do not appear.

**Integration defaults state to the target project's `.skill-rover`.** Other commands default to the current directory's `.skill-rover`. You can choose an explicit location:

```bash
.venv/bin/python scripts/rover.py --state-dir /absolute/path/to/your-project/.skill-rover integrate --project /absolute/path/to/your-project --host both
```

After integration, describe the task normally: “Analyze the payment flow's concurrency issues and add tests.” Prompt hooks request routing for nontrivial multi-step work, complex debugging and specialized artifacts, even with an empty managed catalog. The agent checks installed skills first and uses external discovery for missing capabilities. Reviewed, authorized selections use the enrollment bridge to start tracking. Simple tasks may use no skill. Explicit `$skill-rover` (Codex) or `/skill-rover` (Claude Code) remains a fallback.

Hooks supply instructions; the host model still judges and executes the workflow. `status` exposes pending routing checks, recorded decisions and next review times. Native invocation outside the managed protocol is not counted, so an empty managed table is not proof that no skill was used.

The root `SKILL.md` can also be installed with your existing Agent Skills installer. Instructions-only use does not require Python. **Timed lifecycle helpers and event hooks require the Python setup above.**

## What it does

- Uses task outcomes, platform constraints and real tool availability to compare skills.
- Starts with the host's installed catalog; GitHub search discovers candidate repositories when a capability is missing.
- Reads metadata first, then only selected instructions and resources.
- Keeps exact source identities for same-name skills and respects explicit-only invocation.
- Tracks managed skills across sessions and reassesses them after a configurable interval.
- Switches only after replacement validation, then archives the old owned bundle outside the active catalog.
- Leaves ordinary questions alone when no skill is useful.

## Reassessment policy

The default is **24 hours from first load**, not installation or last use. Loading the same skill again does not postpone review. An actual completed review restarts the interval. A task change or failed execution can request immediate review.

24 hours is a configurable starting point, not a measured universal optimum: it avoids repeatedly searching an ecosystem during one task while revisiting long-lived integrations daily. Use `install --review-hours 168` for a stable weekly cadence, or `--review-hours 1` during active experimentation. Change these based on measured replacement benefit and review cost.

Hooks check on session start, prompt submission and after tool use. **The host must be running and produce an event.** A closed host cannot wake itself; an idle deadline is processed on the next event. A reminder is not a completed evaluation. Offline discovery leaves the current skill and its review deadline intact.

A currently used skill cannot be replaced. Session usage is released when the task ends, and SessionEnd releases that session's remaining usage. After a crashed session, explicitly release its id only after confirming it has ended.

## Ownership and retirement

Helpers manage copies under the selected state directory. They never delete source skill directories, global user installations, or SkillRover itself.

Replacement validates both full-tree hashes, identity-bound evidence, successful checks and active sessions. The old bundle becomes retired in an atomic state update, then moves to the archive. Interrupted archival is retryable with `cleanup`. Archived bundles are excluded from the managed catalog.

This does not erase text from a model's conversation. The agent stops following retired instructions at a safe task boundary. Native host installations outside the managed store remain under the user's control.

## CLI

Run `python scripts/rover.py --help`; every command emits JSON.

| Command | Purpose |
| --- | --- |
| `scan ROOT ...` | Read bounded local metadata; report invocation policy and exact paths |
| `search QUERY` | Search public GitHub repository candidates |
| `fetch OWNER/REPO --ref REF --subdir PATH --output DIR` | Resolve an immutable commit and extract a skill for inspection |
| `install DIR --reviewed` | Install an inspected, authorized owned copy |
| `use DIR --reviewed --session SESSION --reason TEXT` | Enroll, load and record a selected skill in one operation |
| `record-route --session SESSION --decision none\|blocked --reason TEXT` | Explain a turn without managed skill usage |
| `load ID --session SESSION` | Return managed instructions and record usage |
| `release --session SESSION [--id ID]` | Finish usage |
| `due` / `status` | Read review deadlines or persisted state |
| `mark-due ID --reason TEXT` | Request early reassessment |
| `keep ID --reason TEXT` | Record a completed comparison retaining a skill |
| `replace OLD NEW --evidence FILE` | Apply a verified replacement |
| `cleanup` | Retry retiring already superseded bundles |
| `integrate --project DIR --host HOST` | Add project skill installation and native event hooks |

Place `--state-dir PATH` **before** the command and use the same absolute path throughout a project. Never pipe external candidate content into a shell.

## Development and validation

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python examples/lifecycle_demo.py
```

Tests exercise real temporary files, clock boundaries, ownership, archive handling, CLI subprocesses and hook configuration. CI covers supported Python versions on Linux and macOS. See [evaluation notes](evals/README.md) for behavioral cases and the difference between helper tests and real host runs.

The project does not claim statistically proven improvement over native model selection. Initial baseline checks already handled common selection rules well. The reproducible addition is the managed lifecycle protocol and its deterministic enforcement.

## Format and platform references

- [Agent Skills specification](https://agentskills.io/specification)
- [Codex skills](https://learn.chatgpt.com/docs/build-skills) and [hooks](https://learn.chatgpt.com/docs/hooks)
- [Claude Code skills](https://code.claude.com/docs/en/skills) and [hooks](https://code.claude.com/docs/en/hooks)

MIT licensed. No telemetry or external model API is included.
