"""Bounded, non-executing skill inspection."""
import hashlib
import os
import re
from pathlib import Path

import yaml

MAX_MANIFEST = 65536
MAX_BUNDLE = 16 * 1024 * 1024
MAX_FILES = 2000
SKIP = {".git", ".skill-rover", ".venv", "node_modules", "__pycache__"}

def _yaml(path):
    data = Path(path).read_bytes()
    if len(data) > MAX_MANIFEST:
        raise ValueError("metadata exceeds 64 KiB")
    try:
        return yaml.safe_load(data.decode("utf-8"))
    except (yaml.YAMLError, UnicodeError) as exc:
        raise ValueError("invalid UTF-8 YAML: " + str(exc)) from exc

def read_skill(path):
    root = Path(path).expanduser().resolve()
    manifest = root if root.name == "SKILL.md" else root / "SKILL.md"
    raw = manifest.read_bytes()
    if len(raw) > MAX_MANIFEST:
        raise ValueError("SKILL.md exceeds 64 KiB")
    text = raw.decode("utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md must start with YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("missing frontmatter closing delimiter")
    try:
        metadata = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as exc:
        raise ValueError("invalid YAML frontmatter") from exc
    if not isinstance(metadata, dict):
        raise ValueError("frontmatter must be an object")
    name, description = metadata.get("name"), metadata.get("description")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        raise ValueError("invalid skill name")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ValueError("description must contain 1–1024 characters")
    disabled = metadata.get("disable-model-invocation", False)
    if not isinstance(disabled, bool):
        raise ValueError("disable-model-invocation must be boolean")
    implicit = not disabled
    policy_file = manifest.parent / "agents" / "openai.yaml"
    if policy_file.exists():
        ui = _yaml(policy_file)
        if not isinstance(ui, dict):
            raise ValueError("openai.yaml must be an object")
        policy = ui.get("policy", {})
        if not isinstance(policy, dict):
            raise ValueError("invocation policy must be an object")
        allowed = policy.get("allow_implicit_invocation", True)
        if not isinstance(allowed, bool):
            raise ValueError("allow_implicit_invocation must be boolean")
        implicit = implicit and allowed
    return {"name": name, "description": description.strip(),
            "path": str(manifest), "implicit": implicit,
            "compatibility": metadata.get("compatibility", ""),
            "manifest_digest": hashlib.sha256(raw).hexdigest()}

def scan(roots, max_depth=5, max_directories=2000):
    skills, errors, seen = [], [], set()
    visited = 0
    for root in roots:
        root = Path(root).expanduser().resolve()
        if root.is_file() and root.name == "SKILL.md":
            root = root.parent
        if not root.is_dir():
            errors.append({"path": str(root), "error": "skill root does not exist"})
            continue
        for directory, dirs, files in os.walk(root, followlinks=False):
            visited += 1
            if visited > max_directories:
                errors.append({"path": str(root), "error": "directory scan limit reached"})
                return {"skills": skills, "errors": errors}
            current = Path(directory)
            depth = len(current.relative_to(root).parts)
            dirs[:] = sorted(d for d in dirs if d not in SKIP and not (current / d).is_symlink()) if depth < max_depth else []
            if "SKILL.md" not in files:
                continue
            manifest = (current / "SKILL.md").resolve()
            if manifest in seen:
                continue
            seen.add(manifest)
            try:
                skills.append(read_skill(current))
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append({"path": str(manifest), "error": str(exc)})
    return {"skills": skills, "errors": errors}

def bundle_digest(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("bundle must be a real directory")
    digest = hashlib.sha256()
    size = count = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        current = Path(directory)
        for name in dirs + files:
            if (current / name).is_symlink():
                raise ValueError("bundle symlinks are not allowed")
        dirs[:] = sorted(d for d in dirs if d not in SKIP)
        for name in sorted(files):
            file = current / name
            if not file.is_file():
                raise ValueError("bundle contains a non-regular file")
            count += 1
            file_size = file.stat().st_size
            size += file_size
            if count > MAX_FILES or size > MAX_BUNDLE:
                raise ValueError("bundle size or file-count limit exceeded")
            relative = file.relative_to(root).as_posix().encode("utf-8")
            digest.update(len(relative).to_bytes(4, "big"))
            digest.update(relative)
            digest.update(file_size.to_bytes(8, "big"))
            with file.open("rb") as stream:
                for chunk in iter(lambda: stream.read(65536), b""):
                    digest.update(chunk)
    return digest.hexdigest()

