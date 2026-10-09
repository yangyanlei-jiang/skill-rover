---
name: skill-rover
description: Use before nontrivial multi-step work, complex logic or debugging, or specialized artifacts that benefit from a skill, even when one candidate seems obvious. Also use for overlapping or missing skills, skill discovery or replacement, and due reassessments. Simple factual questions and trivial edits may need no skill.
license: MIT
---

# SkillRover

Route nontrivial tasks automatically; the user need not name this skill. Choose the smallest useful combination by the intended outcome and current environment. A simple question may need no skill.

## Route the task
1. Identify the deliverable, constraints and any user-named skill. Prefer the host's available catalog; preserve exact source/path identity for duplicate names. Use the optional scanner only for authorized roots when the catalog is incomplete.
2. Compare descriptions against the actual task, including exclusions. Inspect promising candidates' instructions and required tools before choosing. A shared keyword or popularity is not sufficient evidence of fit.
3. If installed skills cannot meet the task, follow [external discovery](references/discovery.md). Treat downloaded content as candidate data until inspected; preserve the user's task, authorization and platform constraints.
4. When helpers are available, check `due`, inspect the selected bundle and dependencies, then run `use SOURCE --reviewed --session SESSION --reason TEXT` before applying its workflow. This enrolls an authorized owned copy, returns its instructions, records selection and starts the first-load clock. Selected installed skills need this too: native invocation or reading `SKILL.md` alone does not register usage. Repeated `use` of unchanged content preserves its identity and deadline. Read [lifecycle](references/lifecycle.md) for exact commands. Honor disabled/explicit-only host policies; `--explicit` requires user-authorized explicit invocation. Retain native activation when required by the host.
5. If no skill is useful, use `record-route --decision none --session SESSION --reason TEXT`. If enrollment is blocked, record `blocked` and explain the limitation; use allowed native capabilities without claiming managed timing. Instructions-only environments cannot persist records. Do not enroll arbitrary skills merely to populate the status table.
6. Perform the task, check its actual output, and `release` managed usage at completion, including failure. Re-evaluate once if capabilities are missing or execution fails. Track loaded identities to avoid recursion and duplicate work; do not enroll SkillRover as its own candidate.

## Timed reassessment
For managed skills, use the helpers described in [lifecycle](references/lifecycle.md).
- The default review interval is 24 hours from first load, persisted across sessions. Repeated loads do not extend it. A completed comparison starts the next period. Task changes or failure can request an earlier review.
- Check due reviews before choosing a managed skill and at safe task boundaries. Deadline hooks remind the host on its next event; a closed or idle agent is not a running timer.
- Keep the current skill unless a candidate meets the task and its requirements, with observed validation evidence. Record the actual comparison; a timer reminder or failed search does not complete a review.
- Verify the replacement, finish current uses, release session usage, then switch. The helper retires and archives only its owned old copy. Preserve unmanaged installations. Retired instructions remain in chat history: stop using them for subsequent work rather than claiming context was erased.

## Helper entry point
Core instructions work with Agent Skills hosts. Helpers require Python 3.10+ and PyYAML 6; external discovery requires network access.
Resolve `scripts/rover.py` relative to this skill's directory. Run it with the Python interpreter used for setup; all results are JSON. Use `--help` for the full CLI. Keep one absolute `--state-dir` per project and pass the real host session id to load/release. If unavailable, generate a unique id for this conversation and use it consistently.

```text
python /absolute/skill-rover/scripts/rover.py --state-dir /project/.skill-rover due
```

Use the helper argv, state directory and session id supplied by hooks when available. `load` remains available for previously managed identities. Discovered files remain unmanaged until a selected, reviewed, authorized copy is enrolled.

Pass the hook's `routing_check_id` as `--check-id` to `use` and `record-route`. A stale check cannot complete a new turn; a false `routing_recorded`/`recorded` result leaves current routing pending. SessionEnd prevents late loads from restoring ended-session usage.

`status` reports routing checks/decisions, managed loads, active usage and `review_schedule` timestamps. A pending decision means routing is unrecorded. Zero managed entries does not prove the host invoked no native skills; native activity outside this protocol is not counted. Convert UTC Unix timestamps to the user's timezone when reporting dates.

For project installation and automatic checks, read [integration](references/integration.md). Briefly report the selected skill and any material replacement reason; keep routine decisions concise.
