"""Public GitHub discovery. Retrieved bytes remain untrusted data."""
import io
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

from .catalog import MAX_BUNDLE, MAX_FILES, bundle_digest, read_skill

MAX_DOWNLOAD = 32 * 1024 * 1024

def validate_repository(repository):
    if not isinstance(repository, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*", repository):
        raise ValueError("repository must be owner/repo on github.com")
    return repository

def _download(url, authenticated=False, limit=MAX_DOWNLOAD):
    headers = {"User-Agent": "SkillRover/0.1", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if authenticated and token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("download exceeds size limit")
    return data

def _json(url):
    return json.loads(_download(url, authenticated=True, limit=2 * 1024 * 1024))

def search(query, limit=5):
    if not isinstance(query, str) or not query.strip():
        raise ValueError("search query is required")
    if not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    params = urllib.parse.urlencode({"q": query.strip() + " skill", "per_page": limit})
    response = _json("https://api.github.com/search/repositories?" + params)
    return [{"repository": item["full_name"], "url": item["html_url"],
             "description": item.get("description"), "candidate_only": True}
            for item in response.get("items", [])]

def _parts(value):
    if not isinstance(value, str) or "\\" in value:
        raise ValueError("invalid archive path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or any(":" in p for p in path.parts):
        raise ValueError("unsafe archive path")
    return path.parts

def extract_skill(data, subdirectory, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination already exists")
    subset = _parts(subdirectory)
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("archive download exceeds size limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid ZIP archive") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > 10000:
            raise ValueError("archive entry limit exceeded")
        roots, selected, seen = set(), [], set()
        total = 0
        for info in infos:
            parts = _parts(info.filename)
            if not parts:
                continue
            roots.add(parts[0])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("archive links and special files are forbidden")
            if parts in seen:
                raise ValueError("duplicate archive path")
            seen.add(parts)
            relative = parts[1:]
            if relative[:len(subset)] != subset or info.is_dir():
                continue
            relative = relative[len(subset):]
            if not relative:
                continue
            total += info.file_size
            selected.append((info, relative))
            if total > MAX_BUNDLE or len(selected) > MAX_FILES:
                raise ValueError("selected skill exceeds bundle size limit")
        if len(roots) != 1 or not selected:
            raise ValueError("archive must contain one repository root and a skill")
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".skill-rover-fetch-", dir=destination.parent))
        try:
            for info, parts in selected:
                target = staging.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                target.chmod(0o755 if (info.external_attr >> 16) & 0o111 else 0o644)
            if not (staging / "SKILL.md").is_file():
                raise ValueError("selected directory does not contain SKILL.md")
            record = read_skill(staging)
            digest = bundle_digest(staging)
            os.rename(staging, destination)
            return {**record, "path": str(destination.resolve() / "SKILL.md"), "digest": digest}
        finally:
            if staging.exists():
                shutil.rmtree(staging)

def fetch(repository, ref, subdirectory, destination):
    repository = validate_repository(repository)
    if not isinstance(ref, str) or not ref.strip():
        raise ValueError("a branch, tag or commit is required")
    encoded = urllib.parse.quote(ref, safe="")
    commit = _json("https://api.github.com/repos/" + repository + "/commits/" + encoded)
    revision = commit.get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("GitHub did not resolve an immutable commit")
    data = _download("https://codeload.github.com/" + repository + "/zip/" + revision)
    record = extract_skill(data, subdirectory, destination)
    return {**record, "repository": repository, "revision": revision,
            "source": "https://github.com/" + repository + "/tree/" + revision + ("/" + subdirectory if subdirectory else ""),
            "review_required": True}
