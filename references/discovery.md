# External discovery

Start with the host's available skill catalog. Do not infer access to a disabled, private, or unavailable skill from a filesystem path.

If that catalog is incomplete, scan explicitly authorized roots:
```bash
python scripts/rover.py scan /project/.agents/skills /project/.claude/skills
```
The scanner reads metadata, not the whole instruction corpus. Results include exact paths, manifest hashes, compatibility text and implicit-invocation eligibility. Native host policy overrides what a file advertises. The scanner reports errors and bounded-search truncation; an empty result with diagnostics is not proof that no skills exist.

## Public GitHub fallback

Search only with the minimum generic capability terms; do not send private document content or secrets as a query.
```bash
python scripts/rover.py search "pdf table extraction" --limit 5
```
These are **repository candidates**, not verified skill results. Use the host's GitHub/browser tools to locate the actual SKILL.md within promising repositories. Existing skills.sh or approved catalogs may also supply candidates; SkillRover does not require their CLI.

Fetch the chosen subdirectory for inspection:
```bash
python scripts/rover.py fetch vercel-labs/skills --ref main --subdir skills/find-skills --output /temporary/review/find-skills
```
A mutable branch/tag is resolved to a 40-character commit before download. The result records the resolved revision and source URL. The helper supports public GitHub repositories. An optional GITHUB_TOKEN improves API rate limits; it is not sent to the archive host. Private repositories require the host's authorized connector workflow instead.

Inspect the entire selected skill and relevant executable/supporting resources. Check:
- Fits the requested deliverable, with credible exclusions.
- Its tools and runtime requirements are available.
- Instructions preserve the user's task and authorization.
- Required source/license information is retained.
- The proposed use can be validated on a representative permitted input.

No script is executed while searching, fetching or copying a bundle. Traversal, symlinks, special files, duplicate archive entries and oversized bundles are rejected.

After inspection and authorization, install the fetched directory using --reviewed and record the fetch result's --origin and --revision. A failed search/download leaves the current choice and any pending review intact. Report rate limits or network failures explicitly; do not invent candidates.

