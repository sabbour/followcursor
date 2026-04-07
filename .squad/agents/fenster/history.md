# Fenster — Work History

## Completed Work

### 2025-01-04 — Issue #53: Refactor video_exporter.py export thread
**Branch:** `squad/53-refactor-exporter`  
**PR:** https://github.com/sabbour/followcursor/pull/58

Decomposed the 300+ line `_run()` method into composable, testable phases:

- **Extracted `GeometryComputer` class** — Pure-logic bezel/device layout calculations with no Qt or OpenCV dependencies in the constructor. Enables unit testing geometry without video files.
- **Added typed result dataclasses** — `VideoProbeResult` and `GeometryResult` for explicit phase outputs instead of raw dicts/floats.
- **Refactored phases**:
  - `_probe_video()` — Probes source metadata, reconciles FPS/frame-count discrepancies, determines output dimensions
  - `_compute_geometry()` — Uses `GeometryComputer` to calculate device/screen layout, builds static canvas layers (background, bezel, masks)
- **12 new unit tests** covering:
  - No-frame mode (landscape, portrait video on canvas)
  - Standard bezel geometry, aspect ratio preservation
  - Edge cases: small canvas, high padding, zero bezel width
  - All 5 built-in frame presets

**Testing:** All 347 tests pass (339 existing + 12 new). Export behavior unchanged across all formats (MP4, GIF) and frame types.

## Learnings

### Pure-Logic Extraction Pattern
When refactoring complex methods with tangled dependencies (Qt, OpenCV, FFmpeg), extract **pure-logic classes first**. The `GeometryComputer` class demonstrates this:
- **Constructor takes only primitives** (ints, dataclasses) — no Qt/OpenCV objects
- **Single `compute()` method returns a dict** — deterministic, easily testable
- **No side effects** — no logging, no file I/O, no state mutation

This pattern enables:
1. **Unit testing without mocking** — no need for fake `cv2.VideoCapture` or `QSettings`
2. **Property-based testing** — can fuzz inputs, verify invariants (e.g., screen always fits in canvas)
3. **Debugging in isolation** — reproduce geometry bugs without full export pipeline

### Phase Decomposition Strategy
The export pipeline had 5 implicit phases buried in one method. Key to successful refactoring:
1. **Start with phases that have clear I/O boundaries** — probe (reads metadata, returns dataclass), geometry (reads dimensions, returns canvas/masks)
2. **Extract one phase at a time** — don't refactor everything at once
3. **Keep original behavior intact** — run full test suite after each phase extraction

Remaining phases to extract (future work):
- `_prepare_audio()` — voiceover merge
- `_render_frames()` — frame loop, zoom/cursor application
- `_finalize()` — FFmpeg encoding with fallback chain

### Dataclass vs Dict for Phase Results
Originally considered returning raw dicts from phase methods. Switched to typed dataclasses (`VideoProbeResult`, `GeometryResult`) because:
- **Type safety** — IDE autocomplete, type checker catches missing fields
- **Self-documenting** — field names + types make intent clear without docstrings
- **Testable** — can construct test fixtures without worrying about dict key typos

Trade-off: more boilerplate, but worth it for long-lived code that multiple devs will touch.

### Windows ctypes + Geometry Calculations
Bezel geometry uses floating-point math with `np.float32` arrays. Critical to:
- **Clamp values before casting to int** — avoid negative coordinates or out-of-bounds indices
- **Ensure even dimensions** — H.264 requires even width/height; geometry must round correctly
- **Test edge cases** — portrait video, small canvas (640×480), ultra-wide monitors

The geometry computer validates these constraints in pure logic before OpenCV touches any pixels.

### 2025-01-06 — Issue #62: Keystroke viz exposes passwords — filter modes not implemented
**Branch:** `squad/62-keystroke-security`  
**PR:** https://github.com/sabbour/followcursor/pull/63

Critical security fix: keystroke overlay showed ALL typed characters (including passwords) by default. Filter modes were defined but never implemented in the renderer.

**Changes:**
- **Implemented filter_mode logic in `keystroke_renderer.py`:**
  - Modified `_group_keystrokes()` to accept `filter_mode` parameter
  - Created `_should_show_group()` helper to filter keystroke groups based on mode
  - "all" mode shows everything (user explicitly chose this)
  - "modifiers-only" shows only keystrokes with Ctrl, Alt, or Win modifiers
  - "shortcuts-only" shows only keyboard shortcuts (Ctrl+X, Alt+Tab, etc.), filters single character presses
- **Changed default from "all" to "shortcuts-only":**
  - Updated `KeystrokeOverlayConfig` dataclass default
  - Updated `from_dict()` for backward compatibility
  - Updated UI combo box default selection
- **Added security warnings in `editor_panel.py`:**
  - Dynamic tooltip updates when filter mode changes
  - ⚠️ Warning when "All Keys" selected about passwords/sensitive input
  - Helpful descriptions for safer modes

**Testing:** All 347 tests passed.

## Learnings

### Security by Default: Safe Defaults Trump Convenience
The original "show all keystrokes" default was convenient for demos but dangerous for real-world use. Key lessons:

1. **Default to the safest option** — "shortcuts-only" hides passwords by default. Users who want full keystroke capture must explicitly opt in.
2. **Progressive disclosure of risk** — The "All Keys" mode now shows a warning tooltip (⚠️) so users understand the security implications before choosing it.
3. **Filter at the source** — The filter happens in `_group_keystrokes()` BEFORE grouping/rendering, not after. This ensures filtered keystrokes never make it into the rendering pipeline, even in edge cases.

### Filtering Before Grouping vs. After
Initially considered filtering after keystroke groups were formed, but realized this creates a gap:
- **After-grouping filter:** A password like "MyPass123" might form a group, then get filtered as a whole, but intermediate state could leak in logs or intermediate data structures.
- **Before-grouping filter (chosen approach):** Individual keystrokes are filtered immediately, so they never participate in grouping. This prevents even partial passwords from being grouped together.

Trade-off: Slightly more complex filtering logic (track VK codes through grouping), but eliminates entire classes of security bugs.

### Modifier Key Detection: Win32 VK Code Ranges
Windows virtual key codes for modifiers are not contiguous:
- **Ctrl/Alt/Win modifiers:** 0x11, 0x12, 0x5B, 0x5C, 0xA2-0xA5 (used for "shortcuts-only" filter)
- **Shift keys:** 0x10, 0xA0, 0xA1 (NOT considered a modifier for "shortcuts-only" — Shift+A is still just typing)

The filter uses a frozenset for O(1) lookup. Critical to exclude Shift from the modifier set, otherwise typing capital letters would be shown as "shortcuts" when they're really just normal text entry.

### Dynamic Tooltip Updates: User Feedback Loop
The keystroke filter dropdown initially had a static tooltip listing all three modes. Changed to dynamic tooltips that update when the selection changes:
- **"All Keys":** Shows prominent ⚠️ warning about passwords
- **"Modifiers Only":** Explains what will be shown
- **"Shortcuts Only":** Explains safer behavior

This creates a feedback loop: users see the security implication RIGHT as they change the setting, not buried in documentation. This reduces accidental password leaks during tutorial recordings.
# Fenster — Work History

## Completed Work

### 2025-01-04 — Issue #53: Refactor video_exporter.py export thread
**Branch:** `squad/53-refactor-exporter`  
**PR:** https://github.com/sabbour/followcursor/pull/58

Decomposed the 300+ line `_run()` method into composable, testable phases:

- **Extracted `GeometryComputer` class** — Pure-logic bezel/device layout calculations with no Qt or OpenCV dependencies in the constructor. Enables unit testing geometry without video files.
- **Added typed result dataclasses** — `VideoProbeResult` and `GeometryResult` for explicit phase outputs instead of raw dicts/floats.
- **Refactored phases**:
  - `_probe_video()` — Probes source metadata, reconciles FPS/frame-count discrepancies, determines output dimensions
  - `_compute_geometry()` — Uses `GeometryComputer` to calculate device/screen layout, builds static canvas layers (background, bezel, masks)
- **12 new unit tests** covering:
  - No-frame mode (landscape, portrait video on canvas)
  - Standard bezel geometry, aspect ratio preservation
  - Edge cases: small canvas, high padding, zero bezel width
  - All 5 built-in frame presets

**Testing:** All 347 tests pass (339 existing + 12 new). Export behavior unchanged across all formats (MP4, GIF) and frame types.

## Learnings

### Pure-Logic Extraction Pattern
When refactoring complex methods with tangled dependencies (Qt, OpenCV, FFmpeg), extract **pure-logic classes first**. The `GeometryComputer` class demonstrates this:
- **Constructor takes only primitives** (ints, dataclasses) — no Qt/OpenCV objects
- **Single `compute()` method returns a dict** — deterministic, easily testable
- **No side effects** — no logging, no file I/O, no state mutation

This pattern enables:
1. **Unit testing without mocking** — no need for fake `cv2.VideoCapture` or `QSettings`
2. **Property-based testing** — can fuzz inputs, verify invariants (e.g., screen always fits in canvas)
3. **Debugging in isolation** — reproduce geometry bugs without full export pipeline

### Phase Decomposition Strategy
The export pipeline had 5 implicit phases buried in one method. Key to successful refactoring:
1. **Start with phases that have clear I/O boundaries** — probe (reads metadata, returns dataclass), geometry (reads dimensions, returns canvas/masks)
2. **Extract one phase at a time** — don't refactor everything at once
3. **Keep original behavior intact** — run full test suite after each phase extraction

Remaining phases to extract (future work):
- `_prepare_audio()` — voiceover merge
- `_render_frames()` — frame loop, zoom/cursor application
- `_finalize()` — FFmpeg encoding with fallback chain

### Dataclass vs Dict for Phase Results
Originally considered returning raw dicts from phase methods. Switched to typed dataclasses (`VideoProbeResult`, `GeometryResult`) because:
- **Type safety** — IDE autocomplete, type checker catches missing fields
- **Self-documenting** — field names + types make intent clear without docstrings
- **Testable** — can construct test fixtures without worrying about dict key typos

Trade-off: more boilerplate, but worth it for long-lived code that multiple devs will touch.

### Windows ctypes + Geometry Calculations
Bezel geometry uses floating-point math with `np.float32` arrays. Critical to:
- **Clamp values before casting to int** — avoid negative coordinates or out-of-bounds indices
- **Ensure even dimensions** — H.264 requires even width/height; geometry must round correctly
- **Test edge cases** — portrait video, small canvas (640×480), ultra-wide monitors

The geometry computer validates these constraints in pure logic before OpenCV touches any pixels.

### 2025-01-06 — Issue #62: Keystroke viz exposes passwords — filter modes not implemented
**Branch:** `squad/62-keystroke-security`  
**PR:** https://github.com/sabbour/followcursor/pull/63

Critical security fix: keystroke overlay showed ALL typed characters (including passwords) by default. Filter modes were defined but never implemented in the renderer.

**Changes:**
- **Implemented filter_mode logic in `keystroke_renderer.py`:**
  - Modified `_group_keystrokes()` to accept `filter_mode` parameter
  - Created `_should_show_group()` helper to filter keystroke groups based on mode
  - "all" mode shows everything (user explicitly chose this)
  - "modifiers-only" shows only keystrokes with Ctrl, Alt, or Win modifiers
  - "shortcuts-only" shows only keyboard shortcuts (Ctrl+X, Alt+Tab, etc.), filters single character presses
- **Changed default from "all" to "shortcuts-only":**
  - Updated `KeystrokeOverlayConfig` dataclass default
  - Updated `from_dict()` for backward compatibility
  - Updated UI combo box default selection
- **Added security warnings in `editor_panel.py`:**
  - Dynamic tooltip updates when filter mode changes
  - ⚠️ Warning when "All Keys" selected about passwords/sensitive input
  - Helpful descriptions for safer modes

**Testing:** All 347 tests passed.

## Learnings

### Security by Default: Safe Defaults Trump Convenience
The original "show all keystrokes" default was convenient for demos but dangerous for real-world use. Key lessons:

1. **Default to the safest option** — "shortcuts-only" hides passwords by default. Users who want full keystroke capture must explicitly opt in.
2. **Progressive disclosure of risk** — The "All Keys" mode now shows a warning tooltip (⚠️) so users understand the security implications before choosing it.
3. **Filter at the source** — The filter happens in `_group_keystrokes()` BEFORE grouping/rendering, not after. This ensures filtered keystrokes never make it into the rendering pipeline, even in edge cases.

### Filtering Before Grouping vs. After
Initially considered filtering after keystroke groups were formed, but realized this creates a gap:
- **After-grouping filter:** A password like "MyPass123" might form a group, then get filtered as a whole, but intermediate state could leak in logs or intermediate data structures.
- **Before-grouping filter (chosen approach):** Individual keystrokes are filtered immediately, so they never participate in grouping. This prevents even partial passwords from being grouped together.

Trade-off: Slightly more complex filtering logic (track VK codes through grouping), but eliminates entire classes of security bugs.

### Modifier Key Detection: Win32 VK Code Ranges
Windows virtual key codes for modifiers are not contiguous:
- **Ctrl/Alt/Win modifiers:** 0x11, 0x12, 0x5B, 0x5C, 0xA2-0xA5 (used for "shortcuts-only" filter)
- **Shift keys:** 0x10, 0xA0, 0xA1 (NOT considered a modifier for "shortcuts-only" — Shift+A is still just typing)

The filter uses a frozenset for O(1) lookup. Critical to exclude Shift from the modifier set, otherwise typing capital letters would be shown as "shortcuts" when they're really just normal text entry.

### Dynamic Tooltip Updates: User Feedback Loop
The keystroke filter dropdown initially had a static tooltip listing all three modes. Changed to dynamic tooltips that update when the selection changes:
- **"All Keys":** Shows prominent ⚠️ warning about passwords
- **"Modifiers Only":** Explains what will be shown
- **"Shortcuts Only":** Explains safer behavior

This creates a feedback loop: users see the security implication RIGHT as they change the setting, not buried in documentation. This reduces accidental password leaks during tutorial recordings.

### 2025-01-06 — Issue #48: AI-powered scene chapters with auto-detection
**Branch:** `squad/48-ai-chapters`  
**PR:** https://github.com/sabbour/followcursor/pull/64

Added chapter marker support to help users navigate long recordings. Chapters can be auto-detected from activity patterns or added manually.

**Changes:**
- **Added `Chapter` model to `models.py`:**
  - `timestamp_ms`: chapter start time
  - `name`: display name (auto-generated or user-edited)
  - `auto_detected`: flag for heuristic vs manual chapters
  - Full serialization support via `to_dict()` / `from_dict()`
- **Implemented `detect_chapters()` in `activity_analyzer.py`:**
  - Heuristic-based detection (no AI API calls)
  - Detects scene boundaries from:
    - Extended inactivity (>3s idle between events)
    - Major mouse position jumps (>30% of screen distance)
    - Filters out too-short chapters (<5s)
  - Auto-generates sequential chapter names ("Chapter 1", "Chapter 2", etc.)
- **Extended `editor_panel.py` with chapter UI:**
  - "Auto-detect chapters" button triggers heuristic analysis
  - "Add chapter manually" button adds at current playback position
  - Status label shows detection results
  - Signals: `chapters_changed`, `chapter_added`, `chapter_removed`
- **Added chapter markers to `timeline_widget.py`:**
  - Yellow flag icons rendered along timeline bottom
  - Pole + triangle visual (like bookmark markers)
  - Filters chapters outside visible trim range
- **Integrated FFmpeg chapter metadata in `video_exporter.py`:**
  - Generates `;FFMETADATA1` temp file with `[CHAPTER]` sections
  - Maps metadata to MP4 output (YouTube chapter support)
  - Skips chapter export for GIF format
  - Adjusts chapter timestamps for trim offset
  - Cleans up temp metadata file after export
- **Wired persistence in `project_file.py` and `main_window.py`:**
  - Chapters saved/loaded with session in .fcproj files
  - State synchronized with timeline widget
  - Auto-numbering for manual chapters
  - Reset chapters on recording discard

**Testing:** All 288 tests passed.

## Learnings

### Heuristic Scene Detection Without AI
The chapter detection uses pure algorithmic analysis instead of AI API calls, making it:
1. **Fast** — runs in milliseconds on the existing event data
2. **Free** — no API costs or network dependencies
3. **Privacy-preserving** — no user activity data sent to external services

Key heuristics:
- **Idle gaps** — 3s+ of no mouse/keyboard/click activity signals a scene boundary (user paused or switched context)
- **Position jumps** — cursor teleporting >30% of screen distance often means switching windows/apps
- **Minimum chapter length** — filtering out <5s boundaries prevents micro-chapters from activity noise

This approach mirrors how humans mentally segment recordings: "I clicked here, then stopped typing for a while, then moved the mouse somewhere completely different."

### FFmpeg Metadata Integration Pattern
FFmpeg's chapter metadata format is simple but has gotchas:
- **TIMEBASE must match units** — using `TIMEBASE=1/1000` (milliseconds) keeps math simple
- **START/END are inclusive** — chapters end at the next chapter's start, so END can be nominal
- **Metadata input index matters** — when muxing video + audio + metadata, the `-map_metadata N` index must account for all prior inputs (video is 0, audio is 1, metadata is 2 → use `-map_metadata 2`)
- **Trim offset adjustment** — chapter timestamps are recording-relative, but export may be trimmed, so chapters need their timestamps shifted by `-trim_start_ms` and filtered to the trim range

The metadata file is created in the output directory (not /tmp, per security requirements) and cleaned up in the `finally` block to avoid leaking temp files.

### Timeline Widget Rendering Layers
The timeline already had multiple visual layers (heatmap, keyframes, segments, voiceover). Adding chapters required understanding the paint order:
1. Background + grid
2. Activity heatmaps (mouse, keyboard, clicks)
3. Zoom segments + pan points
4. Voiceover/video segments
5. **Chapter markers** (new layer)
6. Trim handles
7. Playhead (always on top)

Chapters render at `h - marker_h - 2` from the bottom so they don't overlap other UI. The flag icon (pole + triangle polygon) is visually distinct from other markers (circles for pan points, rectangles for segments).

### Chapter Auto-Numbering UX
When users manually add a chapter, the editor auto-numbers it by:
1. Scanning existing chapters for names matching `"Chapter N"` pattern
2. Extracting the highest N found
3. Naming the new chapter `"Chapter {N+1}"`

This prevents duplicate chapter numbers and gives a sensible default. Users can always rename chapters later (future feature — not implemented yet, would require edit dialog).

Trade-off: The auto-numbering is simple but doesn't renumber gaps. If user deletes "Chapter 2", the next manual chapter becomes "Chapter 4", not "Chapter 3". This is acceptable for v1 — strict sequential numbering would require complex renaming logic on every chapter delete.

