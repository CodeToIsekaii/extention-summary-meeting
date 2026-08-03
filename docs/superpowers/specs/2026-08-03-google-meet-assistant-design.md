# Google Meet Assistant Design

## Goal

Build a Windows-first Chrome extension and loopback-only helper that record Google Meet tab audio and the user's microphone, preserve captions, and produce an editable Vietnamese meeting record without cloud APIs.

## Data ownership

All mutable data lives below `D:\MyProject\extention summary meeting\runtime`. Chrome may retain unavoidable extension metadata in its profile, but audio is streamed to the helper and is never persisted in Chrome storage. A completed meeting keeps exactly `recording.webm` and `minutes.json`; per-track chunks remain only for recoverable incomplete sessions.

## Components

- A Manifest V3 extension presents a Meet-only side panel, obtains tab capture and microphone streams, relays five-second chunks, observes captions, and renders checkpoints and final minutes.
- A FastAPI helper binds to `127.0.0.1`, authenticates bearer tokens, owns disk-space safeguards, stores recoverable sessions, and runs finalization jobs.
- Faster Whisper Medium performs local transcription. A llama.cpp-compatible Qwen3 4B GGUF produces schema-constrained Vietnamese minutes. Both are lazy-loaded from the D-drive model directory.

## Meeting record

The final JSON contains meeting metadata, summary, topics, decisions, action items, open questions, and timestamped transcript segments. Every action item includes evidence. Missing assignees or deadlines remain null and receive `needs_confirmation` status.

## Failure behavior

Recording cannot start without a healthy helper or five gigabytes free. Chunks are acknowledged and checksummed. Interrupted sessions remain recoverable. Final outputs are written atomically and work files are removed only after both outputs validate.

