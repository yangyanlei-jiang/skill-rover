"""JSON command-line interface for a skill's host agent."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, github, lifecycle
from .catalog import scan
from .integration import hook, integrate
from .store import Store

def parser():
    p = argparse.ArgumentParser(description="SkillRover: discover skills and manage safe reassessment.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--state-dir", default=".skill-rover", help="persistent state directory (default: project .skill-rover)")
    commands = p.add_subparsers(dest="command", required=True)
    c = commands.add_parser("scan", help="inspect metadata without loading instructions")
    c.add_argument("roots", nargs="+")
    c = commands.add_parser("search", help="search public GitHub candidate repositories")
    c.add_argument("query")
    c.add_argument("--limit", type=int, default=5)
    c = commands.add_parser("fetch", help="download an immutable skill for inspection, without executing it")
    c.add_argument("repository")
    c.add_argument("--ref", default="HEAD")
    c.add_argument("--subdir", default="")
    c.add_argument("--output", required=True)
    c = commands.add_parser("install", help="copy a reviewed and authorized bundle into owned storage")
    c.add_argument("source")
    c.add_argument("--reviewed", action="store_true", required=True, help="confirm content/dependencies were reviewed and installation is authorized")
    c.add_argument("--origin")
    c.add_argument("--revision")
    c.add_argument("--review-hours", type=float, default=24)
    c = commands.add_parser("load", help="return instructions and record session usage")
    c.add_argument("id")
    c.add_argument("--session", required=True)
    c.add_argument("--explicit", action="store_true")
    c = commands.add_parser("release", help="release usage when a task/session has finished")
    c.add_argument("--session", required=True)
    c.add_argument("--id")
    commands.add_parser("due", help="list reviews due; does not mark them complete")
    commands.add_parser("status", help="show managed entries, usage, and review history")
    commands.add_parser("cleanup", help="retry archiving already retired owned bundles")
    c = commands.add_parser("mark-due", help="request early review after a failure or task change")
    c.add_argument("id")
    c.add_argument("--reason", required=True)
    c = commands.add_parser("keep", help="record a completed comparison that retained the current skill")
    c.add_argument("id")
    c.add_argument("--reason", required=True)
    c = commands.add_parser("replace", help="switch to a verified candidate and archive the owned old skill")
    c.add_argument("current")
    c.add_argument("candidate")
    c.add_argument("--evidence", required=True)
    c.add_argument("--explicit", action="store_true")
    c = commands.add_parser("integrate", help="install router and deadline hooks in an explicitly selected project")
    c.add_argument("--project", required=True)
    c.add_argument("--host", choices=["codex", "claude", "both"], required=True)
    commands.add_parser("hook", help="handle native JSON events on stdin")
    return p

def dispatch(a):
    store = Store(a.state_dir)
    if a.command == "scan":
        return scan(a.roots)
    if a.command == "search":
        return github.search(a.query, a.limit)
    if a.command == "fetch":
        return github.fetch(a.repository, a.ref, a.subdir, a.output)
    if a.command == "install":
        return lifecycle.install(store, a.source, a.origin, a.revision, a.review_hours * 3600)
    if a.command == "load":
        result = lifecycle.load(store, a.id, a.session, explicit=a.explicit)
        result["instructions"] = Path(result["path"]).read_text(encoding="utf-8")
        return result
    if a.command == "release":
        return lifecycle.release(store, a.session, a.id)
    if a.command == "due":
        return lifecycle.due(store)
    if a.command == "status":
        return store.read()
    if a.command == "cleanup":
        return lifecycle.cleanup(store)
    if a.command == "mark-due":
        return lifecycle.mark_due(store, a.id, a.reason)
    if a.command == "keep":
        return lifecycle.keep(store, a.id, a.reason)
    if a.command == "replace":
        evidence = json.loads(Path(a.evidence).read_text(encoding="utf-8"))
        return lifecycle.replace(store, a.current, a.candidate, evidence, explicit=a.explicit)
    if a.command == "integrate":
        hosts = ["codex", "claude"] if a.host == "both" else [a.host]
        return [integrate(a.project, h, store.root, Path(__file__).resolve().parents[2]) for h in hosts]
    if a.command == "hook":
        data = sys.stdin.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError("hook input exceeds 1 MiB")
        return hook(json.loads(data), store)
    raise ValueError("unsupported command")

def main():
    args = parser().parse_args()
    try:
        result = dispatch(args)
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        # Hook failures remain fail-open; callers still get actionable diagnostics.
        if args.command == "hook":
            print("{}")
            return 0
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0

