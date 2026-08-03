import type { CaptionSegment, ChunkEnvelope, MeetingMinutes } from "./types";

const DEFAULT_BASE_URL = "http://127.0.0.1:8765/v1";

export class HelperError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "HelperError";
    this.code = code;
    this.status = status;
  }
}

export function isFatalUploadError(error: unknown): boolean {
  return error instanceof HelperError && error.code === "disk_stop";
}

async function blobBytes(blob: Blob): Promise<Uint8Array<ArrayBuffer>> {
  if (typeof blob.arrayBuffer === "function") {
    return Uint8Array.from(new Uint8Array(await blob.arrayBuffer()));
  }
  const buffer = await new Promise<ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Cannot read audio chunk"));
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.readAsArrayBuffer(blob);
  });
  return Uint8Array.from(new Uint8Array(buffer));
}

async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await blobBytes(blob));
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join(
    ""
  );
}

export interface SessionManifest {
  id: string;
  title: string;
  status: "recording" | "processing" | "failed" | "completed";
  started_at?: string;
  error?: string | null;
}

export interface JobState {
  session_id: string;
  status: "recording" | "processing" | "paused" | "failed" | "completed";
  error?: string | null;
  output_dir?: string | null;
}

const DEFAULT_FETCHER: typeof fetch = (...args) => globalThis.fetch(...args);

export class HelperClient {
  readonly token: string;
  readonly fetcher: typeof fetch;
  readonly baseUrl: string;

  constructor(token: string, fetcher: typeof fetch = DEFAULT_FETCHER, baseUrl = DEFAULT_BASE_URL) {
    this.token = token;
    this.fetcher = fetcher;
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  private async request<T>(path: string, init: RequestInit = {}, authenticated = true): Promise<T> {
    const headers = new Headers(init.headers);
    if (authenticated) headers.set("Authorization", `Bearer ${this.token}`);
    if (init.body && typeof init.body === "string") headers.set("Content-Type", "application/json");
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      // Model loading and status checks can take longer on a local CPU.
      // Keep the request bounded, but do not fail healthy jobs after 8 seconds.
      signal: init.signal ?? AbortSignal.timeout(30000)
    });
    if (!response.ok) {
      let code = "helper_error";
      let message = `Helper returned HTTP ${response.status}`;
      try {
        const payload = (await response.json()) as {
          detail?: { code?: string; message?: string } | string;
        };
        if (typeof payload.detail === "object") {
          code = payload.detail.code ?? code;
          message = payload.detail.message ?? message;
        } else if (typeof payload.detail === "string") {
          message = payload.detail;
        }
      } catch {
        // Preserve the stable fallback above for non-JSON errors.
      }
      throw new HelperError(response.status, code, message);
    }
    return (await response.json()) as T;
  }

  health(): Promise<{
    status: string;
    disk: { can_start: boolean; warning: boolean; must_stop: boolean; free_gb: number };
  }> {
    return this.request("/health", {}, false);
  }

  pair(): Promise<{ auth_token: string }> {
    return this.request("/pairing", {}, false);
  }

  createSession(title: string, meetUrl: string | null): Promise<SessionManifest> {
    return this.request("/sessions", {
      method: "POST",
      body: JSON.stringify({ title, meet_url: meetUrl, language: "vi" })
    });
  }

  listRecoverable(): Promise<SessionManifest[]> {
    return this.request("/sessions");
  }

  async uploadChunk(sessionId: string, chunk: ChunkEnvelope): Promise<void> {
    const form = new FormData();
    form.set("source", chunk.source);
    form.set("sequence", String(chunk.sequence));
    form.set("started_at_ms", String(chunk.startedAtMs ?? chunk.sequence * chunk.durationMs));
    form.set("duration_ms", String(chunk.durationMs));
    form.set("sha256_hex", await sha256Hex(chunk.blob));
    form.set("audio", chunk.blob, `${chunk.source}-${chunk.sequence}.webm`);
    await this.request(`/sessions/${sessionId}/chunks`, { method: "POST", body: form });
  }

  uploadCaptions(sessionId: string, captions: CaptionSegment[]): Promise<{ accepted: number }> {
    return this.request(`/sessions/${sessionId}/captions`, {
      method: "POST",
      body: JSON.stringify(captions)
    });
  }

  checkpoint(sessionId: string): Promise<MeetingMinutes> {
    return this.request(`/sessions/${sessionId}/checkpoint`, { method: "POST" });
  }

  finalize(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}/finalize`, { method: "POST" });
  }

  retry(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}/retry`, { method: "POST" });
  }

  pause(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}/pause`, { method: "POST" });
  }

  resume(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}/resume`, { method: "POST" });
  }

  fast(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}/fast`, { method: "POST" });
  }

  async deleteSession(sessionId: string): Promise<void> {
    const response = await this.fetcher(`${this.baseUrl}/sessions/${sessionId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${this.token}` }
    });
    if (!response.ok) {
      throw new HelperError(response.status, "delete_failed", "Không xóa được phiên recovery.");
    }
  }

  getStatus(sessionId: string): Promise<JobState> {
    return this.request(`/sessions/${sessionId}`);
  }

  getMinutes(sessionId: string): Promise<MeetingMinutes> {
    return this.request(`/sessions/${sessionId}/minutes`);
  }

  updateMinutes(sessionId: string, patch: Partial<MeetingMinutes>): Promise<MeetingMinutes> {
    return this.request(`/sessions/${sessionId}/minutes`, {
      method: "PATCH",
      body: JSON.stringify(patch)
    });
  }

  regenerateMinutes(sessionId: string): Promise<MeetingMinutes> {
    return this.request(`/sessions/${sessionId}/minutes/regenerate`, { method: "POST" });
  }

  async getRecording(sessionId: string): Promise<Blob> {
    const response = await this.fetcher(`${this.baseUrl}/sessions/${sessionId}/recording`, {
      headers: { Authorization: `Bearer ${this.token}` }
    });
    if (!response.ok) throw new HelperError(response.status, "recording_error", "Không tải được audio.");
    return response.blob();
  }
}
