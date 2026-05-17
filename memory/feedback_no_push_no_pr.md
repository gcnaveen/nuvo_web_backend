---
name: feedback-no-push-no-pr
description: Never push to remote or create PRs — user handles git manually
metadata:
  type: feedback
---

Never push branches to remote and never create pull requests. Just make the code changes locally.

**Why:** User prefers to run and verify changes manually first, then push/PR themselves when ready.

**How to apply:** After making changes, stop at the local commit (or don't even commit unless asked). Do not run `git push`, `gh pr create`, or any command that touches the remote.
