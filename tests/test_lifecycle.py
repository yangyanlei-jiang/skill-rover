import json
from common import Fixture

class LifecycleTests(Fixture):
    def setUp(self):
        super().setUp()
        self.life = self.module("lifecycle")
        self.store = self.module("store").Store(self.base / "state")

    def install(self, name="pdf-extract", interval=60):
        return self.life.install(self.store, self.skill(name), review_seconds=interval, now=0)

    def evidence(self, old, new, passed=True):
        return {"decision": "replace", "task": "extract a PDF table",
                "reason": "candidate preserves table columns in the same sample",
                "current_id": old["id"], "current_digest": old["digest"],
                "candidate_id": new["id"], "candidate_digest": new["digest"],
                "checks": [{"name": "table columns", "passed": passed, "observed": "three columns preserved"}]}

    def test_install_does_not_start_clock_and_source_is_preserved(self):
        record = self.install()
        self.assertEqual(self.life.due(self.store, now=1000000), [])
        self.assertTrue(self.skill().exists())
        self.assertIsNone(record["loaded_at"])

    def test_repeated_load_does_not_postpone_first_review_and_boundary_is_inclusive(self):
        a = self.install()
        self.life.load(self.store, a["id"], "a", now=100)
        self.life.load(self.store, a["id"], "a", now=159)
        self.assertEqual(self.life.due(self.store, now=159), [])
        self.assertEqual(self.life.due(self.store, now=160)[0]["id"], a["id"])

    def test_keep_records_actual_review_and_starts_next_period(self):
        a = self.install()
        self.life.load(self.store, a["id"], "a", now=100)
        self.life.keep(self.store, a["id"], "Compared current task with two candidates; current is best", now=165)
        self.life.load(self.store, a["id"], "a", now=220)
        self.assertEqual(self.life.due(self.store, now=224), [])
        self.assertEqual(self.life.due(self.store, now=225)[0]["id"], a["id"])

    def test_failure_and_task_change_can_mark_review_due_early(self):
        a = self.install()
        self.life.load(self.store, a["id"], "a", now=100)
        self.life.mark_due(self.store, a["id"], "execution failed", now=101)
        self.assertEqual(self.life.due(self.store, now=101)[0]["review_reason"], "execution failed")

    def test_busy_skill_cannot_be_replaced(self):
        a, b = self.install(), self.install("pdf-better")
        self.life.load(self.store, a["id"], "session-other", now=100)
        with self.assertRaisesRegex(ValueError, "in use"):
            self.life.replace(self.store, a["id"], b["id"], self.evidence(a, b), now=200)
        self.assertEqual(self.store.read()["entries"][a["id"]]["status"], "installed")

    def test_successful_switch_archives_only_managed_old_bundle(self):
        a, b = self.install(), self.install("pdf-better")
        self.life.load(self.store, a["id"], "a", now=100)
        self.life.release(self.store, "a")
        result = self.life.replace(self.store, a["id"], b["id"], self.evidence(a, b), now=200)
        state = self.store.read()
        self.assertEqual(result["active"]["id"], b["id"])
        self.assertEqual(state["entries"][a["id"]]["status"], "retired")
        self.assertTrue((self.store.root / "archive" / a["id"] / "SKILL.md").exists())
        self.assertFalse((self.store.root / "packages" / a["id"]).exists())
        self.assertTrue((self.base / "source-pdf-extract" / "SKILL.md").exists())
        self.assertEqual(state["entries"][b["id"]]["loaded_at"], 200)
        with self.assertRaises(ValueError):
            self.life.load(self.store, a["id"], "a", now=201)

    def test_replacement_rejects_failed_checks_and_wrong_identity(self):
        a, b = self.install(), self.install("pdf-better")
        for evidence in [self.evidence(a, b, passed=False),
                         {**self.evidence(a, b), "candidate_id": a["id"]},
                         {**self.evidence(a, b), "checks": []}]:
            with self.assertRaises(ValueError):
                self.life.replace(self.store, a["id"], b["id"], evidence, now=200)
        self.assertEqual(self.store.read()["entries"][a["id"]]["status"], "installed")

    def test_modified_candidate_and_original_are_rejected(self):
        a, b = self.install(), self.install("pdf-better")
        (self.store.root / "packages" / b["id"] / "helper.py").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.life.replace(self.store, a["id"], b["id"], self.evidence(a, b), now=200)

    def test_router_cannot_be_managed_as_a_candidate(self):
        with self.assertRaises(ValueError):
            self.install("skill-rover")

    def test_invalid_intervals_and_empty_sessions_are_rejected(self):
        for interval in [0, -1, float("nan"), float("inf"), True]:
            with self.assertRaises(ValueError):
                self.install(interval=interval)
        a = self.install()
        with self.assertRaises(ValueError):
            self.life.load(self.store, a["id"], "", now=10)

    def test_interrupted_retirement_cleanup_retried_on_next_operation(self):
        a = self.install()
        with self.store.transaction() as state:
            state["entries"][a["id"]]["status"] = "retired"
        self.life.cleanup(self.store)
        self.assertTrue((self.store.root / "archive" / a["id"]).exists())
        self.life.cleanup(self.store)
        self.assertTrue((self.store.root / "archive" / a["id"]).exists())

    def test_corrupt_state_is_not_replaced_by_empty_state(self):
        self.store.root.mkdir(exist_ok=True)
        (self.store.root / "state.json").write_text("{invalid")
        with self.assertRaises(ValueError):
            self.store.read()
        self.assertEqual((self.store.root / "state.json").read_text(), "{invalid")

    def test_explicit_only_skill_requires_explicit_load(self):
        path = self.skill(extra="disable-model-invocation: true\n")
        a = self.life.install(self.store, path, now=0)
        with self.assertRaisesRegex(ValueError, "explicit"):
            self.life.load(self.store, a["id"], "a", now=10)
        self.life.load(self.store, a["id"], "a", explicit=True, now=10)
        self.assertEqual(len(self.life.due(self.store, now=100000)), 1)

    def test_reinstall_same_content_returns_existing_id_without_resetting_clock(self):
        a = self.install()
        self.life.load(self.store, a["id"], "a", now=100)
        b = self.install()
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(self.life.due(self.store, now=160)[0]["id"], a["id"])

