# Lora AI SQLite runtime rollout trigger

This note intentionally creates a small follow-up PR after the SQLite startup
schema fix and image-workflow SHA fallback were merged.

The lora-ai post-merge image workflow requires a merged PR with:

- the `build` label, and
- at least one GitHub `APPROVED` review.

The previous workflow-fix PR had the `build` label but no approved review, so
its post-merge image workflow correctly skipped Docker build, ACR push, and Helm
test-values update.

Approving and merging this follow-up PR should trigger the normal GitHub Actions
image path for the current `main` commit, which includes:

- `ae22a06 fix: initialize sqlite schema on startup`
- `acc8248 fix: tolerate deleted PR head SHA in lora image workflow`

No runtime code changes are introduced by this document.
