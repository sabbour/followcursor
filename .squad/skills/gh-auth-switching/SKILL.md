# Skill: GitHub CLI Auth Switching

**Confidence:** high
**Domain:** GitHub CLI, authentication, PR interactions
**Discovered by:** Squad Coordinator
**Date:** 2026-04-07

## Problem

The user has two `gh` CLI accounts:
- `asabbour_microsoft` — Enterprise Managed User (EMU), active by default
- `sabbour` — personal GitHub account, owns the `sabbour/followcursor` repo

The EMU account **cannot write** to the personal public repo (PR comments, thread resolution, issue updates). It returns:
```
403: "As an Enterprise Managed User, you cannot access this content"
```

## Pattern

Before any **write operation** to the `sabbour/followcursor` repo via `gh` CLI (commenting on PRs, resolving threads, editing issues, merging PRs), switch to the personal account:

```bash
gh auth switch --user sabbour
```

After write operations complete, switch back:

```bash
gh auth switch --user asabbour_microsoft
```

### What counts as a write operation:
- `gh api repos/.../pulls/comments/.../replies` — replying to PR review comments
- `gh api graphql -f query='mutation { resolveReviewThread(...) }'` — resolving threads
- `gh pr merge` — merging PRs
- `gh issue edit` — editing issues (labels, assignees, milestones)
- `gh pr create` — creating PRs
- `gh issue comment` — commenting on issues

### What works with either account:
- `gh issue list` — listing issues (read-only)
- `gh pr list` — listing PRs (read-only)
- `gh api graphql` with read-only queries
- `git push` — uses git credentials, not `gh` auth

## Agent Instructions

When spawning agents that need to perform GitHub write operations, include in the prompt:

```
## GitHub Auth
This repo is owned by the personal account `sabbour`. The default `gh` CLI auth
is an EMU account that CANNOT write to this repo. Before any `gh` write operation:
  gh auth switch --user sabbour
After writes complete:
  gh auth switch --user asabbour_microsoft
```

## Notes
- `gh auth switch` is instant (no network call — just changes active keyring entry)
- There is no per-command `--account` flag; switching is the only option
- Read operations work with either account
