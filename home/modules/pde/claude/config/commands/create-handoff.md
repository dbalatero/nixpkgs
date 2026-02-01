# Create Handoff

You are tasked with writing a handoff document to hand off your work to another agent in a new session. You will create a handoff document that is thorough, but also **concise**. The goal is to compact and summarize your context without losing any of the key details of what you're working on.

## Process

### 1. Filepath & Metadata

Create your file under `.handoffs/YYYY-MM-DD_HH-MM-SS_description.md`, where:
- YYYY-MM-DD is today's date
- HH-MM-SS is the hours, minutes and seconds based on the current time, in 24-hour format
- description is a brief kebab-case description

Example: `.handoffs/2025-01-08_13-55-22_create-context-compaction.md`

### 2. Handoff Writing

Use the following template structure:

```markdown
---
date: [Current date and time with timezone in ISO format]
git_commit: [Current commit hash from `git rev-parse HEAD`]
branch: [Current branch name from `git branch --show-current`]
repository: [Repository name from basename of `git rev-parse --show-toplevel`]
topic: "[Feature/Task Name]"
tags: [implementation, strategy, relevant-component-names]
status: complete
---

# Handoff: {very concise description}

## Task(s)
{description of the task(s) that you were working on, along with the status of each (completed, work in progress, planned/discussed). If you are working on an implementation plan, make sure to call out which phase you are on.}

## Critical References
{List any critical specification documents, architectural decisions, or design docs that must be followed. Include only 2-3 most important file paths. Leave blank if none.}

## Recent Changes
{describe recent changes made to the codebase in file:line syntax}

## Learnings
{describe important things that you learned - e.g. patterns, root causes of bugs, or other important pieces of information someone that is picking up your work after you should know. Consider listing explicit file paths.}

## Artifacts
{an exhaustive list of artifacts you produced or updated as filepaths and/or file:line references}

## Action Items & Next Steps
{a list of action items and next steps for the next agent to accomplish based on your tasks and their statuses}

## Other Notes
{other notes, references, or useful information that don't fall into the above categories}
```

### 3. Approve and Sync

Ask the user to review and approve the document. If they request any changes, make them and ask for approval again.

Once approved, respond with:

```
Handoff created! You can resume from this handoff in a new session with:

/resume-handoff .handoffs/{filename}.md
```

## Additional Notes & Instructions

- **More information, not less**. This is a guideline that defines the minimum of what a handoff should be. Always feel free to include more information if necessary.
- **Be thorough and precise**. Include both top-level objectives, and lower-level details as necessary.
- **Avoid excessive code snippets**. While a brief snippet to describe some key change is important, avoid large code blocks or diffs. Prefer using `/path/to/file.ext:line` references that an agent can follow later.
