# Resume Work from a Handoff Document

You are tasked with resuming work from a handoff document through an interactive process. These handoffs contain critical context, learnings, and next steps from previous work sessions that need to be understood and continued.

## Initial Response

When this command is invoked:

1. **If a handoff document path was provided**:
   - Read the handoff document FULLY
   - Read any critical reference documents it links to
   - Begin the analysis process by ingesting relevant context
   - Propose a course of action to the user and confirm, or ask for clarification

2. **If no parameters provided**, respond with:
   ```
   I'll help you resume work from a handoff document.

   Please provide the path to the handoff file, e.g.:
   /resume-handoff .handoffs/2025-01-08_13-55-22_feature-name.md
   ```

## Process Steps

### Step 1: Read and Analyze Handoff

1. **Read handoff document completely** using the Read tool
2. **Spawn focused research tasks** to verify current state:
   - Verify recent changes mentioned still exist
   - Validate learnings and patterns are still applicable
   - Read all artifacts mentioned

3. **Wait for research tasks** before proceeding

4. **Read critical files** identified from Learnings and Recent Changes sections

### Step 2: Synthesize and Present Analysis

Present comprehensive analysis:

```
I've analyzed the handoff from [date]. Here's the current situation:

**Original Tasks:**
- [Task 1]: [Status from handoff] -> [Current verification]
- [Task 2]: [Status from handoff] -> [Current verification]

**Key Learnings Validated:**
- [Learning with file:line reference] - [Still valid/Changed]
- [Pattern discovered] - [Still applicable/Modified]

**Recent Changes Status:**
- [Change 1] - [Verified present/Missing/Modified]
- [Change 2] - [Verified present/Missing/Modified]

**Recommended Next Actions:**
Based on the handoff's action items and current state:
1. [Most logical next step based on handoff]
2. [Second priority action]
3. [Additional tasks discovered]

**Potential Issues Identified:**
- [Any conflicts or regressions found]

Shall I proceed with [recommended action 1], or would you like to adjust the approach?
```

Get confirmation before proceeding.

### Step 3: Create Action Plan

1. Create a task list from action items in the handoff
2. Present the plan to the user

### Step 4: Begin Implementation

1. Start with the first approved task
2. Reference learnings from handoff throughout implementation
3. Apply patterns and approaches documented
4. Update progress as tasks are completed

## Guidelines

1. **Be Thorough in Analysis**:
   - Read the entire handoff document first
   - Verify ALL mentioned changes still exist
   - Read all referenced artifacts

2. **Be Interactive**:
   - Present findings before starting work
   - Get buy-in on the approach
   - Allow for course corrections

3. **Leverage Handoff Wisdom**:
   - Pay special attention to "Learnings" section
   - Apply documented patterns
   - Avoid repeating mistakes mentioned

4. **Validate Before Acting**:
   - Never assume handoff state matches current state
   - Verify all file references still exist
   - Check for changes since handoff

## Common Scenarios

### Scenario 1: Clean Continuation
- All changes from handoff are present
- No conflicts or regressions
- Clear next steps in action items
- Proceed with recommended actions

### Scenario 2: Diverged Codebase
- Some changes missing or modified
- New related code added since handoff
- Need to reconcile differences
- Adapt plan based on current state

### Scenario 3: Stale Handoff
- Significant time has passed
- Major refactoring has occurred
- Original approach may no longer apply
- Need to re-evaluate strategy
