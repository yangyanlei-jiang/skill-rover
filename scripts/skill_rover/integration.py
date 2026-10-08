"""Explicit project integration and bounded, side-effect-free review reminders."""
import base64
import json
import shlex
import sys
from pathlib import Path

from .lifecycle import _now, cleanup, due_records, release
from .store import atomic_json

EVENTS = ("SessionStart", "UserPromptSubmit", "PostToolUse", "SessionEnd")
NOTICE_SECONDS = 300

def _handler(args, host, event):
    handler = {"type": "command", "timeout": 3 if event == "SessionEnd" else 10}
    if host == "claude":
        # Exec form avoids shell-dependent quoting on all supported platforms.
        handler.update(command=args[0], args=args[1:])
    else:
        handler["command"] = shlex.join(args)
        powershell = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in args) + "; exit $LASTEXITCODE"
        encoded = base64.b64encode(powershell.encode("utf-16-le")).decode("ascii")
        handler["commandWindows"] = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + encoded
    return handler

def integrate(project, host, state_dir, router_root):
    if host not in ("codex", "claude"):
        raise ValueError("host must be codex or claude")
    project, router_root = Path(project).resolve(), Path(router_root).resolve()
    if not (router_root / "SKILL.md").is_file():
        raise ValueError("router root must contain SKILL.md")
    folder = ".codex" if host == "codex" else ".claude"
    config_path = project / folder / ("hooks.json" if host == "codex" else "settings.json")
    skill_path = project / (".agents" if host == "codex" else ".claude") / "skills" / "skill-rover"
    if skill_path.exists() or skill_path.is_symlink():
        if not skill_path.is_symlink() or skill_path.resolve() != router_root:
            raise ValueError("an unrelated skill-rover installation already exists")
    if config_path.is_symlink():
        raise ValueError("refusing to rewrite a symlinked configuration")
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("existing hook configuration is not an object")
    args = [sys.executable, str(router_root / "scripts" / "rover.py"),
            "--state-dir", str(Path(state_dir).absolute()), "hook"]
    hooks = config.setdefault("hooks", {})
    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError("hook event must be a list")
        handler = _handler(args, host, event)
        present = any(any(h == handler for h in group.get("hooks", []))
                      for group in groups if isinstance(group, dict))
        if not present:
            groups.append({"hooks": [handler]})
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        if not skill_path.is_symlink():
            skill_path.symlink_to(router_root, target_is_directory=True)
            created = True
        atomic_json(config_path, config)
    except Exception:
        if created:
            skill_path.unlink()
        raise
    return {"host": host, "skill_path": str(skill_path), "config": str(config_path),
            "state_dir": str(Path(state_dir).absolute()),
            "note": "Review/trust these hooks in your host; restart if they are not detected."}

def hook(payload, store, now=None):
    now = _now(now)
    if not isinstance(payload, dict):
        raise ValueError("hook input must be an object")
    event, session = payload.get("hook_event_name"), payload.get("session_id")
    if event not in EVENTS:
        return {}
    if not isinstance(session, str) or not session:
        raise ValueError("hook session_id is required")
    cleanup(store)
    if event == "SessionEnd":
        release(store, session)
        with store.transaction() as state:
            state["notices"].pop(session, None)
        return {}
    context = ("SkillRover session_id (literal JSON): " + json.dumps(session) + "; state directory: "
               + json.dumps(str(store.root)) + ". Use these exact values with managed load/release commands. ")
    with store.transaction() as state:
        due = due_records(state, now)
        last = state["notices"].get(session)
        remind = bool(due) and (last is None or not 0 <= now - last < NOTICE_SECONDS)
        if remind:
            state["notices"][session] = now
    if not remind:
        if event != "SessionStart":
            return {}
        return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": context +
                "Use skill-rover when specialized skill selection is unclear or a review is due. Simple tasks may need no skill."}}
    # No downloaded descriptions, prompts or instructions enter developer context.
    text = context + ("SkillRover has managed skills due for reassessment. Load the installed skill-rover "
            "skill and run its due command for this project's state directory. Compare candidates "
            "against the current task, validate any replacement, and switch only at a safe task "
            "boundary after releasing usage. A reminder is not a completed review. "
            "If review cannot complete, keep the current skill and leave the review due.")
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
