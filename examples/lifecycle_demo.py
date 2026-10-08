"""A real-file lifecycle walkthrough with an injected clock; no network or waiting."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from skill_rover.lifecycle import due, install, load, release, replace
from skill_rover.store import Store

with tempfile.TemporaryDirectory(prefix="skill-rover-demo-") as directory:
    root = Path(directory)
    store = Store(root / "state")
    records = []
    for name in ("table-basic", "table-preserving"):
        source = root / name
        source.mkdir()
        (source / "SKILL.md").write_text(
            "---\nname: " + name + "\ndescription: Extract tabular values.\n---\nUse the supplied table fixture.",
            encoding="utf-8",
        )
        records.append(install(store, source, review_seconds=86400, now=0))
    old, new = records
    load(store, old["id"], "demo-session", now=100)
    load(store, old["id"], "demo-session", now=86499)
    assert not due(store, now=86499)
    assert due(store, now=86500)[0]["id"] == old["id"]
    # Demonstration-only observed criterion: the candidate bundle is readable.
    evidence = {"decision": "replace", "task": "demonstrate a verified bundle switch",
                "reason": "candidate bundle is readable; this is not a semantic quality benchmark",
                "current_id": old["id"], "current_digest": old["digest"],
                "candidate_id": new["id"], "candidate_digest": new["digest"],
                "checks": [{"name": "candidate manifest readable", "passed": True,
                            "observed": (store.root / "packages" / new["id"] / "SKILL.md").read_text()}]}
    release(store, "demo-session")
    result = replace(store, old["id"], new["id"], evidence, now=86501)
    assert not result["cleanup_pending"]
    assert (store.root / "archive" / old["id"] / "SKILL.md").is_file()
    assert (root / "table-basic" / "SKILL.md").is_file()
    print(json.dumps({"first_review_due_at": 86500, "reload_did_not_reset_deadline": True,
                      "new_skill": result["active"]["name"], "old_owned_copy_archived": True,
                      "original_source_preserved": True}))
