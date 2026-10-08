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
| SessionStart | Supplies the actual session id and state path; adds a due reminder when applicable |
| UserPromptSubmit | Checks review deadlines before a new user turn |
| PostToolUse | Checks during ongoing work; replacement still waits for a safe boundary |
| SessionEnd | Releases that session's usage records |

Command hooks receive JSON on stdin and emit native hookSpecificOutput.additionalContext. Malformed input/errors are reported to stderr and fail open with {}. They do not run candidate content or perform replacement. They retry unfinished archival of already retired owned copies; damaged copies are preserved and reported by status/cleanup. Due reminders are throttled to once per five minutes per session; this throttle does not advance review deadlines.

Review and trust the generated hook definitions in the host. Codex does not run untrusted project/plugin hooks simply because a skill is installed. If hooks are unsupported or disabled, the core skill still works, but deadline checking must be requested at task boundaries.

## Instructions-only integration

Install this root directory using your existing skill installer, then invoke the skill explicitly. To encourage implicit routing, you may add a concise project rule such as:

“Use skill-rover when choosing among overlapping skills, when a needed capability is missing, or when a managed review is due. Ordinary tasks do not require a skill.”

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
