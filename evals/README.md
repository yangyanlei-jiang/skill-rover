# Evaluation

Distinguish three layers:
1. Deterministic helper tests: run unittest; these exercise actual filesystem/state effects.
2. Behavioral decision cases: cases.json defines 30 scenarios and acceptable decisions. Evaluate blind by giving the host only id and prompt, not expected_behavior.
3. Native host smoke runs: record host version, skill activation, tool calls and actual outcome. Hook unit tests alone do not prove a real host trusted and ran the hook.

Use the same model, available tools, context budget and fixtures for baseline versus with-skill. Test explicit and implicit activation separately. Score both reasonable skill alternatives as correct. Include no-skill negatives.

Primary metrics: task completion, invocation/selection accuracy, false-positive routing, replacement correctness and added time/tokens. Do not use a self-reported confidence score as ground truth. Human review is needed for semantic output quality.

Initial baseline: a fresh-context agent evaluated six scenarios before the skill was authored. It already retained the first-load deadline, protected active/user-owned installations, inspected task fit, skipped skills for a simple fact, rejected a failed candidate and honored explicit-only invocation. Thus these checks do not demonstrate an improvement over native model behavior. The concrete v0.1 addition is the executable managed-lifecycle protocol.

See report.md for recorded validation. The 30-case dataset is a regression plan, not a claim that every scenario has run on every platform.

