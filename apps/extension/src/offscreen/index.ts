import { BoundedChunkQueue } from "../shared/chunkQueue";
import { HelperClient, isFatalUploadError } from "../shared/helperClient";
import type { AudioSource, ChunkEnvelope } from "../shared/types";

interface StartMessage {
  target?: string;
  type: string;
  streamId?: string;
  sessionId?: string;
  token?: string;
}

let client: HelperClient | null = null;
let sessionId: string | null = null;
let tabStream: MediaStream | null = null;
let micStream: MediaStream | null = null;
let audioContext: AudioContext | null = null;
let recorders: MediaRecorder[] = [];
let stopping = false;
let retryTimer: number | null = null;
let retrying = false;
let captureStartedAt = 0;
const sequences: Record<AudioSource, number> = { remote: 0, me: 0 };
const queues: Record<AudioSource, BoundedChunkQueue> = {
  remote: new BoundedChunkQueue(30_000),
  me: new BoundedChunkQueue(30_000)
};
const uploads: Record<AudioSource, Promise<void>> = {
  remote: Promise.resolve(),
  me: Promise.resolve()
};
const flushing: Record<AudioSource, boolean> = { remote: false, me: false };

function broadcast(type: string, payload: Record<string, unknown> = {}): void {
  void chrome.runtime.sendMessage({ type, ...payload }).catch(() => undefined);
}

function stopRetryTimer(): void {
  if (retryTimer !== null) window.clearInterval(retryTimer);
  retryTimer = null;
}

function scheduleRetry(): void {
  if (retryTimer !== null) return;
  retryTimer = window.setInterval(async () => {
    if (retrying) return;
    retrying = true;
    try {
      await flushQueue("remote");
      await flushQueue("me");
      if (queues.remote.size === 0 && queues.me.size === 0) stopRetryTimer();
    } catch {
      // Keep the bounded RAM queue and retry until it succeeds or overflows.
    } finally {
      retrying = false;
    }
  }, 1000);
}

async function flushQueue(source: AudioSource): Promise<void> {
  if (!client || !sessionId) return;
  // Recorder callbacks and the retry timer can both ask for a flush. Only
  // one request per track may be in flight, otherwise the same sequence gets
  // uploaded twice and the backend correctly returns 409 Conflict.
  if (flushing[source]) return;
  flushing[source] = true;
  const queue = queues[source];
  try {
    while (queue.peek()) {
      const chunk = queue.peek()!;
      await client.uploadChunk(sessionId, chunk);
      queue.acknowledge(source, chunk.sequence);
    }
  } finally {
    flushing[source] = false;
  }
}

function attachRecorder(stream: MediaStream, source: AudioSource): MediaRecorder {
  const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : "audio/webm";
  const recorder = new MediaRecorder(stream, { mimeType, audioBitsPerSecond: 96_000 });
  let lastChunkAtMs = 0;
  recorder.ondataavailable = (event) => {
    if (!event.data.size) return;
    const endedAtMs = Math.max(1, Date.now() - captureStartedAt);
    const chunk: ChunkEnvelope = {
      source,
      sequence: sequences[source]++,
      startedAtMs: lastChunkAtMs,
      durationMs: Math.max(1, endedAtMs - lastChunkAtMs),
      blob: event.data
    };
    lastChunkAtMs = endedAtMs;
    try {
      queues[source].push(chunk);
    } catch (error) {
      broadcast("CAPTURE_FAILED", { error: error instanceof Error ? error.message : String(error) });
      void stopCapture(false);
      return;
    }
    uploads[source] = uploads[source]
      .then(() => flushQueue(source))
      .catch((error) => {
        if (!isFatalUploadError(error)) {
          scheduleRetry();
          return;
        }
        broadcast("CAPTURE_FAILED", { error: error instanceof Error ? error.message : String(error) });
        // Avoid awaiting this upload chain from inside itself.
        void stopCapture(false);
      });
  };
  recorder.start(30000);
  return recorder;
}

async function startCapture(message: StartMessage): Promise<{ ok: boolean; error?: string }> {
  if (!message.streamId || !message.sessionId || !message.token) {
    return { ok: false, error: "Thiếu stream, session hoặc token." };
  }
  try {
    client = new HelperClient(message.token);
    sessionId = message.sessionId;
    stopping = false;
    captureStartedAt = Date.now();
    sequences.remote = 0;
    sequences.me = 0;
    queues.remote.clear();
    queues.me.clear();
    flushing.remote = false;
    flushing.me = false;
    stopRetryTimer();
    tabStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        mandatory: {
          chromeMediaSource: "tab",
          chromeMediaSourceId: message.streamId
        }
      } as MediaTrackConstraints,
      video: false
    });
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      video: false
    });
    audioContext = new AudioContext();
    audioContext.createMediaStreamSource(tabStream).connect(audioContext.destination);
    tabStream.getAudioTracks()[0]?.addEventListener("ended", () => void stopCapture(true));
    recorders = [attachRecorder(tabStream, "remote"), attachRecorder(micStream, "me")];
    broadcast("CAPTURE_STARTED", { sessionId });
    return { ok: true };
  } catch (error) {
    await stopCapture(false);
    return { ok: false, error: error instanceof Error ? error.message : String(error) };
  }
}

async function stopRecorder(recorder: MediaRecorder): Promise<void> {
  if (recorder.state === "inactive") return;
  await new Promise<void>((resolve) => {
    recorder.addEventListener("stop", () => resolve(), { once: true });
    recorder.stop();
  });
}

async function stopCapture(finalize: boolean): Promise<{ ok: boolean; error?: string }> {
  if (stopping) return { ok: true };
  stopping = true;
  const currentSession = sessionId;
  try {
    await Promise.all(recorders.map(stopRecorder));
    await Promise.all([uploads.remote, uploads.me]);
    await Promise.all([flushQueue("remote"), flushQueue("me")]);
    stopRetryTimer();
    for (const stream of [tabStream, micStream]) stream?.getTracks().forEach((track) => track.stop());
    await audioContext?.close();
    if (finalize && client && currentSession) {
      await client.finalize(currentSession);
      broadcast("CAPTURE_PROCESSING", { sessionId: currentSession });
    }
    return { ok: true };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    broadcast("CAPTURE_FAILED", { error: message, sessionId: currentSession });
    return { ok: false, error: message };
  } finally {
    recorders = [];
    tabStream = null;
    micStream = null;
    audioContext = null;
    client = null;
    sessionId = null;
    queues.remote.clear();
    queues.me.clear();
    stopRetryTimer();
    stopping = false;
  }
}

chrome.runtime.onMessage.addListener((message: StartMessage, _sender, sendResponse) => {
  if (message.target !== "offscreen") return false;
  if (message.type === "START_CAPTURE_STREAMS") {
    void startCapture(message).then(sendResponse);
    return true;
  }
  if (message.type === "STOP_CAPTURE_STREAMS") {
    void stopCapture(true).then(sendResponse);
    return true;
  }
  if (message.type === "RESET_CAPTURE_STREAMS") {
    // Used before starting a new session. It must not finalize the previous
    // session, and it clears any queued chunks belonging to a deleted session.
    void stopCapture(false).then(sendResponse);
    return true;
  }
  return false;
});
