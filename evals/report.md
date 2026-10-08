# v0.1 validation record

Date: 2026-10-08. These are observed results, not a claim that SkillRover always selects the best skill.

## Deterministic validation

- 43 Python unittest cases passed locally on macOS with Python 3.12 and PyYAML 6.0.3.
- The skill-creator frontmatter validator accepted the root skill.
- The lifecycle example verified the first-load deadline, repeated-load stability, successful replacement, owned-copy archival and original-source preservation.
- An independent review exercised 20 concurrent CLI loads and observed all usage records retained. Reported defects were fixed with regression tests: copied-snapshot metadata, source identity, bounded regular-file reads, archive executable permissions, target-project state defaults, hook argument handling, and interrupted retirement recovery. A follow-up case verifies that a damaged retired bundle cannot block unrelated releases.
- GitHub Actions passed all four Linux/macOS × Python 3.10/3.13 combinations for implementation commit `12b1194`: [verified run](https://github.com/yangyanlei-jiang/skill-rover/actions/runs/37725194423). Each job ran the 43 tests and lifecycle example. Check the [live workflow results](https://github.com/yangyanlei-jiang/skill-rover/actions/workflows/tests.yml) for later commits.

## Actual public discovery

`search "pdf table extraction" --limit 2` returned two public repository candidates. They were not represented as verified skills.

`fetch vercel-labs/skills --ref main --subdir skills/find-skills` resolved commit `87a266971d9460a3d2606075b8e91edc83325472` and downloaded the selected bundle for inspection. The helper returned `review_required: true`; no downloaded scripts were executed or installed. This is a connectivity/provenance check, not endorsement of that candidate.

## Independent behavioral checks

A fresh baseline agent answered six decision scenarios before reading SkillRover. A separate agent then read the skill and its references, without reading the expected-answer dataset, and answered the same six topics:

| Scenario | Baseline | With skill |
| --- | --- | --- |
| Reload just before a 24-hour deadline | First-load deadline still due | Same; complete comparison before advancing it |
| Faster candidate; user-owned global link and live session | Validate further, preserve target, defer retirement | Preserve unmanaged installation; archive only owned copy after all uses finish |
| Extraction-only PDF skill for report creation | Inspect creation capability or alternative | Choose creation/layout workflow; different roles need not supersede one another |
| Capital of France | No skill; Paris | No skill; Paris |
| Popular candidate fails validation | Do not replace | Do not replace or falsely record a completed review |
| Explicit-only deployment skill for a conceptual question | Explain without invoking it | Explain without invoking it or bypassing policy |

Both runs produced sensible decisions. This small qualitative check does **not** establish better routing accuracy, lower cost, or task-quality improvement. The 30 scenarios in cases.json remain a broader regression dataset; they have not all been executed on both native hosts.

The with-skill agent also executed a separate real CLI lifecycle experiment using two harmless mock instruction files and a 1.8-second interval. Repeated loading preserved the first timestamp; the entry became due. Two sessions prevented replacement, releasing one remained insufficient, and releasing both allowed a validated switch. The old owned copy moved to the archive, both original directories survived, the archived manifest matched the original SHA-256, and final usage and cleanup queues were empty. The candidate's observed improvement was limited to this fixture: numbered output preserving four labels, their order and a duplicate. It is not evidence about external skills.

## Native host attempts

| Host | Observed outcome | Remaining limit |
| --- | --- | --- |
| Claude Code 2.1.281, macOS | Discovered skill-rover, invoked its native Skill tool, read lifecycle.md, and correctly explained timing/ownership/usage rules. UserPromptSubmit and PostToolUse handlers ran successfully. | SessionStart was blocked before handler execution because this test sandbox denied creation of the host's session-env directory. SessionEnd delivery and an end-to-end native replacement were not verified. |
| Codex CLI 0.155.0, macOS | Generated and subprocess-tested project hooks and skill installation. Attempted ephemeral read-only native launch, including isolated log/state paths. | The CLI failed before model execution with “failed to initialize in-process app-server client: Operation not permitted”. Native skill activation and trusted-hook execution remain unverified in this environment. |
| Native Windows hosts | Generated direct-exec Claude commands and a Codex PowerShell override; checked command structure. | No native Windows host run was performed. |

The first Claude attempt loaded project settings alone and received a model authentication error. Repeating with the machine's existing user/provider configuration succeeded. No credentials or global host settings were changed. These checks distinguish host configuration and filesystem constraints from a passing product unit test.

## Scope of the evidence

Helpers enforce lifecycle mechanics, not semantic truth. The agent must actually inspect and validate each candidate. Timed checking happens on the next host event; a stopped host does not wake itself. Hooks require host trust and Python dependencies. Retiring a copy does not erase instructions already present in a conversation.
