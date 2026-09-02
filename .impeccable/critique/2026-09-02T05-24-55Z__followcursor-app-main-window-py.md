---
target: native FollowCursor main window, grounded in live screenshot
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\asabbour\\Git\\followcursor\\followcursor\\app\\main_window.py"
target_fingerprint: "sha256:b6233e0e323046b8366fd852d3fc1dd011d48d2e081595610813384741b468d9"
target_path: "C:\\Users\\asabbour\\Git\\followcursor\\followcursor\\app\\main_window.py"
timestamp: 2026-09-02T05-24-55Z
slug: followcursor-app-main-window-py
---
Method: dual-agent (A: impeccable-finish-reviewer · B: Explore, detector rerun in parent after B lacked terminal access)

## Design Health Score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 1 | Status exists in source but is outside the captured launch composition. |
| 2 | Match system / real world | 3 | Familiar commands; “screen” omits supported window capture. |
| 3 | User control and freedom | 3 | Cancel and project controls exist, but the first view offers one vague path. |
| 4 | Consistency and standards | 3 | Rail is consistent; initial command availability is ambiguous. |
| 5 | Error prevention | 2 | Countdown helps, but source selection can proceed with implicit defaults. |
| 6 | Recognition rather than recall | 3 | Commands are labeled; the huge clickable canvas does not read as a control. |
| 7 | Flexibility and efficiency | 3 | Strong source-verified keyboard shortcuts. |
| 8 | Aesthetic and minimalist design | 2 | Restrained, but the extreme void reads unfinished. |
| 9 | Error recovery | 3 | Specific save, load, export, and finalization recovery exists in source. |
| 10 | Help and documentation | 1 | No visible source-choice or pre-recording reassurance. |
| **Total** | | **24/40** | **Needs focused improvement** |

## Design Specificity Verdict

The rail and violet accent feel coherent, but the launch state remains category-interchangeable: a generic dark editor with a dashed empty field. The verified native screenshot shows the source prompt displaced right and below center, incomplete preview boundaries, and no visible title/status chrome. That falls short of DESIGN.md’s “Precision Glass Studio.”

The detector found 86 advisory-level token drift findings in followcursor/app/main_window.py: 64 undocumented colors, 15 off-ramp 13px/15px font sizes, and 7 off-ramp 2px/4px/7px radii. Repetition inflates the count, but the underlying drift is real. Browser overlays were skipped because native Qt has no injectable DOM; followcursor-live.png is the visual evidence instead.

## Overall Impression

The app is calm and operational, but its most important first moment feels accidental. The biggest opportunity is to make source selection a deliberate, centered command surface that remains correctly framed at every Windows DPI scale.

## What's Working

- The recording surface remains visually dominant.
- Record, Edit, Open, and Save are labeled and easy to scan.
- Violet is used economically for brand and selection rather than flooding passive surfaces.

## Priority Issues

1. **[P1] Launch composition breaks at the captured geometry.** Fix restored geometry and DPI behavior; validate at 100%, 125%, 150%, and 200%. Suggested command: `/impeccable adapt`.
2. **[P1] Source selection lacks a confident primary action.** Center a bounded “Choose recording source” action and name “screen or window.” Suggested command: `/impeccable onboard`.
3. **[P1] Source cards are not keyboard-operable.** Use focusable controls with Enter/Space, accessible names, and predictable tab order. Suggested command: `/impeccable audit`.
4. **[P2] Initial commands do not communicate prerequisites.** Establish explicit empty-state enablement for Edit, Save, and Export. Suggested command: `/impeccable harden`.
5. **[P2] Visual implementation has drifted from the design contract.** Consolidate literal colors, font sizes, and radii into centralized tokens or document intentional additions. Suggested command: `/impeccable polish`.

## Persona Red Flags

- **First-time tutorial creator:** cannot tell whether choosing a source starts recording, or whether windows are supported.
- **Repeat creator:** shortcuts help, but ambiguous disabled states and clipped chrome erode fast-path confidence.
- **Keyboard/screen-reader user:** cannot complete source-card selection without a mouse and receives weak semantic identification.

## Minor Observations

The active Record tile is clear, version text is appropriately quiet, and Open/Save grouping is sensible. Mica is enabled at runtime, but the launch capture still reads mostly flat black and charcoal.

## Questions to Consider

- Should launch feel like an empty editor or a purpose-built capture-source step?
- Is “Nothing records until you press Record” the reassurance first-time users need?
- Is the purple-neutral palette in main_window.py an intentional second palette or implementation drift?
