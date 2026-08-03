# Meet Assistant UI Handoff

## User and context

The primary user runs the extension beside a live Google Meet on a Windows laptop. The interface must minimize attention switching, make recording unmistakable, and favor machine smoothness over fast AI output. Vietnamese is the default language.

## Flow and states

1. The side panel opens in `idle`, checks the helper, token, active Meet tab, and D-drive capacity.
2. One explicit “Bắt đầu ghi” click moves through `starting` to `recording`; no automatic recording is allowed.
3. `recording` keeps a persistent red REC indicator, elapsed time, source/caption health, Stop, and Checkpoint actions.
4. Stop moves through `stopping` and `processing`; the panel polls the helper and offers Pause/Resume where supported.
5. `completed` exposes “Mở biên bản”. `error` keeps the exact reason and recovery action.
6. The minutes page loads by `minutes.html?session=<id>`, supports audio seek from timestamps, editing, saving, and explicit Markdown/HTML export.

Helper offline, missing token, missing permissions, low disk, caption loss, 30-second upload overflow, processing failure, and recoverable sessions must each be distinguishable. Status changes use `aria-live`; focus remains on the initiating control unless an unrecoverable error requires the retry action.

## Component contracts

### RecordingPanel

- Inputs: recording state, helper/token readiness, elapsed time, latest checkpoint, and callbacks.
- Primary action is full-width. REC is text plus color, never color alone.
- Starting/stopping/processing disable conflicting actions. Checkpoint remains secondary and reports slow local processing.
- Side-panel layout is single-column from 320–600 px; controls have at least 44 px targets.

### MinutesEditor

- Inputs: one `MeetingMinutes`, optional blob audio URL, async save callback.
- Sections: metadata, summary, decisions, action table, open questions, searchable transcript.
- `needs_confirmation` uses amber badge and explicit wording. Missing owner/deadline displays “Chưa xác định/Chưa có deadline”.
- Timestamp controls are keyboard buttons and seek the audio element.

## Tokens

- Background `#f5f7fb`, surface `#ffffff`, ink `#172033`, muted `#667085`.
- Primary `#3157d5`; recording/error `#c9363e`; warning `#b56a08`; success `#16805b`.
- Focus ring `0 0 0 3px rgba(49,87,213,.28)`; minimum contrast 4.5:1.
- Typography uses system sans; 13/16 body in side panel, 16/24 body in minutes page.
- Spacing follows 4/8/12/16/24/32 px. Radius 10 px cards and 8 px controls.
- Motion is limited to 150 ms state transitions and a reduced-motion-safe REC pulse.

## Engineering target and acceptance

Target is a React/Vite client-only Chrome extension. The UI is accepted when all lifecycle states are visually distinct, keyboard reachable, screen-reader announced, usable at 320 px width, and covered by component interaction tests plus a production build.
