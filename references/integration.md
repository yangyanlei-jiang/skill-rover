# Codex and Claude Code integration

## Project setup

From a persistent clone with dependencies installed, run:
```bash
.venv/bin/python scripts/rover.py --state-dir /absolute/project/.skill-rover integrate --project /absolute/project --host both
```

The command uses its current Python executable in hook commands and installs symlinks:
- Codex: .agents/skills/skill-rover; command hooks in .codex/hooks.json.
- Claude Code: .claude/skills/skill-rover; command hooks in .claude/settings.json.

Claude Code uses direct execution with an argument array, avoiding shell quoting differences. Codex uses a POSIX command plus a Windows PowerShell override. SessionEnd handlers use a three-second timeout to meet the Codex limit. The integration command defaults state to the target project's .skill-rover; other commands use the current directory unless --state-dir is supplied.

It preserves unrelated JSON fields and hook groups, and repeated identical integration does not add duplicate handlers. It refuses to overwrite unrelated existing installations. If you move the clone or Python environment, inspect and remove the previous SkillRover hook entries before integrating the new path.

Keep .skill-rover/ out of version control: it stores source locations, usage and evaluation evidence. The tool does not automatically change the target project's .gitignore; add that entry as appropriate.

## Event contract

| Event | Behavior |
| --- | --- |
| SessionStart | Supplies session id, helper argv, state path and automatic routing instructions |
| UserPromptSubmit | Always requests a skill-needs decision, records a pending check and checks deadlines, even with an empty catalog |
| PostToolUse | Reminds once per turn if routing is unrecorded, and checks due reviews; replacement waits for a safe boundary |
| SessionEnd | Releases that session's usage records |

Command hooks receive JSON on stdin and emit native hookSpecificOutput.additionalContext. Malformed input/errors are reported to stderr and fail open with {}. They do not run candidate content or perform replacement. They retry unfinished archival of already retired owned copies; damaged copies are preserved and reported by status/cleanup. Due reminders are throttled to once per five minutes per session; this throttle does not advance review deadlines.

Review and trust the generated hook definitions in the host. Codex does not run untrusted project/plugin hooks simply because a skill is installed. If hooks are unsupported or disabled, the core skill still works, but deadline checking must be requested at task boundaries.

Routing uses the host's semantic judgment, not a hook's keyword heuristic. The host uses `use` to enroll reviewed, authorized selections or `record-route` to explain none/blocked decisions. Prompt content is not stored. The five-minute due throttle never suppresses a new prompt's routing check. Duplicate delivery of a Codex `turn_id` does not reset a completed decision.

For user-wide hooks without `--state-dir`, the helper uses the payload's absolute `cwd` to select that project's `.skill-rover`; explicit state takes precedence. Hooks/rules instruct the model to route automatically but do not forcibly execute its decisions. `status.routing` exposes unrecorded checks instead of claiming they succeeded.

## Instructions-only integration

Install this root directory using your existing skill installer. Automatic discovery is enabled; explicit invocation is a fallback. For hosts without prompt hooks, add a project rule such as:

“Before nontrivial multi-step tasks, complex debugging or specialized artifacts, use skill-rover to select suitable skills, even when a candidate is obvious. Register reviewed, authorized selections with its use helper. Simple questions may need no skill.”

A prompt rule increases discoverability; it does not guarantee automatic activation or provide a background timer.

## Host limitations

The core skill is portable. Additional hooks are host-specific and require Python in the local execution environment. A cloud agent cannot access a user's local installation unless the files and dependencies are provisioned there.

Managed candidates are loaded by returning their actual instructions through the helper, with invocation restrictions retained. They are not installed as native slash-menu entries. Unmanaged/native skills should be activated through the host's own mechanism.

SkillRover cannot remove text already sent to a model, wake a stopped host, grant permissions, or reliably infer that an arbitrary crashed session is finished. These are explicit host boundaries.

References checked on 2026-10-08:
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/hooks
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks
