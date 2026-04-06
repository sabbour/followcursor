# McManus — UI Dev History

## Recent Work

### 2026-04-06: Interactive Annotations (Issue #54)

Implemented complete annotation system for text, arrows, and highlights.

**Models** (models.py):
- Added TextAnnotation, ArrowAnnotation, HighlightBox dataclasses
- Created AnnotationCollection container class
- Full serialization support with 	o_dict() / rom_dict() methods
- Normalized coordinates (0-1) for resolution independence

**Renderer** (nnotation_renderer.py):
- Dual-pipeline architecture: QPainter for preview, OpenCV for export
- Followed established patterns from cursor_renderer.py and keystroke_renderer.py
- Proper layering: highlights (back) → arrows → text (front)
- Timeline-aware rendering (only visible during time range)
- Alpha blending for highlight boxes and text backgrounds

**UI** (ditor_panel.py):
- Added ANNOTATIONS collapsible section with three action buttons
- Scrollable annotation list with type icons and delete buttons
- Real-time annotation placement at playhead position
- Default 3-second duration for new annotations
- Integrated into editor panel signal system

**Integration**:
- ideo_exporter.py: Added annotation rendering to both normal and speed-adjusted frame loops
- compositor.py: Updated compose_scene() with annotation support (handles zoom-video-only mode)
- preview_widget.py: Added set_annotations() method and state tracking
- project_file.py: Full save/load support for AnnotationCollection
- main_window.py: State management, signal routing, export/preview wiring

**Testing**: All 58 existing tests pass.

## Learnings

1. **Dual-Pipeline Pattern**: The cursor and keystroke renderers established a clean pattern with separate QPainter and OpenCV render functions. Following this pattern made integration straightforward and maintainable.

2. **Normalized Coordinates**: Using 0-1 normalized coordinates for annotation positions ensures annotations work correctly regardless of source resolution or export dimensions. Critical for cross-resolution compatibility.

3. **Timeline Integration**: Annotations need the current playhead time for proper placement. Connected _on_seek() in main_window to update both preview and editor panel with set_current_time().

4. **Signal-Driven Architecture**: FollowCursor uses Qt signals for all inter-component communication. Added three new signals to EditorPanel: nnotation_added, nnotation_removed, nnotation_updated.

5. **State Management Pattern**: Followed existing patterns for state variables (self._annotations), save/load integration, and export parameter passing. Consistency with _keystroke_config and _click_preset made wiring straightforward.

6. **Layering Order**: Rendering order matters for visual hierarchy. Highlights must be drawn first (background), then arrows, then text (foreground) for proper layering in both preview and export.

7. **Alpha Blending**: Highlight boxes and text backgrounds require proper alpha blending. OpenCV uses cv2.addWeighted() with overlay technique; QPainter uses QColor.setAlphaF().

8. **Zoom-Video-Only Mode**: The compositor has special handling for frameless + zoom mode (virtual screen rect calculation). Had to handle this case separately in annotation rendering.

9. **List Management**: Used insertWidget(count - 1) pattern to keep annotation items above the stretch spacer in the scrollable list. Delete handling removes both from UI and data model.

10. **Factory Pattern**: All annotation models use static create() factory methods that auto-generate UUIDs. Follows the established pattern from ZoomKeyframe, VideoSegment, etc.

## Technical Decisions

- **Coordinate System**: Normalized (0-1) rather than absolute pixels for resolution independence
- **Rendering Pipeline**: Separate functions for QPainter (preview) and OpenCV (export)
- **Default Duration**: 3 seconds for new annotations (reasonable visibility window)
- **Storage Format**: Full AnnotationCollection serialized as nested dict in project.json
- **UI Layout**: Scrollable list with max-height of 200px to prevent panel overflow
- **Color Defaults**: Yellow (#FFCC00) for arrows/highlights, white text with dark background

## Code Organization

The annotation feature follows FollowCursor's established patterns:
- Data models in models.py with serialization support
- Dual-pipeline renderer in dedicated module
- UI controls in collapsible section within editor panel
- State management in main window
- Integration points: video exporter, compositor, project file, preview widget

This organization ensures maintainability and consistency with the existing codebase.
