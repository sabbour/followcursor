---
name: FollowCursor
description: An iOS-inspired Windows studio for recording and shaping cinematic product walkthroughs.
colors:
  brand: "#8b5cf6"
  brand-hover: "#9d74f7"
  brand-active: "#7c3aed"
  brand-translucent: "rgba(139, 92, 246, 0.18)"
  canvas-deep: "#000000"
  layer-1: "#141414"
  layer-2: "#1f1f1f"
  layer-3: "#292929"
  layer-4: "#333333"
  layer-5: "#3d3d3d"
  foreground-primary: "#ffffff"
  foreground-secondary: "#d6d6d6"
  foreground-tertiary: "#adadad"
  foreground-disabled: "#5c5c5c"
  stroke-default: "#666666"
  stroke-secondary: "#525252"
  light-canvas: "#ffffff"
  light-layer-2: "#fafafa"
  light-layer-3: "#f5f5f5"
  light-foreground-primary: "#242424"
  light-foreground-secondary: "#424242"
  light-stroke-default: "#d1d1d1"
  record-red: "#ef4444"
  success-green: "#10b981"
  marker-amber: "#f59e0b"
  info-blue: "#3b82f6"
  timeline-teal: "#14b8a6"
typography:
  display:
    fontFamily: "Segoe UI Variable, Segoe UI, sans-serif"
    fontSize: "68px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "0"
  headline:
    fontFamily: "Segoe UI Variable, Segoe UI, sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "0"
  title:
    fontFamily: "Segoe UI Variable, Segoe UI, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0"
  body:
    fontFamily: "Segoe UI Variable, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: "0"
  label:
    fontFamily: "Segoe UI Variable, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "1px"
  timecode:
    fontFamily: "Consolas, Courier New, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.43
    letterSpacing: "0"
rounded:
  none: "0px"
  small: "6px"
  medium: "8px"
  large: "12px"
  xlarge: "16px"
  circular: "9999px"
spacing:
  xxs: "2px"
  xs: "4px"
  compact: "6px"
  sm: "8px"
  inset: "10px"
  md: "12px"
  lg: "16px"
  section: "20px"
  xl: "24px"
  xxl: "32px"
  major: "48px"
  rail: "64px"
components:
  button-secondary:
    backgroundColor: "{colors.layer-3}"
    textColor: "{colors.foreground-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.small}"
    padding: "6px 12px"
    height: "32px"
  button-primary:
    backgroundColor: "{colors.brand}"
    textColor: "{colors.foreground-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.small}"
    padding: "6px 12px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.brand-hover}"
    textColor: "{colors.foreground-primary}"
  button-primary-active:
    backgroundColor: "{colors.brand-active}"
    textColor: "{colors.foreground-primary}"
  button-record:
    backgroundColor: "{colors.record-red}"
    textColor: "{colors.foreground-primary}"
    rounded: "{rounded.medium}"
    height: "48px"
    width: "200px"
  input-default:
    backgroundColor: "{colors.layer-2}"
    textColor: "{colors.foreground-primary}"
    typography: "{typography.body}"
    rounded: "{rounded.small}"
    padding: "6px 8px"
    height: "32px"
  source-card:
    backgroundColor: "{colors.layer-4}"
    textColor: "{colors.foreground-primary}"
    rounded: "{rounded.medium}"
    padding: "8px"
---

# Design System: FollowCursor

## Overview

**Creative North Star: "The Precision Glass Studio"**

FollowCursor is a focused, precise Windows editing environment with the calm material hierarchy and control clarity associated with iOS. It remains a native PySide6 desktop application: familiar under mouse and keyboard, dense enough for repeated editing work, and composed enough that the recording remains the visual subject.

The interface uses quiet translucent chrome, generous optical spacing, and confident actions. Neutral layers organize the workflow while Studio Violet marks primary actions, active navigation, selection, and focus. Record Red is reserved for capture and destructive urgency. Timeline Teal and Marker Amber give media and editing events stable identities without turning the whole shell colorful.

The adaptation borrows visual principles, not platform behavior. It does not introduce mobile navigation, touch-only gestures, safe-area layout, ReplayKit, or iPhone and iPad runtime assumptions. New work should extend the centralized tokens and existing component patterns before introducing a local visual treatment.

**Key Characteristics:**

- Windows-native interaction patterns with iOS-inspired material restraint.
- A fixed editing frame around a fluid, aspect-preserving preview.
- Translucent tonal layers with restrained ambient lift and crisp separators.
- Semantic accent color in the timeline and high-confidence actions.
- Compact desktop typography with clear, calm hierarchy and optical spacing.
- Equal design intent in dark and light themes.

## Colors

The palette combines a neutral Fluent ramp with a violet brand voice and task-specific signal colors.

### Primary

- **Studio Violet** (`#8b5cf6`): Primary actions, selected navigation, focus, zoom activity, and direct-manipulation handles. Hover uses `#9d74f7`; pressed uses `#7c3aed`.

### Secondary

- **Record Red** (`#ef4444`): Recording, stop, destructive actions, and danger states. Keep it specific to urgency.
- **Timeline Teal** (`#14b8a6`): Voice and clip media on the timeline. It distinguishes media content from camera motion.
- **Marker Amber** (`#f59e0b`): Chapters, trim handles, pan points, progress cues, and other temporal markers.
- **Status Green** (`#10b981`): Successful completion and healthy state.
- **Information Blue** (`#3b82f6`): Informational status where violet would imply selection or action.

### Neutral

- **Deep Canvas** (`#000000`) and **Layer 1** (`#141414`): The deepest application and preview surroundings.
- **Layers 2-5** (`#1f1f1f`, `#292929`, `#333333`, `#3d3d3d`): Panels, content, cards, menus, and transient surfaces in increasing visual prominence.
- **Primary, Secondary, and Tertiary Foreground** (`#ffffff`, `#d6d6d6`, `#adadad`): The text and icon hierarchy on dark surfaces.
- **Default and Secondary Stroke** (`#666666`, `#525252`): Control boundaries and dividers.
- **Light Canvas and Layers** (`#ffffff`, `#fafafa`, `#f5f5f5`): Light-theme equivalents, paired with `#242424` primary text and `#424242` secondary text.

**The Semantic Timeline Color Rule.** Studio Violet means camera and cursor activity, Timeline Teal means media, and Marker Amber means temporal structure or attention. Preserve those meanings in custom-painted editing surfaces.

**The Accent Economy Rule.** Use Studio Violet to identify action, selection, or focus. Do not wash large passive surfaces in brand color.

## Typography

**Display Font:** Segoe UI Variable, with Segoe UI and sans-serif fallbacks  
**Body Font:** Segoe UI Variable, with Segoe UI and sans-serif fallbacks  
**Label/Mono Font:** Segoe UI Variable for labels; Consolas with Courier New fallback for timecode

**Character:** The type system uses Windows-native Segoe UI Variable with the calm hierarchy of an iOS editing surface. Weight, foreground contrast, and breathing room carry hierarchy more often than large jumps in size. Do not depend on Apple-only fonts that are unavailable on customer systems.

### Hierarchy

- **Display** (700, `68px`, `92px`): Available in the token ramp for rare display moments; it is not standard editor chrome.
- **Headline** (600, `24px`, `32px`): Dialog or major workflow headings.
- **Title** (600, `20px`, `28px`): Prominent section and overlay titles.
- **Body** (400, `14px`, `20px`): Default controls, labels, menus, and explanatory text. Semibold weight provides local emphasis.
- **Label** (600, `12px`, `16px`, `1px` letter spacing): Uppercase inspector headers and compact category labels.
- **Caption** (400, `10-12px`, `14-16px`): Dense metadata, timeline labels, and secondary status.
- **Timecode** (400, `14px`, `20px`): Stable-width playback and duration readouts.

**The Operational Scale Rule.** Keep persistent editor chrome within the caption-to-subtitle range. Large display type must not compete with the preview or timeline.

## Layout

The application is a frameless Windows desktop shell with a fixed editing frame. The minimum window is `900 x 600`; the initial window is `1200 x 800`. A `46px` runtime title bar and `28px` status bar bound the vertical workspace. The main content uses a fixed `64px` navigation rail, a fluid center column, and a fixed `320px` inspector. The inspector is hidden in Record mode and returns with the timeline in Edit mode. Its three equal-width task tabs are Motion, Style, and Audio, with Motion selected by default. Each task owns an independent scrolling region while shared utilities remain fixed below it. Do not replace this structure with a mobile tab bar, stacked navigation, or sheet-led workflow.

The center column places the aspect-preserving preview first, a `56px` playback bar second, and the timeline third. The preview has a `480 x 270` minimum. The custom timeline track is `160px` high and uses stable row geometry so content and hover states do not shift the editor.

Use the 2px-based spacing scale with an 8-16px working rhythm. Controls commonly use 8-12px internal spacing; sections use 16-24px separation. Inspector bodies use `16px` horizontal insets, `8px` internal gaps, and `16px` section gaps. Fixed action areas remain outside scrolling content.

The source picker is a focused selection surface with a `760 x 500` minimum and generous `32px` horizontal margins. Source cards have a `200 x 155` minimum and use a thumbnail-first composition.

Custom-painted widgets must respond to theme changes through theme-aware token getters. Do not copy the remaining dark-only local colors into new work. Current code also contains `48px` QSS versus `46px` runtime title-bar values and `280px` QSS versus `320px` runtime inspector values; runtime geometry is the shipped evidence, while these mismatches remain implementation debt.

## Elevation & Depth

Depth is layered, quiet, and material-led. Tonal surfaces and translucent overlays establish the base hierarchy; shadows clarify menus, dialogs, and transient overlays. On supported Windows 11 builds, native Mica supplies the glass-like host material. Older Windows uses opaque QSS layers with the same contrast hierarchy rather than simulated blur.

### Shadow Vocabulary

- **Flat** (`0px` blur, `0px` Y offset): Base canvas and edge-aligned structure.
- **Control** (`2px` blur, `1px` Y offset, `rgba(0, 0, 0, 0.28)`): Minimal lift for controls at rest.
- **Card** (`4px` blur, `2px` Y offset, `rgba(0, 0, 0, 0.28)`): Source cards and the editor panel.
- **Command** (`8px` blur, `4px` Y offset, `rgba(0, 0, 0, 0.28)`): Menus, source picker, tooltips, and settings dialogs.
- **Dialog** (`16px` blur, `8px` Y offset, `rgba(0, 0, 0, 0.28)`): Modal and callout surfaces.

Qt's standard drop-shadow effect renders one key shadow. The ambient `rgba(0, 0, 0, 0.24)` companion tokens document Fluent intent but are not rendered by that helper. Focus glow and elevation also compete for Qt's single graphics-effect slot; choose the effect that communicates the component's most important state.

**The Tonal Before Shadow Rule.** Establish hierarchy with the neutral layer ramp first. Add elevation only where a surface must visibly detach from its parent.

## Shapes

FollowCursor uses compact, softened geometry. Small controls and internal items use `6px` corners. Cards and larger buttons use `8px`. Dialogs and popovers use `12px`; exceptional overlay containers can use `16px`. Circles are reserved for status dots, slider handles, and other intrinsically round controls. Rounded geometry must not turn every command into a pill.

Borders are functional rather than decorative: `1px` neutral strokes define resting controls, accessible strokes strengthen hover, and `2px` Studio Violet identifies selection or focus. Tabs and edge-aligned navigation use square outer geometry with local indicators rather than floating pills.

## Components

Controls are quiet chrome with confident actions. Every interactive component must communicate rest, hover, pressed or active, focus, and disabled states where applicable.

### Buttons

- **Shape:** `6px` radius and `32px` minimum height for standard actions; `8px` for larger workflow actions.
- **Primary:** Studio Violet with white semibold text. Export is `32px` high; Save is `40px` high.
- **Secondary:** Layer 3 fill, primary foreground, `1px` default stroke, and `6px 12px` padding.
- **Record / Stop:** Record is a `48px` filled red action with a `200px` minimum width. Stop is a `40px` outlined danger action with a `140px` minimum width.
- **Hover / Focus:** Hover lightens or strengthens the role color. Pressed darkens it. Focus uses a `2px` Studio Violet boundary or the shared `6px` glow helper when Qt permits it.

### Cards / Containers

- **Corner Style:** `8px` for source and preview cards; `12-16px` for large transient surfaces.
- **Background:** Layer 4 at rest and Layer 5 on hover.
- **Shadow Strategy:** Card elevation uses `4px` blur and `2px` Y offset.
- **Border:** `1px` default stroke at rest; selected source cards use a `2px` Studio Violet stroke.
- **Internal Padding:** Usually `8px`; source cards use `6px` internal margins around thumbnail-first content.

### Inputs / Fields

- **Style:** Layer 2 fill, primary foreground, `1px` default stroke, `6px` radius, and `6px 8px` padding at a `32px` minimum height.
- **Focus:** Studio Violet border plus the focus treatment supported by the specific Qt widget.
- **Error / Disabled:** Semantic danger colors for errors. Disabled fields fall to Layer 1 with disabled foreground and secondary stroke.

### Navigation

The left rail uses fixed `64 x 64` items with a `20px` icon over a `12px` label. Resting items are transparent, hover uses a subtle neutral fill, and active items use translucent Studio Violet with violet text. Tabs remain transparent and use a `2px` violet bottom indicator for selection.

### Inspector Sections

The fixed `320px` post-recording inspector is organized by task rather than control type. Motion owns Smart Zoom and opens by default. Style owns Background, Device Frame, Click Effects, and Output Size; all four groups start collapsed so the tab remains a compact inventory until the creator chooses a customization. Audio owns Chapters and Voiceover; Chapters starts collapsed while the voiceover workflow remains immediately available. Style and Audio use exclusive disclosure: opening one section closes its sibling so the narrow inspector presents one decision context at a time.

Inspector sections use a fixed `32px` disclosure header with an uppercase semibold label, a native Qt disclosure arrow, and a collapsible body. Section fills, strokes, labels, separators, inputs, hover states, and focus states must use centralized theme tokens so dark and light themes preserve the same hierarchy and readable contrast.

Within Motion, Generate locally is the sole violet primary action and Generate with AI is its paired neutral alternative. Audio uses the same compact action-row pattern for automatic and playhead-based creation. Optional AI and manual alternatives must not visually outrank the active task's primary workflow. Dynamic feedback occupies one bounded status line; full text remains available through the tooltip and accessible name. Clear utility commands remain text-only. The fixed footer stays outside all tab scroll regions and keeps Undo and Redo together, followed by the native Qt information icon and Settings.

**The Inspector Task Ownership Rule.** Motion controls camera movement, Style controls presentation, and Audio controls chapters and voice. Keep new inspector controls with the task they change rather than adding another top-level tab.

**The Inspector Action Hierarchy Rule.** Use one violet primary action within the active task. Optional, alternate, and utility actions remain neutral secondary controls.

### Timeline

The `160px` timeline is the signature editing surface. It combines a ruler with fixed Mouse, Clicks, Zoom, Voice, optional Clips, and Chapter rows. Zoom segments use rounded violet blocks, transition ramps, edge handles, speed labels, and numbered amber pan points. Voice segments use teal state variants; unavailable media becomes neutral and pending synthesis adds an amber progress arc. Trim handles stay at viewport edges and use Marker Amber until snapped to the playhead.

### Preview

The preview preserves the target aspect ratio and letterboxes when necessary. It supports direct centroid and annotation manipulation, reason-coded debug markers, recording blur, and context actions for zoom and pan. Temporary mode banners use compact, centered, translucent brand treatment rather than permanent chrome.

## Do's and Don'ts

### Do:

- **Do** use centralized tokens for spacing, type, color, shape, motion, and custom paint.
- **Do** preserve the fixed rail, fluid preview, timeline, and inspector hierarchy for editor workflows.
- **Do** maintain semantic timeline colors across default, hover, selected, generating, and unavailable states.
- **Do** provide dark- and light-theme behavior for every new QSS rule, icon, and custom-painted element.
- **Do** keep primary and destructive color rare enough that active choices remain obvious.
- **Do** use tooltips and visible focus for icon-only or unfamiliar controls.
- **Do** preserve the inspector's Motion, Style, and Audio task ownership, disclosure defaults, and fixed utility footer.
- **Do** translate iOS inspiration through material, spacing, hierarchy, and motion while preserving Windows input conventions.

### Don't:

- **Don't** promote one-off dark violet-gray values from dialogs, overlays, or timeline paint code into new primitives.
- **Don't** use Studio Violet as passive decoration or as a substitute for hierarchy.
- **Don't** make cards float inside cards; use tonal panels, dividers, and collapsible sections for structure.
- **Don't** use large display typography in persistent editor chrome.
- **Don't** canonize glyph and emoji controls where the established icon pipeline provides a clear symbol.
- **Don't** promote optional AI or footer utilities to violet primary actions inside the inspector.
- **Don't** claim formal accessibility conformance; preserve keyboard access and focus treatment while documenting verified behavior only.
- **Don't** introduce ReplayKit, safe-area constraints, edge-swipe navigation, mobile tab bars, or touch-only interactions.
