# SkillRover v0.1 design

Approved scope: a cross-platform meta-skill that discovers, selects and uses suitable skills; installed skills first, GitHub discovery when needed. The user approved implementation and public repository creation on 2026-10-08, including automatic reassessment and replacement after a fixed period from loading.

## Product contract
The root SKILL.md is installable. The host agent makes semantic selection using task outcome, constraints, availability and evidence. Python helpers perform cataloging, GitHub retrieval, managed installation, durable lifecycle bookkeeping and event integration. No separate model API, vector database or daemon is required.

## Lifecycle
Default review interval: 86400 seconds (24 hours), configurable. This is an engineering starting point, not an empirically optimal interval. First successful instruction load sets loaded_at. Repeated loads do not postpone a deadline. A completed reassessment (keep or replacement) starts the next period. Task changes and execution failure also trigger review immediately.

Hooks check deadlines on SessionStart, UserPromptSubmit and PostToolUse, and release usage on SessionEnd. Due checks are event-driven: a stopped host cannot wake itself, and idle wall-clock deadlines are handled on the next host event. Hooks only inject a bounded reminder; they never install, execute remote code, delete skills, or claim a semantic assessment occurred. Offline/failed reviews stay due. Throttle repeated reminders for five minutes without marking a review completed.

Register loads using a session id; release after the skill's task ends. Replacement cannot retire a skill that any session is using. A failed/crashed session requires explicit release after verifying the session is finished; do not silently expire usage leases.

## Storage and ownership
State lives under a project-local .skill-rover by default, overridable with --state-dir. Atomic JSON snapshots plus a cross-platform process lock protect transitions. Skill bundles are copied into a managed packages directory, immutable by convention and checked by a full-tree SHA256. Unmanaged source directories are never deleted. Replaced owned bundles move out of the active managed catalog into an archive after a durable state transition. Retry interrupted archive cleanup on the next operation. A new bundle must be readable and verified before retiring the old one. Original source copies and the router itself cannot be automatically uninstalled.

State distinguishes installed, loaded, reviewed, active, retired; discovery alone does not start the review clock. Same-name skills preserve exact source/path identity. Invocation restrictions are respected. Native disabled skills are not made invocable through raw-file fallback.

## Evidence
A replacement evidence JSON binds current and candidate ids and full-tree digests, a task, reason, decision=replace, and non-empty passed checks with observed results. Failed checks prevent replacement. Both the agent and helpers verify compatibility; helpers cannot prove semantic superiority or truth of agent-supplied observations. No popularity-only replacement and no invented confidence scores.
Keeping a skill likewise records task/reason and reschedules the timer only after an actual comparison. Reviews and replacements are recorded in the state history.

## Discovery
Prefer host-provided catalogs. The optional scanner reads bounded SKILL.md metadata from explicit roots and reports parser errors, original paths, fingerprints and invocation restrictions. It does not treat lexical scores as semantic verdicts.
GitHub repository search is a candidate-source lookup, not a claim that a repository contains an appropriate skill. Inspect a specific repository/subdirectory at an immutable commit. Download bounded GitHub archives without executing content; reject traversal, symlinks, malformed manifests and excessive sizes. Only an authorized, reviewed local bundle is copied into the managed store.

## Integration
Codex and Claude Code use the same core skill and state. An explicit integrate command installs the router into a project skill directory and adds command hooks while preserving unrelated configuration. Commands use the current Python executable and absolute paths. Generated examples follow each host's official current event schema (not the legacy Cursor hook schema).
Managed candidates are file-read activated through the router; they do not need a native slash-command entry. Retirement removes them from the managed catalog and archives files. It cannot erase instructions already in a model's conversation; at the safe task boundary the agent must stop following retired instructions.

## Acceptance
Real-file tests exercise scanner constraints, deadline boundaries, repeated load, keep/review behavior, usage protection, identity-bound evidence, failed validation, rollback/retry cleanup, archive traversal, state concurrency and integration idempotence.
A 30-case behavioral suite defines acceptable outcomes including no-skill cases. Run baseline and with-skill checks without reporting hypothetical results as measurements. Both installed CLIs should be smoke-tested where authentication permits; distinguish harness tests from full model runs.

## Sources
- https://agentskills.io/specification
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks

