# Product

<!-- impeccable:product-schema 1 -->

## Platform

windows

Impeccable does not currently define a Windows-native platform value. This
project records `windows` deliberately because `web`, `ios`, `android`, and
`adaptive` would misrepresent the shipped product.

## Users

The primary users are product teams creating product demonstrations and
walkthroughs on Windows. This includes product managers, designers, sales
teams, and marketing teams that need polished recordings they can refine
before sharing.

Tutorial creators and developer advocates are supported audiences when they
need the same recording and editing workflow.

## Product Purpose

FollowCursor is an all-in-one walkthrough studio for recording a screen or
individual window, shaping the viewer's attention, adding presentation
elements, and exporting a polished MP4 or GIF.

Success means a product team can turn a raw Windows capture into a clear,
presentable walkthrough without assembling a separate capture, camera-motion,
narration, chaptering, and export toolchain.

## Positioning

FollowCursor combines capture with an editable walkthrough timeline. It uses
recorded cursor, click, keyboard, and activity signals to generate or guide
camera movement, while keeping zoom, pan, timing, narration, chapters, visual
framing, and export under the creator's control.

The lead position is the complete walkthrough workflow, not automatic zoom as
an isolated effect.

## Operating Context

Users select a Windows monitor or application window, record an interaction,
then review the result in the editor. They can trim the recording, adjust zoom
and pan keyframes, remove events or segments, add narration and chapters,
choose presentation framing, and export the finished walkthrough.

Projects can be saved as `.fcproj` bundles and reopened for later editing.
Exports are intended for tutorials, product demonstrations, and walkthroughs
that may be shared directly or handed off to another video editor.

## Capabilities and Constraints

- The shipped product is a native Windows 10/11 desktop application built with
  Python and PySide6/Qt 6.
- It captures monitors and individual windows locally and records cursor,
  click, keyboard, and activity data used by the editing workflow.
- It supports manual, activity-driven, and optional AI-assisted zoom and pan
  decisions.
- It exports H.264 MP4 or GIF through ffmpeg, with hardware acceleration when
  available and software fallback where supported.
- Optional Azure AI features can analyze recordings and generate narration,
  voiceover, and chapter markers. Core recording and editing must not depend on
  those optional services.
- Saved project files preserve the recording and editable project state.
- Product terminology includes recordings, projects, zoom keyframes, pan path
  points, chapters, voiceover, backgrounds, frames, and exports.

## Brand Commitments

- Preserve the product name `FollowCursor`.
- Present the product as a focused Windows creation tool, not a generic web
  video platform.
- Keep product language practical and creator-oriented. Claims must describe
  shipped behavior rather than unsupported outcomes.
- Preserve existing FollowCursor icon and naming assets unless a future
  rebrand explicitly replaces them.

## Evidence on Hand

- The repository README and documentation describe the complete recording,
  editing, customization, AI, project, and export workflows.
- The application source under `followcursor/app/` implements the native
  product and its interaction model.
- The project includes a product screenshot and a demonstration video used by
  the repository documentation.
- No confirmed customer testimonials, adoption metrics, independent
  benchmarks, or formal accessibility certification are documented. Future
  work must not fabricate them.

## Product Principles

1. Keep the walkthrough editable after capture rather than baking every camera
   decision into the recording session.
2. Use real interaction signals to guide attention while preserving direct
   creator control.
3. Keep the path from recording to a shareable result inside one coherent
   desktop workflow.
4. Make optional AI assistance additive; the core product remains useful
   without it.
5. Prefer reliable export and recoverable project state over effects that make
   the workflow fragile.

## Accessibility & Inclusion

The product supports keyboard-driven workflows, visible focus treatment, and
light and dark interface themes. No formal WCAG target or other accessibility
certification is currently documented; future work must not claim one without
evidence.
