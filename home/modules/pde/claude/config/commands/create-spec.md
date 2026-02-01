# Create Spec

Guide the creation of implementation specs that enable context-free resumption.

## When to Use

- Starting a new feature, bugfix, or refactor
- User says "let's plan X" or "help me spec out Y"
- Complex work that will span multiple sessions/PRs
- Work that might be interrupted and resumed later

## Output Structure

All specs live in `.specs/{feature-name}/`:

```
.specs/
└── {feature-name}/
    ├── spec.md      # The implementation spec
    └── scratch.md   # Progress tracking (created during implementation)
```

## Spec Building Process

### Phase 1: Discovery

1. **Understand the problem**: What's broken? What's the desired outcome?
2. **Investigate the codebase**: Find relevant files, patterns, existing solutions
3. **Query the database** (if relevant): Understand data shapes, volumes, edge cases
4. **Document findings** as you go - these become part of the spec

### Phase 2: Design

1. **Identify approach options**: List alternatives considered
2. **Make design decisions**: Document rationale for chosen approach
3. **Identify risks**: What could go wrong? How to mitigate?
4. **Plan rollout**: Feature flags? Staged deployment?

### Phase 3: Implementation Planning

1. **Break into atomic steps**: Each step should be independently verifiable
2. **Order for dependencies**: Dependencies flow downward
3. **Define acceptance criteria**: What must be true for each step to be complete?

## Spec.md Template

```markdown
# {Feature Name} - Implementation Spec

## Problem Statement

{What's broken or missing? Why does it matter?}

## Investigation Findings

### Codebase
- {Key files and their roles}
- {Existing patterns to follow}
- {Gotchas discovered}

### Database (if applicable)
- {Relevant tables and relationships}
- {Data volumes and patterns}

## Design

### Approach
{Description of the chosen solution}

### Alternatives Considered
| Option | Pros | Cons | Why not chosen |
|--------|------|------|----------------|
| ... | ... | ... | ... |

### Key Decisions
1. **{Decision}**: {Rationale}
2. ...

### Risks
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | ... | ... | ... |

## Implementation Steps

### Step 1: {Description}
**Purpose**: {What this step accomplishes}
**Files**:
- `path/to/file.ts` - {what changes}
**Acceptance Criteria**:
- [ ] {Criterion 1}
- [ ] {Criterion 2}

### Step 2: {Description}
...

## Pre-Implementation Checklist

- [ ] Design reviewed with user
- [ ] Implementation steps approved
- [ ] Ready to implement
```

## What Makes a Good Spec

1. **Self-contained**: A context-free Claude can read it and start implementing
2. **Investigative evidence**: Shows the work done to understand the problem
3. **Decision rationale**: Explains *why*, not just *what*
4. **Clear acceptance criteria**: Unambiguous definition of "done" for each step

## Asking Clarifying Questions

During spec creation, use AskUserQuestion to resolve:
- Ambiguous requirements
- Design tradeoffs that need user input
- Scope decisions (what's in vs out)

Don't proceed with ambiguity - capture decisions in the spec.

## Finishing Up

Before completing spec creation:

1. **Write spec.md** to `.specs/{feature-name}/spec.md`
2. **Review with user**: Walk through the spec, get approval
3. **Create scratch.md stub**: Initialize `.specs/{feature-name}/scratch.md` with:

```markdown
# {Feature Name} - Scratch Notes

## Progress

- [ ] Step 1: {description}
- [ ] Step 2: {description}
...

## Current State

**Status**: Not started
**Last completed**: N/A

## Speedbumps

{Track issues where expected M steps took N steps, M << N}

## Learnings to Codify

{Patterns, gotchas, or improvements to add to instructions later}
```

4. **Inform user**: Spec is ready, they can run `/implement-spec {feature-name}` to begin
