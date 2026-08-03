type ExtensionMessage = {
  target?: string;
  type: string;
  sessionId?: string;
  token?: string;
};

let activeTabId: number | null = null;

function isMeetUrl(url?: string): boolean {
  return Boolean(url?.startsWith("https://meet.google.com/"));
}

async function stopActiveCapture(tabId: number, canMessageTab: boolean): Promise<void> {
  if (activeTabId !== tabId) return;
  if (canMessageTab) {
    await chrome.tabs.sendMessage(tabId, { type: "STOP_CAPTIONS" }).catch(() => undefined);
  }
  await chrome.runtime.sendMessage({ target: "offscreen", type: "STOP_CAPTURE_STREAMS" }).catch(() => undefined);
  activeTabId = null;
}

async function ensureOffscreenDocument(): Promise<void> {
  const offscreenUrl = chrome.runtime.getURL("offscreen.html");
  const contexts = await chrome.runtime.getContexts({
    contextTypes: [chrome.runtime.ContextType.OFFSCREEN_DOCUMENT],
    documentUrls: [offscreenUrl]
  });
  if (contexts.length > 0) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: [chrome.offscreen.Reason.USER_MEDIA, chrome.offscreen.Reason.BLOBS],
    justification: "Record tab and microphone audio and stream chunks to the local helper."
  });
}

function isMissingReceiverError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /Receiving end does not exist/i.test(error.message)
  );
}

async function sendOffscreenMessage(message: Record<string, unknown>, retry = true) {
  try {
    return await chrome.runtime.sendMessage(message);
  } catch (error) {
    if (retry && isMissingReceiverError(error)) {
      await new Promise((resolve) => window.setTimeout(resolve, 150));
      return chrome.runtime.sendMessage(message);
    }
    throw error;
  }
}

async function activeMeetTab(): Promise<chrome.tabs.Tab> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab.url?.startsWith("https://meet.google.com/")) {
    throw new Error("Hãy mở tab Google Meet trước khi bắt đầu ghi.");
  }
  return tab;
}

async function syncSidePanelForOpenTabs(): Promise<void> {
  const tabs = await chrome.tabs.query({});
  await Promise.all(
    tabs
      .filter((tab): tab is chrome.tabs.Tab & { id: number } => typeof tab.id === "number")
      .map((tab) =>
        chrome.sidePanel.setOptions({
          tabId: tab.id,
          enabled: isMeetUrl(tab.url)
        })
      )
  );
}

chrome.runtime.onInstalled.addListener(() => {
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  void syncSidePanelForOpenTabs();
});

chrome.runtime.onStartup.addListener(() => {
  void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
  void syncSidePanelForOpenTabs();
});

void chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
void syncSidePanelForOpenTabs();

chrome.action.onClicked.addListener((tab) => {
  if (!tab.id || !isMeetUrl(tab.url)) return;
  void chrome.sidePanel.setOptions({
    tabId: tab.id,
    path: "sidepanel.html",
    enabled: true,
  });
});

chrome.runtime.onMessage.addListener((message: ExtensionMessage, _sender, sendResponse) => {
  if (message.target === "offscreen") return false;
  if (message.type === "START_CAPTURE") {
    void (async () => {
      try {
        const tab = await activeMeetTab();
        activeTabId = tab.id!;
        const streamId = await new Promise<string>((resolve, reject) => {
          chrome.tabCapture.getMediaStreamId({ targetTabId: tab.id }, (value) => {
            if (chrome.runtime.lastError || !value) {
              reject(new Error(chrome.runtime.lastError?.message ?? "Không lấy được tab audio."));
            } else {
              resolve(value);
            }
          });
        });
        await ensureOffscreenDocument();
        await chrome.tabs.sendMessage(tab.id!, {
          type: "START_CAPTIONS",
          sessionId: message.sessionId,
          token: message.token
        }).catch(() => undefined);
        const result = await sendOffscreenMessage({
          target: "offscreen",
          type: "START_CAPTURE_STREAMS",
          streamId,
          sessionId: message.sessionId,
          token: message.token
        });
        sendResponse(result);
      } catch (error) {
        sendResponse({ ok: false, error: error instanceof Error ? error.message : String(error) });
      }
    })();
    return true;
  }
  if (message.type === "STOP_CAPTURE") {
    void (async () => {
      if (activeTabId !== null) {
        await chrome.tabs.sendMessage(activeTabId, { type: "STOP_CAPTIONS" }).catch(() => undefined);
      }
      const result = await sendOffscreenMessage({ target: "offscreen", type: "STOP_CAPTURE_STREAMS" });
      activeTabId = null;
      sendResponse(result);
    })();
    return true;
  }
  return false;
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeTabId) void stopActiveCapture(tabId, false);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url !== undefined) {
    void chrome.sidePanel.setOptions({ tabId, enabled: isMeetUrl(changeInfo.url) });
    if (tabId === activeTabId && !isMeetUrl(changeInfo.url)) {
      void stopActiveCapture(tabId, false);
    }
  } else if (changeInfo.status === "complete") {
    void chrome.sidePanel.setOptions({ tabId, enabled: isMeetUrl(tab.url) });
  }
});
