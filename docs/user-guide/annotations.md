# Annotations & Overlays

FollowCursor lets you add visual annotations to your recording and display an overlay showing keyboard shortcuts — so viewers can follow along with exactly what you're doing.

---

## Annotations

Annotations are visual markers you place on your recording to draw attention to specific areas. You can add them in the **ANNOTATIONS** section of the Editor Panel.

Three types are available:

| Type | Visual | Use it to... |
| ---- | ------ | ------------ |
| **Text** | White text on a dark background badge | Label an area, name a feature, or add a note |
| **Arrow** | Yellow directional line with an arrowhead | Point from one location to another |
| **Highlight** | Semi-transparent filled rectangle | Draw attention to a region of the screen |

All annotations:

- Show in both the **preview** and the **exported video**
- Are **time-aware** — each one is visible only during its set time range (default: 3 seconds)
- Are **resolution-independent** — they use relative positioning so they look correct at any output size
- Are **saved with the project file** so they're there when you re-open it

Annotations render behind the cursor and click effects, so interactive elements stay on top and remain easy to see.

---

## Keystroke Overlay

The keystroke overlay shows keyboard shortcuts as floating badges on the video, making it easy for viewers to follow the shortcuts you're using.

Configure it in the **KEYSTROKE OVERLAY** section of the Editor Panel:

| Setting | Options |
| ------- | ------- |
| **Filter mode** | **Shortcuts only** (default) · **Modifiers only** · **All keystrokes** |
| **Position** | Bottom-center · Bottom-left · Near cursor |
| **Style** | Floating badge · Minimal text · Key cap |
| **Display duration** | How long each badge stays visible (default: 1500 ms) |
| **Font size** | Badge text size (default: 18) |
| **Opacity** | Badge transparency (default: 0.85) |

!!! note "Default filter keeps passwords safe"
    The default **Shortcuts only** mode shows only combos that include Ctrl, Alt, or Win — it does **not** show regular typing. This prevents accidentally revealing passwords or personal text in your recordings.

### Filter Mode Options

- **Shortcuts only** — shows combos like `Ctrl+C`, `Ctrl+Shift+P`. The safest choice for most recordings.
- **Modifiers only** — shows only when a modifier key (Ctrl, Alt, Shift, Win) is held.
- **All keystrokes** — shows every key press. Use this only when you specifically want to demonstrate letter-by-letter typing.

### Overlay Position

- **Bottom-center** — badge appears in the middle of the lower portion of the video
- **Bottom-left** — badge appears in the lower-left corner
- **Near cursor** — badge floats close to wherever your cursor is at the time of the keystroke
