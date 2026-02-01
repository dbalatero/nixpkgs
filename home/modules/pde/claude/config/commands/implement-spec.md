# Implement Spec

Implement specs with rigorous progress tracking for context-free resumption.

## When to Use

- User says "implement the spec" or "continue working on X"
- Resuming work after context loss
- Starting implementation of an approved spec

## First Steps

1. **Read the spec**: `.specs/{feature-name}/spec.md`
2. **Read the scratch file**: `.specs/{feature-name}/scratch.md`
3. **Check git state**: `git status`, current branch
4. **Determine current state**: What's done? What's in progress? What's next?

## Scratch.md Structure

```markdown
# {Feature Name} - Scratch Notes

## Progress

- [x] Step 1: {description} - Done
- [ ] Step 2: {description} - In progress
- [ ] Step 3: {description} - Not started

## Current State

**Status**: {In progress | Blocked | Completed}
**Current branch**: {branch-name}
**Last completed**: {What was the last thing finished}
**Working on**: {What's currently in progress}
**Next up**: {What comes after current work}

## Speedbumps

### {Date or Context}: {Brief title}
**Expected**: {M steps/approach}
**Actual**: {N steps/what happened}
**Root cause**: {Why the gap}
**Learning**: {What to do differently}

## Open Questions Resolved

1. **Q**: {Question that came up}
   **A**: {How it was resolved}

## Learnings to Codify

- [ ] {Pattern or gotcha to add to CLAUDE.md}
- [ ] {Improvement to spec template}
```

## Implementation Loop

For each step in the spec:

### 1. Start Step
```
Update scratch.md:
- Mark step as "In progress"
- Set "Working on" to current task
```

### 2. Implement
- Follow acceptance criteria from spec
- Run validation (lint, build, test) as appropriate
- Fix issues as they arise

### 3. Track Speedbumps

If something takes longer than expected:

```markdown
### {Context}: {Title}
**Expected**: Thought this would be a simple edit to X
**Actual**: Had to also modify Y, Z, and debug W
**Root cause**: {Why}
**Learning**: {What to improve}
```

### 4. Update Scratch
```markdown
## Current State

**Status**: In progress
**Current branch**: {branch}
**Last completed**: Step {n-1}
**Working on**: Step {n} - {specific task}
**Next up**: Step {n+1}
```

### 5. Repeat
Move to next step.

## When to Update Scratch.md

**MANDATORY updates after:**
- Completing a step
- Encountering a speedbump
- Resolving an open question
- Any context that would be lost on session end
- Before any risky operation
- At natural breakpoints

**Rule of thumb**: If a context-free Claude couldn't figure out where you are, update scratch.md.

## Context-Free Resumption

A Claude resuming this work should be able to:

1. Read `spec.md` -> Understand the full plan
2. Read `scratch.md` -> Know exactly where we are
3. Run `git status` -> See the git state
4. Continue from "Working on" -> Pick up immediately

If any of these fail, the scratch.md needs more detail.

## Handling Blocks

If blocked on something:

```markdown
## Current State

**Status**: Blocked
**Blocked on**: {Description of blocker}
**Waiting for**: {What needs to happen}
**Can continue when**: {Condition to unblock}
```

## Completing Implementation

When all steps are done:

1. Update scratch.md Progress (all checked)
2. Set Status to "Completed"
3. Document any remaining learnings
4. Ask user if they want to codify learnings into CLAUDE.md

```markdown
## Current State

**Status**: Completed
**All steps**: Done

## Learnings to Codify

- [x] Added X to CLAUDE.md
- [ ] Should add Y pattern
```

## Error Recovery

If something goes wrong:

1. Document in scratch.md under Speedbumps
2. Include exact error message
3. Document the fix
4. Continue implementation

Never lose error context - it's valuable for improving instructions.
