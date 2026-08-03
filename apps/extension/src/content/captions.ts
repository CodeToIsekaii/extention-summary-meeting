import type { CaptionSegment } from "../shared/types";

const REGION_SELECTORS = [
  '[role="region"][aria-label*="Caption" i]',
  '[aria-live="polite"]',
  '[data-caption-region]'
];

function compactText(value: string | null | undefined): string {
  return (value ?? "").replace(/\s+/g, " ").trim();
}

export function extractCaptionCandidates(root: Document, nowMs: number): CaptionSegment[] {
  const regions = Array.from(root.querySelectorAll<HTMLElement>(REGION_SELECTORS.join(",")));
  const candidates: CaptionSegment[] = [];
  for (const region of regions) {
    const rows = Array.from(
      region.querySelectorAll<HTMLElement>("[data-speaker-name], [data-speaker-id]")
    );
    for (const row of rows) {
      const speaker = compactText(
        row.dataset.speakerName ?? row.querySelector<HTMLElement>("[data-speaker-name]")?.innerText
      );
      const parts = Array.from(row.querySelectorAll<HTMLElement>("span, [data-caption-text]"))
        .map((node) => compactText(node.innerText || node.textContent))
        .filter(Boolean);
      const text = compactText(parts.filter((part) => part !== speaker).join(" "));
      if (text) {
        candidates.push({
          start_ms: nowMs,
          end_ms: nowMs,
          speaker: speaker || null,
          text
        });
      }
    }
    for (const textNode of region.querySelectorAll<HTMLElement>('[jsname="tgaKEf"]')) {
      const row = textNode.parentElement;
      const speaker = compactText(row?.querySelector<HTMLElement>('[jsname="YSxPC"]')?.textContent);
      const text = compactText(textNode.textContent);
      if (text && !candidates.some((item) => item.speaker === (speaker || null) && item.text === text)) {
        candidates.push({
          start_ms: nowMs,
          end_ms: nowMs,
          speaker: speaker || null,
          text
        });
      }
    }
  }
  return candidates;
}

export class CaptionAccumulator {
  private lastSeen = new Map<string, number>();

  accept(captions: CaptionSegment[]): CaptionSegment[] {
    return captions.filter((caption) => {
      const fingerprint = `${caption.speaker ?? ""}|${caption.text}`;
      const seenAt = this.lastSeen.get(fingerprint);
      if (seenAt !== undefined && caption.start_ms - seenAt < 10_000) return false;
      this.lastSeen.set(fingerprint, caption.start_ms);
      return true;
    });
  }
}
