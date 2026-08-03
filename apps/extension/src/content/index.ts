import { CaptionAccumulator, extractCaptionCandidates } from "./captions";

const BASE_URL = "http://127.0.0.1:8765/v1";

class CaptionUploadClient {
  constructor(private readonly token: string) {}

  async uploadCaptions(
    sessionId: string,
    captions: Array<{
      start_ms: number;
      end_ms: number;
      speaker: string | null;
      text: string;
    }>
  ): Promise<void> {
    const response = await fetch(`${BASE_URL}/sessions/${sessionId}/captions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(captions)
    });
    if (!response.ok) {
      throw new Error(`Caption upload failed with HTTP ${response.status}`);
    }
  }
}

let observer: MutationObserver | null = null;
let startedAt = 0;
let client: CaptionUploadClient | null = null;
let sessionId: string | null = null;
let accumulator = new CaptionAccumulator();
let uploadChain = Promise.resolve();

function stopCaptions(): Promise<void> {
  observer?.disconnect();
  observer = null;
  const pendingUploads = uploadChain;
  client = null;
  sessionId = null;
  uploadChain = Promise.resolve();
  return pendingUploads;
}

function scan(): void {
  if (!client || !sessionId) return;
  const elapsed = Date.now() - startedAt;
  const fresh = accumulator.accept(extractCaptionCandidates(document, elapsed));
  if (!fresh.length) return;
  const activeClient = client;
  const activeSession = sessionId;
  uploadChain = uploadChain
    .then(() => activeClient.uploadCaptions(activeSession, fresh))
    .then(() => undefined)
    .catch(() => undefined);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "START_CAPTIONS") {
    void stopCaptions();
    startedAt = Date.now();
    client = new CaptionUploadClient(message.token);
    sessionId = message.sessionId;
    accumulator = new CaptionAccumulator();
    observer = new MutationObserver(scan);
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
    scan();
  }
  if (message.type === "STOP_CAPTIONS") {
    void stopCaptions().then(() => sendResponse({ ok: true }));
    return true;
  }
  return false;
});
