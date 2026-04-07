# Project Context

- **Project:** followcursor
- **Created:** 2026-04-03

## Core Context

Agent Ralph initialized and ready for work.

## Recent Updates

📌 Team initialized on 2026-04-03

## Learnings

Initial setup complete.

---

## 2026-04-07 — Triage, README feature grouping, routing.md

**Session:** `20260407T2006-ralph-triage-routing`
**Requested by:** Ahmed Sabbour

### What was done

1. **Heartbeat triggered** — ran `gh workflow run squad-heartbeat.yml` manually.
2. **Triaged 3 open issues** — applied `squad`, `squad:member`, `go:yes`, `type:docs`, `priority:p2` labels and posted triage comments:
   - #132 → McManus (Fluent icons in MkDocs)
   - #133 → Fenster (README + screen_recorder.py docstring fix)
   - #134 → McManus (User Guide restructure)
3. **Created and implemented issue #135** — grouped README feature list under 6 categories (PR #136).
4. **Fixed CI blocker** — docs-only PRs were permanently blocked because `paths-ignore: '**/*.md'` on the `pull_request` trigger prevented the required `build` check from ever running. Removed the filter from `pull_request` (kept it on `push`).
5. **Populated `routing.md`** — replaced template stubs with real FollowCursor routing rules: 14 work-type rows and 27 module ownership rows. The heartbeat triage script (`ralph-triage.js`) now has the data it needs to route by file path and keyword.

### Learnings

#### Docs-only PRs and required CI checks
When `build.yml` uses `paths-ignore: '**/*.md'` on the `pull_request` trigger and branch protection requires the `build` check, any PR that only touches `.md` files will be permanently blocked — the check never runs, stays in `Expected` state, and merge is refused. Fix: remove `paths-ignore` from `pull_request`; keep it on `push` if desired.

#### ralph-triage.js needs `## Work Type → Agent` heading exactly
The section header regex is `/^##\s*work\s*type\s*(?:→|->)\s*agent\b/i`. The routing.md heading must match this pattern — use `## Work Type → Agent` (not `## Routing Table`).

#### routing.md was a stub — heartbeat triage was silently doing nothing
The installed `routing.md` had `{domain 1}` placeholders. Every triage run hit the lead-fallback path for all issues. Always verify routing.md is populated before relying on heartbeat auto-triage.



**Session:** `20260407T193053-fluent2-pr-merges`
**Requested by:** Ahmed Sabbour

Ran autonomous merge loop to land all 6 Fluent 2 PRs (#124–#129) into main.

### Merge order discipline for multi-PR batches
When multiple PRs touch the same high-churn file (here: `theme.py` touched by 5 of 6 PRs), merge order is a first-class concern:
- Merge PRs that don't touch the hot file first and last — they are the safest bookends
- Among PRs that do touch the hot file, sort by cumulative diff size ascending: smallest additions first, largest last
- This minimises the conflict surface at each step and ensures the most important additions land cleanly

### File deletion cascade — worktree rebase trap
When PRs were created against an older `origin/main` (before newer files existed), rebasing onto current main and reapplying patches can cause `git` to mark those newer files as "deleted" (because the patch predates them). Fix: after reapplying, run `git checkout origin/main -- {file}` for any file that should exist but was dropped.

### Review thread resolution workflow
- Fix the code issue first, commit + push
- Reply via REST: `POST /repos/{owner}/{repo}/pulls/comments` with `in_reply_to: COMMENT_ID`
- Then resolve the thread via GraphQL: `resolveReviewThread(input: {threadId: "..."})`
- Order matters: comment reply first, resolve second — resolving without a reply leaves the thread unexplained

### Worktree cleanup
After merging each PR: `git worktree remove wt-{number}` + `git branch -d squad/{number}-*`. Never leave stale worktrees — they accumulate and cause `git worktree add` naming collisions.

### Key files in this project (for future reference)
- `followcursor/app/theme.py` — central QSS stylesheet; high-churn, always check conflicts
- `followcursor/app/tokens.py` — design token definitions (DARK_*, LIGHT_*, motion, spacing)
- `followcursor/app/main_window.py` — app entry and theme wiring
- `followcursor/app/title_bar.py` — custom title bar with theme toggle button
- `followcursor/app/editor_panel.py` — recording settings panel (320px wide, spacing tokens)
- `followcursor/app/mica.py` — Windows 11 Mica/Acrylic via DwmSetWindowAttribute (new in this session)
- `followcursor/app/fluent_button.py` — animated Fluent 2 button component (new)
- `followcursor/app/fluent_tab_bar.py` — animated Fluent 2 tab bar component (new)
