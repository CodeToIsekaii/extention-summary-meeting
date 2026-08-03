import { describe, expect, it } from "vitest";
import { BoundedChunkQueue } from "./chunkQueue";

describe("BoundedChunkQueue", () => {
  it("keeps failed chunks in sequence and removes them after acknowledgement", () => {
    const queue = new BoundedChunkQueue(30_000);
    queue.push({ source: "remote", sequence: 0, durationMs: 5000, blob: new Blob(["a"]) });
    queue.push({ source: "remote", sequence: 1, durationMs: 5000, blob: new Blob(["b"]) });

    expect(queue.peek()?.sequence).toBe(0);
    queue.acknowledge("remote", 0);
    expect(queue.peek()?.sequence).toBe(1);
  });

  it("signals overflow rather than persisting more than 30 seconds", () => {
    const queue = new BoundedChunkQueue(30_000);
    for (let sequence = 0; sequence < 6; sequence += 1) {
      queue.push({
        source: "me",
        sequence,
        durationMs: 5000,
        blob: new Blob([String(sequence)])
      });
    }

    expect(() =>
      queue.push({ source: "me", sequence: 6, durationMs: 5000, blob: new Blob(["overflow"]) })
    ).toThrow("Audio buffer exceeded 30000ms");
  });

  it("can discard a failed session before the next recording starts", () => {
    const queue = new BoundedChunkQueue(30_000);
    queue.push({ source: "remote", sequence: 0, durationMs: 5000, blob: new Blob(["a"]) });

    queue.clear();

    expect(queue.size).toBe(0);
  });
});
