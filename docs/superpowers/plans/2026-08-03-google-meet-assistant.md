# Google Meet Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a Windows Chrome extension and local helper that record Google Meet, generate local transcripts and structured Vietnamese minutes, and keep all material data on drive D.

**Architecture:** A React Manifest V3 extension captures two audio sources and captions, sending bounded chunks to an authenticated FastAPI service on loopback. The helper owns transactional session storage, audio mixing, local Whisper/Qwen adapters, recovery, cleanup, and the final meeting repository.

**Tech Stack:** TypeScript, React, Vite, Vitest, Chrome MV3 APIs, Python 3.11, FastAPI, Pydantic, pytest, faster-whisper, llama.cpp CLI, FFmpeg/imageio-ffmpeg.

## Global Constraints

- All audio, models, caches, temporary files, logs, environments, and dependencies must live below `D:\MyProject\extention summary meeting`.
- Bind the helper only to `127.0.0.1` and require a bearer token on every session endpoint.
- Never persist meeting audio in Chrome IndexedDB or chrome.storage.
- Completed meetings contain only `recording.webm` and `minutes.json`.
- Use CPU-safe low-priority defaults and load AI models only on demand.

---

### Task 1: Helper domain and transactional storage

**Files:** `apps/helper/pyproject.toml`, `apps/helper/src/meet_assistant/{config,domain,storage}.py`, `apps/helper/tests/`

**Interfaces:** Produce `Settings.load()`, `MeetingRepository.create_session()`, `append_chunk()`, `append_captions()`, `complete_session()`, and recovery queries.

- [ ] Add failing tests for D-drive path enforcement, free-space thresholds, chunk sequencing/checksums, caption de-duplication, atomic minutes writes, and successful cleanup.
- [ ] Run the focused pytest suite and confirm failures identify missing behavior.
- [ ] Implement the minimal domain and repository behavior.
- [ ] Run focused and complete helper tests.

### Task 2: Authenticated helper API

**Files:** `apps/helper/src/meet_assistant/{api,auth,main}.py`, `apps/helper/tests/test_api.py`

**Interfaces:** Expose health, session creation, chunks, captions, checkpoint, finalize, minutes read/update, and retry under `/v1`.

- [ ] Add failing API contract tests for authentication, validation, disk guards, session lifecycle, and error responses.
- [ ] Implement loopback-safe FastAPI routes and dependency-injected services.
- [ ] Verify the API suite and OpenAPI generation.

### Task 3: Media and AI pipeline

**Files:** `apps/helper/src/meet_assistant/{audio,transcription,summarization,pipeline,resources}.py`, associated tests and fixtures.

**Interfaces:** Produce `Transcriber`, `Summarizer`, `AudioFinalizer`, `FinalizationPipeline`, and process resource controls.

- [ ] Add failing tests for track ordering, transcript/caption alignment, evidence validation, unknown speaker handling, atomic finalization, retry, and cleanup.
- [ ] Implement FFmpeg discovery/mixing and lazy local model adapters.
- [ ] Implement structured fallback behavior when models are not installed and installation diagnostics.
- [ ] Verify pipeline tests with tiny generated audio fixtures.

### Task 4: Chrome extension capture and UI

**Files:** `apps/extension/package.json`, `src/{background,content,offscreen,sidepanel,minutes,shared}/`, tests, and MV3 manifest.

**Interfaces:** Produce helper client, recording state machine, caption observer, dual MediaRecorder capture, bounded in-memory retry queue, side panel, and final minutes editor.

- [ ] Add failing Vitest tests for state transitions, retries, timeout stop, caption de-duplication, payload contracts, task rendering, and exports.
- [ ] Implement the helper client and pure recording state machine.
- [ ] Implement Meet caption observation and tab/microphone capture with audio loopback.
- [ ] Implement side panel controls, checkpoint display, recovery list, and minutes editor.
- [ ] Build the unpacked extension and run all frontend tests.

### Task 5: Setup, packaging, and end-to-end verification

**Files:** root PowerShell scripts, `README.md`, integration tests, and CI-style local verification script.

**Interfaces:** Produce `setup.ps1`, `start-helper.ps1`, `verify.ps1`, D-drive cache configuration, model installer, and user installation instructions.

- [ ] Test scripts in dry-run and isolated runtime directories.
- [ ] Install dependencies into the project-local environment and build both components.
- [ ] Run helper tests, extension tests, type checks, builds, API smoke tests, storage audit, and a synthetic capture/finalization flow.
- [ ] Audit every requirement in the design and document any hardware-only manual checks.

