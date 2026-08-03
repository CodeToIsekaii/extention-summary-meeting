import { describe, expect, it } from "vitest";
import { CaptionAccumulator, extractCaptionCandidates } from "./captions";

describe("Meet captions", () => {
  it("extracts a speaker and text from a caption-like region", () => {
    document.body.innerHTML = `
      <div role="region" aria-label="Captions">
        <div data-speaker-name="Lan"><span>Lan</span><span>Chốt deadline thứ Sáu.</span></div>
      </div>`;

    const candidates = extractCaptionCandidates(document, 1200);

    expect(candidates).toEqual([
      { start_ms: 1200, end_ms: 1200, speaker: "Lan", text: "Chốt deadline thứ Sáu." }
    ]);
  });

  it("supports Meet jsname caption markup without data attributes", () => {
    document.body.innerHTML = `
      <div role="region" aria-label="Captions">
        <div><span jsname="YSxPC">Huy</span><span jsname="tgaKEf">Tôi nhận task này.</span></div>
      </div>`;

    expect(extractCaptionCandidates(document, 2000)).toEqual([
      { start_ms: 2000, end_ms: 2000, speaker: "Huy", text: "Tôi nhận task này." }
    ]);
  });

  it("deduplicates repeated MutationObserver snapshots", () => {
    const accumulator = new CaptionAccumulator();
    const caption = {
      start_ms: 1000,
      end_ms: 1600,
      speaker: "Minh",
      text: "Tôi sẽ kiểm tra."
    };

    expect(accumulator.accept([caption])).toEqual([caption]);
    expect(accumulator.accept([caption])).toEqual([]);
  });

  it("suppresses the same visible caption across nearby observer timestamps", () => {
    const accumulator = new CaptionAccumulator();

    expect(
      accumulator.accept([
        { start_ms: 1000, end_ms: 1000, speaker: "Minh", text: "Tôi sẽ kiểm tra." }
      ])
    ).toHaveLength(1);
    expect(
      accumulator.accept([
        { start_ms: 1500, end_ms: 1500, speaker: "Minh", text: "Tôi sẽ kiểm tra." }
      ])
    ).toHaveLength(0);
  });
});
