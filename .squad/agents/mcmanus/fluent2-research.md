# Fluent 2 & Windows 11 Design Research for PySide6

**Research Date:** January 2026  
**Platform:** PySide6 (Qt 6)  
**Target:** Windows 11-native look & feel

---

## Executive Summary

1. **Windows 11 uses Fluent 2 Design System** — emphasizing calm, natural UI with soft geometry (4px/8px corner radius), Mica/Acrylic materials, Segoe UI Variable typography, and a 4px spacing grid
2. **PySide6-Fluent-Widgets library exists** — mature, GPLv3-licensed, provides 50+ Fluent-styled widgets (buttons, menus, dialogs, navigation) with acrylic support and theme switching
3. **Current FollowCursor theme is close but incomplete** — uses Segoe UI Variable, 6-12px radius, purple accent (#8b5cf6), but lacks: proper spacing tokens, state animations, elevation shadows, and Fluent component patterns
4. **Implementation strategy: hybrid approach** — adopt PySide6-Fluent-Widgets for complex components (navigation, dialogs, menus); refine existing QSS for video-editor-specific UI (timeline, preview, panels)
5. **Priority gaps to address** — spacing/padding consistency (4px grid), hover/pressed state animations (100ms ease-out), subtle shadows (QGraphicsDropShadowEffect), and rounded corners on all interactive elements

---

## 1. Windows 11 Design Principles

### Core Philosophy

Windows 11 design is built on **Fluent Design System v2**, focusing on creating interfaces that are:

- **Effortless** — Natural, intuitive interactions that build on familiar patterns
- **Calm** — Reduced visual clutter, soft colors, and ample whitespace
- **Personal** — Adaptive to user preferences (theme, accent color, wallpaper)
- **Familiar** — Grounded in platform conventions
- **Complete & Coherent** — Consistent across all app surfaces

### Visual Foundations

#### **Geometry & Spacing**
- **Corner Radius:**
  - Top-level containers (windows, dialogs): **8px**
  - In-page elements (buttons, inputs, cards): **4px**
  - Bar elements (sliders, progress bars): **4px**
  - No rounding when maximized or when elements are joined without gaps
- **Spacing Grid:** All layout uses **4px base unit** multiples (4, 8, 12, 16, 24, 32, etc.)
- **Padding Standards:**
  - Button: 10px vertical, 20px horizontal
  - Input fields: 8-12px internal padding
  - Section spacing: 16-24px between groups

#### **Typography: Segoe UI Variable**
- **Variable font** with smooth weight interpolation for clarity at all sizes
- **Type Ramp:**
  - Header: 46px / weight 200
  - Subheader: 34px / weight 200
  - Title: 24px / weight 300
  - Subtitle: 20px / weight 400
  - Body: 15px / weight 400
  - Caption: 12px / weight 400

#### **Color System**
- **Neutral palette:** Shades from white to near-black, mode-aware (light/dark)
- **Brand/Accent colors:** Single accent color (default: Windows blue #0078D4) with auto-generated hover/pressed variants
- **Status colors:** Success (green), Warning (orange/yellow), Danger (red), Info (blue)
- **Semantic tokens:** `colorBrandBackground`, `colorNeutralForeground1`, `colorNeutralStroke1`, etc.

#### **Materials (Visual Depth)**
- **Mica** — Opaque, subtly tinted with user's wallpaper; ideal for window backgrounds and title bars
  - Samples wallpaper once, updates on window move/resize
  - Mode-aware (light/dark)
  - Variants: Mica (standard) and Mica Alt (deeper tint for tabbed UIs)
- **Acrylic** — Semi-transparent frosted glass effect; reserved for transient surfaces (flyouts, menus, tooltips)
  - Real-time blur of content behind
  - Not recommended for main backgrounds (performance)
- **Shadows:** Layered drop shadows (0-3 layers) to create elevation hierarchy

#### **Motion & Animation**
- **Ease-out cubic-bezier** (0.33, 0, 0.67, 1) for all state transitions
- **Duration:** 100ms for hover/pressed states, 300ms for content reveals
- **Principles:** Motion should guide attention, provide feedback, but never distract

---

## 2. Fluent 2 Design System

### Design Principles

Fluent 2's four pillars:

1. **Natural on every platform** — Adapts to device and builds on familiar patterns (80% native components, 20% signature experiences)
2. **Built for focus** — Minimal clutter, calm aesthetics, keeps users centered
3. **One for all, all for one** — Inclusive design considering range of abilities and perspectives
4. **Unmistakably Microsoft** — Signature experiences (color, sound, icons) for brand recognition

### Design Tokens

**Three-tier architecture:**

1. **Global Tokens** — Raw values (hex colors, px sizes, font names)
   - Example: `grey64 = #A3A3A3`, `size80 = 8px`
2. **Alias Tokens** — Semantic names mapped to global tokens, context-aware
   - Example: `colorBrandBackgroundPressed`, `spacing200`
3. **Control Tokens** — Component-specific overrides

**Token Categories:**

| Category | Examples |
|----------|----------|
| **Color** | `colorBrandBackground`, `colorNeutralForeground1`, `colorStatusSuccessBackground` |
| **Spacing** | `size40` (4px), `size80` (8px), `size160` (16px), `size200` (20px), etc. |
| **Typography** | `typeRampBaseFontSize`, `typeRampPlus1LineHeight` |
| **Shape** | `borderRadius4`, `borderRadius8` |
| **Shadow** | `shadow4`, `shadow8`, `shadow16` |

### Theming

- Supports **light, dark, high-contrast, and custom brand** themes
- All alias tokens auto-adapt to theme mode
- Theme can be set per-surface (entire app or specific dialogs/panels)

---

## 3. Fluent 2 Component Catalog

### Component Categories & Qt Mapping

| Fluent 2 Component | Purpose | Qt/PySide6 Widget | Implementation Method |
|-------------------|---------|-------------------|----------------------|
| **Buttons** |
| Button | Primary action trigger | QPushButton | QSS + hover states |
| SplitButton | Primary + dropdown menu | QPushButton + QMenu | Custom widget |
| ToggleButton | On/off state | QPushButton (checkable) | QSS + icon swap |
| CompoundButton | Button with icon+label+description | QPushButton + custom paint | Custom QPainter |
| **Input & Selection** |
| Input | Single-line text entry | QLineEdit | QSS + 4px radius |
| Textarea | Multi-line text | QTextEdit | QSS |
| Checkbox | Multi-select toggle | QCheckBox | QSS + custom indicator |
| Radio Group | Single-select from list | QRadioButton + QButtonGroup | QSS |
| Switch | Binary toggle | Custom widget or QCheckBox | QPainter (pill shape) |
| Slider | Range value picker | QSlider | Custom QStyle |
| Spin Button | Number input with +/- | QSpinBox | QSS |
| Combobox | Dropdown selector | QComboBox | QSS + QAbstractItemView |
| Dropdown | Same as combobox | QComboBox | QSS |
| Searchbox | Input with search icon | QLineEdit + QPushButton | QSS |
| Tag Picker | Multi-select with chips | Custom widget | QPainter + QFlowLayout |
| **Navigation** |
| Tablist | Horizontal/vertical tab switcher | QTabWidget | QSS + custom tab bar |
| Nav (navigation menu) | Sidebar nav with icons+labels | QListWidget + custom items | QPainter for hover |
| Breadcrumb | Hierarchical path | QLabel + separators or custom | QSS |
| Menu | Context/dropdown menu | QMenu | QSS + acrylic effect |
| **Containers** |
| Card | Content grouping surface | QFrame | QSS + 4px radius + shadow |
| Accordion | Collapsible sections | QFrame + QPushButton headers | Custom layout |
| Dialog | Modal overlay | QDialog | QSS + 8px radius + dim backdrop |
| Drawer | Slide-in panel | QWidget + animation | QPropertyAnimation |
| Divider | Visual separator | QFrame (HLine/VLine) | QSS |
| **Progress & Status** |
| Progress Bar | Determinate task progress | QProgressBar | QSS + rounded ends |
| Spinner | Indeterminate loading | Custom widget | QPainter (rotating arc) |
| Skeleton | Loading placeholder | QFrame with animated gradient | QPainter |
| Badge | Status indicator | QLabel | QPainter (rounded rect) |
| Message Bar | Alert banner | QFrame + icon + text | QSS + slide animation |
| Toast | Transient notification | Custom QWidget (floating) | QPainter + QTimer |
| **Display** |
| Avatar | User photo/icon | QLabel + pixmap | QPainter (circle crop) |
| Avatar Group | Stacked avatars | QHBoxLayout + overlapping | Custom layout |
| Image | Photo/illustration | QLabel | Native |
| Icon | Vector symbol | QLabel + QIcon/SVG | QSvgWidget or QLabel |
| Label | Text descriptor | QLabel | QSS |
| Link | Clickable text | QLabel + mouse events | QSS underline on hover |
| Text | Body/heading text | QLabel | QSS with type ramp |
| Persona | Avatar + name + status | Custom widget | QPainter |
| **Advanced** |
| Toolbar | Action bar | QToolBar | QSS |
| Popover | Contextual info bubble | QWidget + QGraphicsDropShadowEffect | Custom positioning |
| Tooltip | Hover hint | QToolTip | QSS |
| List | Vertical item collection | QListWidget | QSS + custom items |
| Tree | Hierarchical data | QTreeWidget | QSS |
| Carousel | Horizontal content slider | QScrollArea + animation | QPushButton nav |
| Rating | Star rating input | Custom widget | QPainter (stars) |

### Components Relevant to Video Editor/Recorder

**High Priority:**
- **Button** — Record, Stop, Export, Save, Play/Pause
- **Slider** — Timeline scrubbing, zoom level, volume
- **Tablist** — Source picker (Screens / Windows), Editor sections
- **Combobox** — Resolution, format, frame presets, background presets
- **Progress Bar** — Export progress
- **Spinner** — Loading indicator during capture init
- **Dialog** — Settings, export options, source picker modal
- **Tooltip** — Hover hints on timeline, buttons
- **Toolbar** — Playback controls, zoom controls

**Medium Priority:**
- **Switch** — Feature toggles (show cursor, auto-zoom, include audio)
- **Input/Textarea** — Chapter titles, project name
- **Badge** — Notification dots, status indicators
- **Card** — Screen/window preview cards in source picker
- **Divider** — Separating UI sections

**Lower Priority:**
- **Accordion** — Collapsible editor sections (if space-constrained)
- **Popover** — Contextual help/settings
- **Toast** — Success/error notifications after export

---

## 4. Current FollowCursor Theme Analysis

### Strengths

✅ **Typography:** Already uses Segoe UI Variable (font-family declared in QSS)  
✅ **Dark theme:** Solid dark base (#1b1a2e) with subtle borders (#2d2b45)  
✅ **Accent color:** Purple (#8b5cf6) is distinct and modern  
✅ **Border radius:** Most buttons use 6-12px radius (close to Fluent's 4-8px)  
✅ **Hover states:** Defined for most interactive elements

### Gaps vs. Fluent 2

❌ **Spacing inconsistency:** Mix of 4px, 6px, 8px, 12px, 14px, 16px, 18px, 20px — not on 4px grid  
❌ **No spacing tokens:** All values hardcoded in QSS, not reusable  
❌ **Missing animations:** No transition properties for hover/pressed states  
❌ **No elevation shadows:** No drop shadows on cards, dialogs, or floating elements  
❌ **Inconsistent corner radius:** Mix of 4px, 6px, 8px, 10px, 12px, 18px  
❌ **No semantic color tokens:** Color values repeated throughout stylesheet  
❌ **Missing Fluent patterns:** No acrylic, no Mica emulation, no fluid motion  
❌ **Scroll bar styling:** Basic, not Fluent (should be 12px wide with rounded track)  
❌ **No focus indicators:** Missing keyboard focus outlines (accessibility gap)  
❌ **Button states incomplete:** Pressed state not always defined  
❌ **No disabled state colors:** Some widgets lack disabled styling

### Current Palette

**Background layers:**
- Canvas: `#0e0d19` (darkest — preview area)
- Surface: `#131221` (dark — sidebar, timeline, status bar)
- Panel: `#1b1a2e` (base — main widget background)
- Elevated: `#201f34` (cards, keyframe items)
- Interactive: `#28263e` (button backgrounds)

**Borders:**
- Subtle: `#2d2b45`
- Medium: `#3d3b55`
- Strong: `#4e4c68`

**Foreground:**
- Primary: `#e4e4ed`
- Secondary: `#8886a0`
- Muted: `#5a5873`
- Dim: `#6c6890`

**Accent:**
- Brand: `#8b5cf6` (purple)
- Brand hover: `#9d74f7`
- Brand active: `rgba(139, 92, 246, 0.18)` (18% opacity)

**Status:**
- Success: `#22c55e` (green)
- Danger: `#ef4444` (red)
- Danger hover: `#f87171`
- Warning: Not defined
- Info: Not defined

---

## 5. Implementation Strategy

### Recommended Approach: **Hybrid (Library + Custom QSS)**

#### Phase 1: Evaluate PySide6-Fluent-Widgets (1-2 weeks)

**Install & Test:**
```bash
pip install "PySide6-Fluent-Widgets[full]"
```

**Pilot areas:**
1. **Source picker dialog** — Replace current SourceCard widgets with FluentCard
2. **Navigation sidebar** — Use NavigationInterface for Record/Edit/Export tabs
3. **Dialogs** — Use FluentDialog for settings, export options
4. **Command bar** — Use CommandBar for playback controls

**Evaluation criteria:**
- Visual fidelity to Windows 11
- Performance (especially acrylic blur)
- Integration effort (can we mix with existing QSS?)
- License compatibility (GPLv3 — OK for open-source app)

#### Phase 2: Refine Custom QSS (2-3 weeks)

For video-editor-specific UI that doesn't map well to library components:

**Timeline widget:**
- Keep custom QPainter rendering (no library equivalent)
- Apply Fluent spacing/colors via constants

**Preview widget:**
- Keep custom compositing
- Add Fluent-style border and shadow

**Editor panel:**
- Migrate collapsible sections to library Accordion (if available)
- Use library ComboBox/Slider for controls
- Keep custom keyframe list (highly specialized)

**Title bar:**
- Keep custom (frameless window constraint)
- Apply Fluent button styling

#### Phase 3: Design Token System (1 week)

**Create `tokens.py`:**
```python
# Color tokens
COLOR_BRAND = "#8b5cf6"
COLOR_BRAND_HOVER = "#9d74f7"
COLOR_NEUTRAL_BG = "#1b1a2e"
COLOR_NEUTRAL_FG1 = "#e4e4ed"
# ... etc.

# Spacing tokens (4px grid)
SPACE_XXS = 4
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 24
SPACE_XL = 32

# Corner radius
RADIUS_SMALL = 4
RADIUS_MEDIUM = 8

# Typography
FONT_SIZE_BODY = 13
FONT_SIZE_CAPTION = 11
FONT_SIZE_TITLE = 16
```

**Refactor QSS to reference tokens:**
```python
DARK_THEME = f"""
QPushButton {{
    border-radius: {RADIUS_SMALL}px;
    padding: {SPACE_XS}px {SPACE_LG}px;
    background-color: {COLOR_BRAND};
    color: white;
}}
"""
```

#### Phase 4: Animations & Micro-interactions (1 week)

**Add QPropertyAnimation for:**
- Button hover (background color fade-in, 100ms)
- Panel slide-in/out (editor panel, source picker)
- Timeline playhead smooth movement

**Add QGraphicsDropShadowEffect for:**
- Cards in source picker
- Floating dialogs
- Tooltips

#### Phase 5: Accessibility & Polish (1 week)

**Focus indicators:**
- Add 2px accent-colored outline on focus
- Test keyboard navigation through all controls

**High-contrast mode:**
- Query system theme (QGuiApplication.palette())
- Provide alternate stylesheet with higher contrast ratios

**Motion preferences:**
- Detect OS "reduce motion" setting
- Disable animations if enabled

---

## 6. Existing Qt Fluent Libraries

### Primary Option: PySide6-Fluent-Widgets

**Homepage:** https://qfluentwidgets.com/  
**GitHub:** https://github.com/zhiyiYo/PyQt-Fluent-Widgets (PyQt fork: https://github.com/TypingWonder/Pyside6-Fluent)  
**PyPI:** https://pypi.org/project/PySide6-Fluent-Widgets/

**Features:**
- 50+ Fluent-styled widgets (buttons, navigation, menus, dialogs, cards, inputs, sliders, etc.)
- Acrylic blur effects (Windows only, using DWM APIs)
- Light/dark theme switching
- Smooth animations (fade, slide, zoom)
- Icon library integration (Fluent Icons)
- Qt Designer plugin support
- Active maintenance (1,000+ commits, regular releases)

**License:** GPLv3 (free for open-source; commercial license available)

**Pros:**
- Mature and comprehensive
- Well-documented with examples
- Active community (GitHub Discussions)
- Handles complex components (NavigationInterface, FluentWindow, Settings panels)
- Professional quality (used in production apps)

**Cons:**
- GPLv3 license (not an issue for FollowCursor, which is open-source)
- Some components may be overkill (e.g., full FluentWindow when we have custom title bar)
- Acrylic blur has performance cost (but can be disabled)
- Mixing library widgets with custom QSS may require careful theming coordination

### Alternative: qluent (QStyle approach)

**GitHub:** https://github.com/yzhgit/qluent  
**Approach:** Custom QStyle subclass (not widget library)

**Features:**
- Applies Fluent look to standard Qt widgets via QStyle
- Lightweight (no widget replacements)
- JSON theme files

**Pros:**
- Minimal code changes (just set application style)
- Works with existing Qt widgets

**Cons:**
- Less mature (fewer stars/commits)
- More limited customization
- No acrylic or advanced effects
- Unclear maintenance status

**Verdict:** PySide6-Fluent-Widgets is the stronger choice.

---

## 7. Recommendations

### Priority 1: Quick Wins (1-2 days)

1. **Normalize spacing to 4px grid**
   - Audit all `padding`, `margin`, `spacing` values in `theme.py`
   - Round to nearest 4px multiple
   - Create spacing constants

2. **Unify corner radius to 4px/8px**
   - 4px: Buttons, inputs, cards, timeline elements
   - 8px: Dialogs, panels, source picker modal
   - Remove 6px, 10px, 12px variants

3. **Add CSS transitions**
   - QPushButton hover: `transition: background-color 100ms ease-out;`
   - Note: QSS doesn't support transitions natively — requires QPropertyAnimation in code

4. **Define missing status colors**
   - Warning: `#f59e0b` (orange)
   - Info: `#3b82f6` (blue)

### Priority 2: Strategic Enhancements (2-3 weeks)

5. **Install PySide6-Fluent-Widgets**
   - Pilot in source picker dialog first
   - Evaluate performance and visual quality
   - Decide on incremental rollout vs. selective use

6. **Add drop shadows**
   - QGraphicsDropShadowEffect on cards, dialogs
   - Use shadow4 (4px blur, 2px offset) for subtle elevation

7. **Improve focus indicators**
   - 2px solid outline in accent color (#8b5cf6)
   - 2px offset for clarity

8. **Animate hover states**
   - QPropertyAnimation on background-color
   - 100ms ease-out duration

### Priority 3: Long-term Refinement (1-2 months)

9. **Design token system**
   - Create `app/tokens.py` with all color/spacing/typography constants
   - Refactor theme.py to use tokens

10. **Accessibility audit**
    - Test with keyboard-only navigation
    - Verify WCAG 2.1 AA contrast ratios
    - Support OS high-contrast mode

11. **Motion system**
    - Define easing curves (ease-out cubic-bezier)
    - Standardize durations (100ms, 200ms, 300ms)
    - Respect OS "reduce motion" setting

12. **Typography refinement**
    - Use Segoe UI Variable weights explicitly (200, 300, 400, 600)
    - Define type ramp for headers/body/captions
    - Ensure consistent line-height (1.4 for body, 1.2 for headers)

### Priority 4: Advanced (Future)

13. **Mica emulation** (low priority — complex, limited value)
    - Sample wallpaper via Win32 API
    - Apply subtle tint to window background
    - Performance cost likely not worth it

14. **Custom QStyle** (if library doesn't fit)
    - Subclass QProxyStyle
    - Override drawControl/drawPrimitive for Fluent appearance
    - More work but gives full control

15. **Fluent animations library**
    - Create reusable QPropertyAnimation presets
    - Fade in/out, slide up/down, scale in/out
    - Attach to signals for consistent feel

---

## Appendix: Key Reference URLs

**Windows 11 Design:**
- Design Principles: https://learn.microsoft.com/en-us/windows/apps/design/design-principles
- Guidelines Overview: https://learn.microsoft.com/en-us/windows/apps/design/guidelines-overview
- Geometry (Corner Radius): https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/geometry
- Materials (Mica/Acrylic): https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/materials
- Typography: https://learn.microsoft.com/en-us/windows/apps/design/signature-experiences/typography

**Fluent 2 Design System:**
- Design Principles: https://fluent2.microsoft.design/design-principles
- Design Tokens: https://fluent2.microsoft.design/design-tokens
- Components: https://fluent2.microsoft.design/components/web/react
- Layout & Spacing: https://fluent2.microsoft.design/layout
- Color Tokens: https://fluent2.microsoft.design/color-tokens/

**PySide6-Fluent-Widgets:**
- Documentation: https://qfluentwidgets.com/
- PyPI: https://pypi.org/project/PySide6-Fluent-Widgets/
- GitHub (PyQt): https://github.com/zhiyiYo/PyQt-Fluent-Widgets
- Gallery Examples: https://github.com/zhiyiYo/PyQt-Fluent-Widgets/tree/master/examples/gallery

---

## Conclusion

FollowCursor is well-positioned to adopt Windows 11's Fluent 2 design language. The existing theme already uses Segoe UI Variable and a modern dark palette. By normalizing spacing to a 4px grid, unifying corner radius to 4px/8px, adding drop shadows, and selectively integrating PySide6-Fluent-Widgets for navigation/dialogs, we can achieve a polished, Windows 11-native appearance while preserving the app's unique video-editor identity.

The hybrid approach (library for standard UI + custom QSS/QPainter for specialized video controls) balances implementation speed with flexibility. Starting with quick wins (spacing normalization, radius unification, status colors) provides immediate visual improvement, while strategic integration of the Fluent library and design token system sets the foundation for long-term consistency and maintainability.
