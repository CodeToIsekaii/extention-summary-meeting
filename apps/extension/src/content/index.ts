import { CaptionAccumulator, extractCaptionCandidates } from "./captions";
import { HelperClient } from "../shared/helperClient";

let observer: MutationObserver | null = null;
let startedAt = 0;
let client: HelperClient | null = null;
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
    client = new HelperClient(message.token);
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
