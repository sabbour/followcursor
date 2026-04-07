# Decisions Archive

## PR Review Fixes — Backend (Fenster, 2026-01-20)

**Status:** Applied | **Items:** 6 fixes + 12 prior resolutions

### Key Architectural Choices

1. **Modifier VKs now recorded**
   - Removed modifier VK codes (Shift/Ctrl/Alt/Win) from `_IGNORE_VKS` in keyboard_tracker
   - Trade-off: correct shortcut detection vs. slightly larger project files and broader privacy surface
   - Documented privacy implications in module docstring

2. **Chapter END time computation**
   - Changed from hardcoded `START + 1000` to computing END from next chapter's start time
   - Added `-f ffmetadata` and `-map_chapters` flags so ffmpeg interprets metadata correctly
   - Last chapter's END uses trimmed video duration

3. **Z-order change**
   - Moved annotation rendering BEFORE cursor/click rendering in main frame loop and extra-frames loop
   - New order: video → annotations → cursor → click effects → keystrokes

4. **Near-cursor keystroke placement**
   - Implemented actual cursor-relative positioning using `KeyEvent.x`/`KeyEvent.y` data
   - Falls back to bottom-center with debug log when no cursor data available

5. **JSON decoding error handling**
   - Confirmed `json.loads()` in `project_file.py` already inside try/except with `JSONDecodeError`
   - No change needed — already robust

## PR Review Fixes — UI & Docs (McManus, 2026-04-06)

**Status:** Applied | **Items:** 25 fixes + 2 prior resolutions + 1 new test

### Key Architectural Choices

1. **Keystroke rendering in preview**
   - Added `key_events` and `keystroke_config` parameters to `compose_scene()` and preview widget
   - Extends compositor's public API but keeps keystroke rendering consistent between preview and export
   - Alternative (rendering outside compositor) would duplicate zoom/clip logic

2. **Annotation z-order alignment**
   - Moved annotations to render **before** cursor and click effects in `compose_scene()`
   - Order: video → annotations → cursor → clicks → keystrokes
   - Ensures cursor/clicks always visible on top of annotations

3. **Single overlay allocation in annotation renderer**
   - `render_annotations_cv` allocates one shared overlay copy per frame call instead of per-annotation
   - Each annotation blends its region and resets overlay for next one
   - Avoids O(n) full-frame copies for n annotations per frame

4. **HighlightBox opacity precedence**
   - Documented that `opacity` takes precedence over color alpha in both QPainter and CV renderers
   - No runtime behavior change — both renderers already used `opacity`
   - Color's alpha channel effectively ignored

---
*All decisions applied as of 2026-04-07T01:30:06Z*
