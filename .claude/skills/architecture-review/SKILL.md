---
name: architecture-review
description: Run the standard Foundry architecture review process — compares the current branch against a base ref, gathers relevant RFCs, and invokes the adversarial-architect subagent for a structured, read-only review. Use when the user asks for an architecture review, adversarial review, or wants RFC work checked before merge.
argument-hint: '[base-ref]'
user-invocable: true
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash(git status:*)
  - Bash(git branch:*)
  - Bash(git diff:*)
  - Bash(git log:*)
  - Bash(git rev-parse:*)
  - Bash(ls:*)
  - Bash(find:*)
  - Agent
---

# Architecture Review

Runs Foundry's standard adversarial architecture review: scope the change, gather
context, delegate to the `adversarial-architect` subagent, and hand back its
findings untouched.

This skill is **review-only**. Never edit files, stage changes, commit, or run any
git command that mutates state (no `add`, `commit`, `checkout`, `reset`, `stash`,
etc.) while running it.

## Arguments

Raw skill arguments: `$ARGUMENTS`

- No arguments → comparison base is `origin/main`.
- One argument → treat it as the comparison base ref (e.g. `/architecture-review origin/main`,
  or any other branch/tag/commit the user names).

## Steps

1. **Confirm current branch and Git status.**
   Run `git branch --show-current` and `git status --short --untracked-files=all`.
   Note both tracked modifications and untracked files — untracked files under
   `src/`, `tests/`, or `docs/` are still in scope for the review.

2. **Determine the comparison base.**
   Use the argument passed in `$ARGUMENTS` if present; otherwise default to
   `origin/main`. Verify the ref actually resolves with
   `git rev-parse --verify <base>` before relying on it. If it doesn't resolve,
   tell the user and stop rather than guessing a substitute ref.

3. **Collect the Git diff.**
   Run `git diff <base>...HEAD --stat` to size the change, and
   `git diff <base>...HEAD` (or targeted per-file diffs if the full diff is very
   large) to know exactly what changed. Include untracked files from step 1 in
   the scope even though `git diff` won't show them.

4. **Locate relevant RFCs and implementation reports.**
   Look under `docs/` (e.g. `docs/rfc-*-architecture.md`,
   `docs/rfc-*-implementation-report.md`) for documents matching the current
   branch or the changed area. Use `git status`/`git diff --stat` output to infer
   which RFC number or feature area is in play, then `Glob`/`Grep` for matches.
   These give the subagent the intended design to check the implementation
   against.

5. **Invoke the `adversarial-architect` subagent.**
   Launch it via the `Agent` tool with `subagent_type: "adversarial-architect"`.
   The prompt must be self-contained (the subagent starts with no context) and
   should include:
   - The branch name and comparison base ref.
   - The full list of modified and untracked files from step 1.
   - Pointers to the RFC/architecture/implementation-report docs found in step 4.
   - An instruction to verify the diff itself (`git diff <base>...HEAD`) rather
     than trust the file list, since the file list is just a pointer.
   - An explicit instruction that this is review-only: no fixes, no edits.
   - A request for the standard adversarial-architect structured review format.

6. **Return only the structured review.**
   When the subagent's findings arrive, output them to the user as-is. Do not
   add your own summary, preamble, or editorializing before or after the review.
   Do not compress or drop sections — pass through the full structured output.

7. **Never modify code or Git state.**
   At no point in this skill should any file be edited or written, and no git
   command that changes repository state should run. If the user asks for fixes
   based on the review, that is a separate, explicit follow-up request — not part
   of this skill.
