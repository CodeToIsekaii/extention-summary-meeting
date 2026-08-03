import { useEffect, useMemo, useState } from "react";
import { HelperClient } from "../shared/helperClient";
import type { MeetingMinutes } from "../shared/types";
import { MinutesEditor } from "./MinutesEditor";

export function App() {
  const sessionId = useMemo(() => new URLSearchParams(location.search).get("session"), []);
  const [client, setClient] = useState<HelperClient | null>(null);
  const [minutes, setMinutes] = useState<MeetingMinutes | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) {
      setError("Thiếu mã cuộc họp.");
      return;
    }
    let objectUrl: string | null = null;
    void chrome.storage.local.get("helperToken").then(async ({ helperToken }) => {
      if (!helperToken) throw new Error("Chưa cấu hình token backend local trong side panel.");
      const helper = new HelperClient(helperToken);
      setClient(helper);
      const [loadedMinutes, recording] = await Promise.all([
        helper.getMinutes(sessionId),
        helper.getRecording(sessionId)
      ]);
      objectUrl = URL.createObjectURL(recording);
      setMinutes(loadedMinutes);
      setAudioUrl(objectUrl);
    }).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason)));
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [sessionId]);

  if (error) return <main className="loading-shell"><h1>Không mở được biên bản</h1><p role="alert">{error}</p></main>;
  if (!minutes || !client || !sessionId) return <main className="loading-shell"><p>Đang tải biên bản từ ổ D…</p></main>;

  return (
    <MinutesEditor
      initialMinutes={minutes}
      audioUrl={audioUrl}
      onSave={async (updated) => setMinutes(await client.updateMinutes(sessionId, updated))}
      onRegenerate={() => client.regenerateMinutes(sessionId)}
    />
  );
}
