---
name: deslop
description: Remove AI-generated code slop and clean up code style
model: inherit
---

# Remove AI Code Slop

Check the diff of recent changes with `git diff HEAD~1` (or against the appropriate base), and remove all AI generated slop introduced.

This includes:
- Extra comments that a human wouldn't add or is inconsistent with the rest of the file
- Extra defensive checks or try/catch blocks that are abnormal for that area of the codebase (especially if called by trusted / validated codepaths)
- Casts to any to get around type issues
- Deeply nested code that should be refactored using early return guards to improve readability
- Overly verbose variable names or excessive documentation
- Unnecessary type annotations that TypeScript can infer
- Redundant null/undefined checks where the type system guarantees values
- Any other style that is inconsistent with the file

Report at the end with only a 1-3 sentence summary of what you changed.
