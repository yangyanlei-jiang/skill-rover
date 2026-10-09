"""Managed ownership, review deadlines and evidence-bound replacement."""
import math
import os
import re
import shutil
import time
import uuid
from pathlib import Path

from .catalog import SKIP, bundle_digest, read_skill

DEFAULT_REVIEW_SECONDS = 86400
_UNBOUND = object()

def _now(now):
    value = time.time() if now is None else now
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError("time must be finite")
    return value

def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(field + " must be non-empty")
    return value.strip()

def _entry(state, identity):
    if not isinstance(identity, str) or not re.fullmatch(r"[a-f0-9]{32}", identity):
        raise ValueError("invalid managed skill id")
    record = state["entries"].get(identity)
    if not record or record.get("id") != identity:
        raise ValueError("unknown managed skill id")
    return record

def package_path(store, record, area="packages"):
    parent = store.root / area
    if parent.is_symlink():
        raise ValueError("managed directory must not be a symlink")
    path = parent / record["id"]
    if path.is_symlink():
        raise ValueError("managed package must not be a symlink")
    return path

def _checked(store, state, identity):
    record = _entry(state, identity)
    if record["status"] == "retired":
        raise ValueError("skill is retired")
    if record.get("owned") is not True:
        raise ValueError("skill is not owned by SkillRover")
    path = package_path(store, record)
    if bundle_digest(path) != record["digest"]:
        raise ValueError("managed bundle changed; inspect and reimport it")
    return record

def install(store, source, origin=None, revision=None, review_seconds=DEFAULT_REVIEW_SECONDS, now=None):
    now = _now(now)
    if isinstance(review_seconds, bool) or not isinstance(review_seconds, (float, int)) or not math.isfinite(review_seconds) or review_seconds <= 0:
        raise ValueError("review interval must be positive and finite")
    source = Path(source).expanduser().resolve()
    digest = bundle_digest(source)
    source_identity = origin or str(source)
    cleanup(store)
    with store.transaction() as state:
        for existing in state["entries"].values():
            if (existing["digest"] == digest and existing["source"] == source_identity
                    and existing["revision"] == revision and existing["status"] != "retired"):
                _checked(store, state, existing["id"])
                return dict(existing)
        identity = uuid.uuid4().hex
        record = {"id": identity, "digest": digest,
                  "owned": True, "source": source_identity,
                  "revision": revision, "installed_at": now, "loaded_at": None,
                  "reviewed_at": None, "review_seconds": review_seconds,
                  "status": "installed", "review_reason": None}
        target = package_path(store, record)
        target.parent.mkdir(parents=True, exist_ok=True)
        if source == target.parent.resolve() or source in target.parent.resolve().parents:
            raise ValueError("source cannot contain the managed store")
        try:
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(*SKIP), symlinks=True)
            info = read_skill(target)
            if bundle_digest(target) != digest:
                raise ValueError("source changed during installation")
            if info["name"] == "skill-rover":
                raise ValueError("the router cannot be managed as its own candidate")
            record.update(name=info["name"], implicit=info["implicit"])
            state["entries"][identity] = record
            state["history"].append({"action": "install", "id": identity, "at": now})
        except Exception:
            if target.exists():
                shutil.rmtree(target)
            raise
        return dict(record)

def load(store, identity, session, explicit=False, now=None, expected_check=_UNBOUND):
    now, session = _now(now), _text(session, "session")
    cleanup(store)
    with store.transaction() as state:
        current = state.get("routing", {}).get(session, {})
        if current.get("ended_at") is not None:
            raise ValueError("session has ended")
        if expected_check is not _UNBOUND and expected_check != current.get("check_id"):
            raise ValueError("routing check changed before skill load")
        record = _checked(store, state, identity)
        if not record["implicit"] and not explicit:
            raise ValueError("skill requires explicit invocation")
        if record["loaded_at"] is None:
            record["loaded_at"] = now
        record["last_used_at"] = now
        entries = state["uses"].setdefault(session, [])
        if identity not in entries:
            entries.append(identity)
        state["history"].append({"action": "load", "id": identity, "session": session, "at": now})
        return {**record, "path": str(package_path(store, record) / "SKILL.md")}

def release(store, session, identity=None):
    session = _text(session, "session")
    cleanup(store)
    with store.transaction() as state:
        if identity is None:
            state["uses"].pop(session, None)
        else:
            entries = state["uses"].get(session, [])
            state["uses"][session] = [item for item in entries if item != identity]
            if not state["uses"][session]:
                state["uses"].pop(session, None)
    return {"released": session, "id": identity}

def due_records(state, now):
    result = []
    for record in state["entries"].values():
        if record["status"] == "retired" or record["loaded_at"] is None:
            continue
        anchor = record["reviewed_at"] if record["reviewed_at"] is not None else record["loaded_at"]
        deadline = anchor + record["review_seconds"]
        if record.get("review_reason") or now >= deadline:
            sessions = [s for s, ids in state["uses"].items() if record["id"] in ids]
            result.append({**record, "due_at": deadline, "in_use_by": sessions})
    return sorted(result, key=lambda r: (r["due_at"], r["id"]))

def due(store, now=None):
    cleanup(store)
    return due_records(store.read(), _now(now))

def mark_due(store, identity, reason, now=None):
    now, reason = _now(now), _text(reason, "reason")
    cleanup(store)
    with store.transaction() as state:
        record = _checked(store, state, identity)
        if record["loaded_at"] is None:
            raise ValueError("load the skill before marking a review due")
        record["review_reason"] = reason
        state["history"].append({"action": "review-requested", "id": identity, "at": now, "reason": reason})
    return dict(record)

def keep(store, identity, reason, now=None):
    now, reason = _now(now), _text(reason, "reason")
    cleanup(store)
    with store.transaction() as state:
        record = _checked(store, state, identity)
        if record["loaded_at"] is None:
            raise ValueError("cannot review a skill that has not been loaded")
        record["reviewed_at"], record["review_reason"] = now, None
        state["history"].append({"action": "keep", "id": identity, "at": now, "reason": reason})
    return dict(record)

def _evidence(evidence, old, candidate):
    if not isinstance(evidence, dict) or evidence.get("decision") != "replace":
        raise ValueError("replacement evidence is required")
    for key, wanted in [("current_id", old["id"]), ("current_digest", old["digest"]),
                        ("candidate_id", candidate["id"]), ("candidate_digest", candidate["digest"])]:
        if evidence.get(key) != wanted:
            raise ValueError("evidence does not match " + key)
    _text(evidence.get("task"), "evidence.task")
    _text(evidence.get("reason"), "evidence.reason")
    checks = evidence.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ValueError("evidence must contain actual validation checks")
    for check in checks:
        if not isinstance(check, dict) or check.get("passed") is not True:
            raise ValueError("candidate failed validation")
        _text(check.get("name"), "check.name")
        _text(check.get("observed"), "check.observed")

def cleanup(store):
    """The retired state is durable before files move; retries are idempotent."""
    pending = []
    with store.transaction() as state:
        for identity, record in state["entries"].items():
            _entry(state, identity)
            if record["status"] != "retired" or record.get("owned") is not True:
                continue
            try:
                source = package_path(store, record)
                target = package_path(store, record, "archive")
                if source.exists():
                    if bundle_digest(source) != record["digest"]:
                        pending.append({"id": identity, "error": "retired bundle changed; preserved"})
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    if target.exists():
                        pending.append({"id": identity, "error": "archive destination already exists; preserved"})
                        continue
                    os.replace(source, target)
            except (OSError, ValueError) as exc:
                pending.append({"id": identity, "error": str(exc) + "; preserved"})
    return pending

def replace(store, old_id, candidate_id, evidence, explicit=False, now=None):
    now = _now(now)
    if old_id == candidate_id:
        raise ValueError("replacement must be a different candidate")
    cleanup(store)
    with store.transaction() as state:
        old, candidate = _checked(store, state, old_id), _checked(store, state, candidate_id)
        if any(old_id in ids for ids in state["uses"].values()):
            raise ValueError("current skill is in use; switch at a safe task boundary")
        if not candidate["implicit"] and not explicit:
            raise ValueError("candidate requires explicit invocation")
        _evidence(evidence, old, candidate)
        old["status"] = "retired"
        old["replacement_id"] = candidate_id
        candidate["loaded_at"] = candidate["loaded_at"] if candidate["loaded_at"] is not None else now
        candidate["reviewed_at"], candidate["review_reason"] = now, None
        state["history"].append({"action": "replace", "old": old_id, "new": candidate_id,
                                 "at": now, "evidence": evidence})
        active = dict(candidate)
    return {"active": active, "retired": old_id, "cleanup_pending": cleanup(store)}
