import { useCallback, useEffect, useMemo, useReducer, useState } from "react";
import { HelperClient, type SessionManifest } from "../shared/helperClient";
import { initialRecordingState, recordingReducer } from "../shared/state";
import type { MeetingMinutes } from "../shared/types";
import { RecordingPanel } from "./RecordingPanel";

interface StoredSettings {
  helperToken?: string;
  activeSession?: { id: string; startedAt: number };
}

export function App() {
  const [state, dispatch] = useReducer(recordingReducer, initialRecordingState);
  const [token, setToken] = useState("");
  const [tokenDraft, setTokenDraft] = useState("");
  const [helperReady, setHelperReady] = useState(false);
  const [canStartWithDisk, setCanStartWithDisk] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [checkpoint, setCheckpoint] = useState<MeetingMinutes | null>(null);
  const [recoverable, setRecoverable] = useState<SessionManifest[]>([]);
  const [processingPaused, setProcessingPaused] = useState(false);
  const [diskWarning, setDiskWarning] = useState<string | null>(null);
  const [pairingMessage, setPairingMessage] = useState<string | null>(null);
  const [retryingSessionId, setRetryingSessionId] = useState<string | null>(null);
  const client = useMemo(() => new HelperClient(token), [token]);

  const refreshHelper = useCallback(async () => {
    try {
      const health = await client.health();
      setHelperReady(health.status === "ok");
      setCanStartWithDisk(health.disk.can_start);
      if (health.disk.must_stop) {
        setDiskWarning(
          `Ổ D chỉ còn ${health.disk.free_gb.toFixed(2)} GB. Ghi âm sẽ dừng an toàn.`
        );
      } else if (health.disk.warning) {
        setDiskWarning(
          `Ổ D chỉ còn ${health.disk.free_gb.toFixed(2)} GB. Hãy sớm dừng và giải phóng dung lượng.`
        );
      } else if (!health.disk.can_start) {
        setDiskWarning(
          `Ổ D còn ${health.disk.free_gb.toFixed(2)} GB; cần ít nhất 5 GB để bắt đầu.`
        );
      } else {
        setDiskWarning(null);
      }
      if (token) setRecoverable(await client.listRecoverable());
    } catch {
      setHelperReady(false);
      setCanStartWithDisk(false);
      setDiskWarning(null);
    }
  }, [client, token]);

  useEffect(() => {
    void chrome.storage.local.get(["helperToken", "activeSession"]).then(async (stored: StoredSettings) => {
      const savedToken = stored.helperToken ?? "";
      setToken(savedToken);
      setTokenDraft(savedToken);
      if (stored.activeSession) {
        dispatch({ type: "START_REQUESTED" });
        dispatch({
          type: "STARTED",
          sessionId: stored.activeSession.id,
          startedAt: stored.activeSession.startedAt
        });
        try {
          const savedClient = new HelperClient(savedToken);
          const job = await savedClient.getStatus(stored.activeSession.id);
          if (job.status === "processing" || job.status === "paused") {
            dispatch({ type: "PROCESSING" });
            setProcessingPaused(job.status === "paused");
          } else if (job.status === "completed") {
            dispatch({ type: "COMPLETED" });
            await chrome.storage.local.remove("activeSession");
          } else if (job.status === "failed") {
            dispatch({ type: "FAILED", message: job.error ?? "Phiên trước xử lý thất bại." });
          } else {
            const captures = await new Promise<chrome.tabCapture.CaptureInfo[]>((resolve) => {
              chrome.tabCapture.getCapturedTabs(resolve);
            });
            if (!captures.some((capture) => capture.status === "active")) {
              dispatch({
                type: "FAILED",
                message: "Phiên ghi trước đã bị gián đoạn. Chọn Xử lý lại trong Recovery."
              });
              await chrome.storage.local.remove("activeSession");
            }
          }
        } catch (error) {
          // A session can have been deleted manually while Chrome still has its id.
          if (error instanceof Error && /404|not found|session_not_found/i.test(error.message)) {
            await chrome.storage.local.remove("activeSession");
            dispatch({ type: "RESET" });
          }
        }
      }
    });
  }, []);

  useEffect(() => {
    void refreshHelper();
    const interval = window.setInterval(() => void refreshHelper(), 5000);
    return () => window.clearInterval(interval);
  }, [refreshHelper]);

  useEffect(() => {
    if (state.phase !== "recording" || state.startedAt === null) return;
    const tick = () => setElapsedMs(Date.now() - state.startedAt!);
    tick();
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [state.phase, state.startedAt]);

  useEffect(() => {
    if (state.phase !== "processing" || !state.sessionId) return;
    const session = state.sessionId;
    const interval = window.setInterval(async () => {
      try {
        const job = await client.getStatus(session);
        setProcessingPaused(job.status === "paused");
        if (job.status === "completed") {
          dispatch({ type: "COMPLETED" });
          await chrome.storage.local.remove("activeSession");
          window.clearInterval(interval);
        } else if (job.status === "failed") {
          dispatch({ type: "FAILED", message: job.error ?? "Xử lý cuộc họp thất bại." });
          window.clearInterval(interval);
        }
      } catch {
        // Continue polling; helper may be busy or restarting.
      }
    }, 2000);
    return () => window.clearInterval(interval);
  }, [client, state.phase, state.sessionId]);

  useEffect(() => {
    const listener = (message: { type: string; error?: string }) => {
      if (message.type === "CAPTURE_PROCESSING") dispatch({ type: "PROCESSING" });
      if (message.type === "CAPTURE_FAILED") {
        dispatch({ type: "FAILED", message: message.error ?? "Ghi âm bị gián đoạn." });
      }
    };
    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const saveToken = async () => {
    const normalized = tokenDraft.trim();
    await chrome.storage.local.set({ helperToken: normalized });
    setToken(normalized);
    setPairingMessage(normalized ? "Đã lưu token backend local." : null);
  };

  const autoPair = async () => {
    try {
      setPairingMessage("Đang lấy token từ backend local...");
      const pairingClient = new HelperClient("");
      const pairing = await pairingClient.pair();
      const nextToken = pairing.auth_token.trim();
      await chrome.storage.local.set({ helperToken: nextToken });
      setToken(nextToken);
      setTokenDraft(nextToken);
      setPairingMessage("Ghép cặp tự động thành công.");
    } catch (error) {
      setPairingMessage(
        error instanceof Error ? error.message : "Không lấy được token từ backend local."
      );
    }
  };

  const start = async () => {
    try {
      dispatch({ type: "START_REQUESTED" });
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab?.url?.startsWith("https://meet.google.com/")) {
        throw new Error("Hãy mở Google Meet trong tab hiện tại.");
      }
      const title = tab.title?.replace(/\s*-\s*Google Meet.*$/i, "").trim() || `Google Meet ${new Date().toLocaleString("vi-VN")}`;
      const session = await client.createSession(title, tab.url);
      const startedAt = Date.now();
      await chrome.storage.local.set({ activeSession: { id: session.id, startedAt } });
      const response = await chrome.runtime.sendMessage({
        type: "START_CAPTURE",
        sessionId: session.id,
        token
      });
      if (!response?.ok) throw new Error(response?.error ?? "Không thể bắt đầu capture.");
      dispatch({ type: "STARTED", sessionId: session.id, startedAt });
    } catch (error) {
      dispatch({ type: "FAILED", message: error instanceof Error ? error.message : String(error) });
    }
  };

  const stop = async () => {
    try {
      dispatch({ type: "STOP_REQUESTED" });
      const response = await chrome.runtime.sendMessage({ type: "STOP_CAPTURE" });
      if (!response?.ok) throw new Error(response?.error ?? "Không thể hoàn tất audio.");
      dispatch({ type: "PROCESSING" });
    } catch (error) {
      dispatch({ type: "FAILED", message: error instanceof Error ? error.message : String(error) });
    }
  };

  const createCheckpoint = async () => {
    if (!state.sessionId) return;
    try {
      setCheckpoint(await client.checkpoint(state.sessionId));
    } catch (error) {
      dispatch({ type: "FAILED", message: error instanceof Error ? error.message : String(error) });
    }
  };

  const openMinutes = (sessionId = state.sessionId) => {
    if (!sessionId) return;
    void chrome.tabs.create({ url: chrome.runtime.getURL(`minutes.html?session=${encodeURIComponent(sessionId)}`) });
  };

  const deleteRecovery = async (sessionId: string) => {
    await client.deleteSession(sessionId);
    setRecoverable((items) => items.filter((item) => item.id !== sessionId));
  };

  const retryRecovery = async (session: SessionManifest) => {
    if (retryingSessionId) return;
    try {
      setRetryingSessionId(session.id);
      setPairingMessage(`Đang xử lý lại “${session.title}”…`);
      const job = await client.retry(session.id);
      await chrome.storage.local.set({ activeSession: { id: session.id, startedAt: Date.now() } });
      dispatch({ type: "START_REQUESTED" });
      dispatch({ type: "STARTED", sessionId: session.id, startedAt: Date.now() });
      if (job.status === "processing" || job.status === "paused") {
        dispatch({ type: "PROCESSING" });
        setProcessingPaused(job.status === "paused");
      }
      setRecoverable((items) => items.map((item) => item.id === session.id ? { ...item, status: "processing" } : item));
    } catch (error) {
      if (error instanceof Error && /404|not found|session_not_found/i.test(error.message)) {
        setRecoverable((items) => items.filter((item) => item.id !== session.id));
        await chrome.storage.local.remove("activeSession");
      }
      setPairingMessage(error instanceof Error ? error.message : "Không thể xử lý lại phiên này.");
    } finally {
      setRetryingSessionId(null);
    }
  };

  const pauseProcessing = async () => {
    if (!state.sessionId) return;
    await client.pause(state.sessionId);
    setProcessingPaused(true);
  };

  const resumeProcessing = async () => {
    if (!state.sessionId) return;
    await client.resume(state.sessionId);
    setProcessingPaused(false);
  };

  const useFastMode = async () => {
    if (!state.sessionId) return;
    await client.fast(state.sessionId);
    setProcessingPaused(false);
  };

  return (
    <>
      <RecordingPanel
        state={state}
        helperReady={helperReady}
        canStartWithDisk={canStartWithDisk}
        tokenConfigured={Boolean(token)}
        elapsedMs={elapsedMs}
        checkpoint={checkpoint}
        processingPaused={processingPaused}
        diskWarning={diskWarning}
        onStart={start}
        onStop={stop}
        onCheckpoint={createCheckpoint}
        onOpenMinutes={() => openMinutes()}
        onPause={() => void pauseProcessing()}
        onResume={() => void resumeProcessing()}
        onFast={() => void useFastMode()}
      />

      <section className="settings-card">
        <details>
          <summary>Cài đặt backend local</summary>
          <label htmlFor="helper-token">Token ghép cặp</label>
          <input
            id="helper-token"
            type="password"
            value={tokenDraft}
            onChange={(event) => setTokenDraft(event.target.value)}
            placeholder="Dán token từ config/settings.json"
          />
          <div className="primary-actions">
            <button className="button button-secondary" onClick={saveToken}>Lưu token</button>
            <button className="button button-secondary" onClick={() => void autoPair()}>
              Ghép cặp tự động
            </button>
          </div>
          {pairingMessage ? <p>{pairingMessage}</p> : null}
          <p>Dữ liệu và model được giữ trong thư mục runtime trên ổ D.</p>
        </details>
      </section>

      {recoverable.length ? (
        <section className="recovery-card">
          <p className="eyebrow">RECOVERY</p>
          <h2>Phiên chưa hoàn tất</h2>
          {recoverable.map((session) => (
            <div className="recovery-row" key={session.id}>
              <div><strong>{session.title}</strong><span>{session.status}</span></div>
              <div className="recovery-actions">
                <button className="button button-secondary" disabled={retryingSessionId === session.id} onClick={() => void retryRecovery(session)}>
                  {retryingSessionId === session.id ? "Đang xử lý…" : "Xử lý lại"}
                </button>
                <button className="button button-quiet" onClick={() => void deleteRecovery(session.id)}>Xóa</button>
              </div>
            </div>
          ))}
        </section>
      ) : null}
    </>
  );
}
