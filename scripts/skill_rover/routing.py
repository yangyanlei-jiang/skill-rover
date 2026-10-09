"""Per-turn routing observations and enrollment of actually selected skills."""
from pathlib import Path
import uuid

from . import lifecycle
from .catalog import read_skill

_CURRENT = object()


def start(store, session, now=None):
    now, session = lifecycle._now(now), lifecycle._text(session, "session")
    with store.transaction() as state:
        sessions = state.setdefault("routing", {})
        previous = sessions.get(session, {})
        if previous.get("check_id") and previous.get("ended_at") is None:
            return dict(previous)
        current = {"checks": previous.get("checks", 0), "checked_at": now,
                   "check_id": uuid.uuid4().hex, "turn_id": None, "decision": "pending",
                   "reason": None, "selected_ids": [], "decided_at": None,
                   "reminded": False, "ended_at": None}
        sessions[session] = current
        return dict(current)


def end(store, session, now=None):
    now, session = lifecycle._now(now), lifecycle._text(session, "session")
    with store.transaction() as state:
        current = state.setdefault("routing", {}).setdefault(session, {"checks": 0})
        current["ended_at"] = now
        state["uses"].pop(session, None)
        state["notices"].pop(session, None)


def begin(store, session, turn=None, now=None):
    now, session = lifecycle._now(now), lifecycle._text(session, "session")
    with store.transaction() as state:
        sessions = state.setdefault("routing", {})
        previous = sessions.get(session, {})
        if previous.get("ended_at") is not None:
            raise ValueError("session has ended; wait for SessionStart")
        # Multiple hook sources can deliver the same Codex turn.
        if turn and previous.get("turn_id") == turn:
            return dict(previous)
        current = {"checks": previous.get("checks", 0) + 1, "checked_at": now,
                   "check_id": uuid.uuid4().hex, "turn_id": turn, "decision": "pending", "reason": None,
                   "selected_ids": [], "decided_at": None, "reminded": False, "ended_at": None}
        sessions[session] = current
        return dict(current)


def record(store, session, decision, reason, selected_ids=(), now=None, check_id=_CURRENT):
    now, session = lifecycle._now(now), lifecycle._text(session, "session")
    reason = lifecycle._text(reason, "reason")
    if decision not in ("selected", "none", "blocked"):
        raise ValueError("unknown routing decision")
    identities = list(dict.fromkeys(selected_ids))
    if (decision == "selected") != bool(identities):
        raise ValueError("selected decisions require managed identities; other decisions forbid them")
    with store.transaction() as state:
        sessions = state.setdefault("routing", {})
        current = sessions.setdefault(session, {"checks": 0, "checked_at": None, "turn_id": None})
        if current.get("ended_at") is not None:
            raise ValueError("session has ended")
        expected = current.get("check_id") if check_id is _CURRENT else check_id
        stale = expected != current.get("check_id")
        for identity in identities:
            entry = lifecycle._entry(state, identity)
            if entry["status"] == "retired" or identity not in state["uses"].get(session, []):
                raise ValueError("selection must be loaded by this session")
        if not stale and decision == "selected" and current.get("decision") == "selected":
            identities = list(dict.fromkeys(current["selected_ids"] + identities))
        state["history"].append({"action": "route", "session": session, "decision": decision,
                                 "reason": reason, "selected_ids": identities, "at": now,
                                 "check_id": expected, "recorded": not stale})
        if stale:
            return {"recorded": False, "check_id": expected, "current_check_id": current.get("check_id")}
        current.update(decision=decision, reason=reason, selected_ids=identities, decided_at=now)
        return {**current, "recorded": True}


def remind_pending(store, session):
    with store.transaction() as state:
        current = state.get("routing", {}).get(session)
        if not current or current.get("ended_at") is not None or current.get("decision") != "pending" or current.get("reminded"):
            return False
        current["reminded"] = True
        return True


def use(store, source, session, reason, origin=None, revision=None,
        review_seconds=lifecycle.DEFAULT_REVIEW_SECONDS, explicit=False, now=None, check_id=_CURRENT):
    if now is not None:
        now = lifecycle._now(now)
    session = lifecycle._text(session, "session")
    reason = lifecycle._text(reason, "reason")
    current = store.read().get("routing", {}).get(session, {})
    if current.get("ended_at") is not None:
        raise ValueError("session has ended")
    check_id = current.get("check_id") if check_id is _CURRENT else check_id
    if check_id != current.get("check_id"):
        raise ValueError("routing check changed before enrollment")
    source = Path(source).expanduser().resolve()
    if source.name == "SKILL.md":
        source = source.parent
    info = read_skill(source)
    if not info["implicit"] and not explicit:
        raise ValueError("skill requires explicit invocation")
    # CLI requires a review/authorization attestation before reaching this helper.
    entry = lifecycle.install(store, source, origin, revision, review_seconds, now=now)
    loaded = lifecycle.load(store, entry["id"], session, explicit=explicit, now=now, expected_check=check_id)
    decision = record(store, session, "selected", reason, [entry["id"]], now=now, check_id=check_id)
    loaded["routing_recorded"] = decision["recorded"]
    return loaded


def status(store, now=None):
    now = lifecycle._now(now)
    pending = lifecycle.cleanup(store)
    state = store.read()
    active = [entry for entry in state["entries"].values() if entry["status"] != "retired"]
    schedule = []
    for entry in active:
        anchor = entry["reviewed_at"] if entry["reviewed_at"] is not None else entry["loaded_at"]
        deadline = None if anchor is None else anchor + entry["review_seconds"]
        sessions = [session for session, ids in state["uses"].items() if entry["id"] in ids]
        schedule.append({"id": entry["id"], "name": entry["name"], "source": entry["source"],
                         "first_loaded_at": entry["loaded_at"],
                         "last_used_at": entry.get("last_used_at", entry["loaded_at"]),
                         "next_review_at": deadline, "in_use_by": sessions,
                         "due": deadline is not None and (bool(entry.get("review_reason")) or now >= deadline)})
    schedule.sort(key=lambda row: (row["next_review_at"] is None, row["next_review_at"] or 0, row["id"]))
    routing = state.get("routing", {})
    deadlines = [row["next_review_at"] for row in schedule if row["next_review_at"] is not None]
    return {**state, "cleanup_pending": pending, "tracking_scope": "managed_loads",
            "review_schedule": schedule,
            "summary": {"managed_active": len(active),
                        "ever_loaded": sum(entry["loaded_at"] is not None for entry in state["entries"].values()),
                        "in_use": sum(bool(row["in_use_by"]) for row in schedule),
                        "routing_checks": sum(item["checks"] for item in routing.values()),
                        "pending_routes": sum(item.get("decision") == "pending" and item.get("ended_at") is None for item in routing.values()),
                        "next_review_at": min(deadlines) if deadlines else None}}
