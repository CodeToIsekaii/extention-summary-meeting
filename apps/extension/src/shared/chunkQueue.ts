import type { AudioSource, ChunkEnvelope } from "./types";

export class BoundedChunkQueue {
  readonly maxDurationMs: number;
  private chunks: ChunkEnvelope[] = [];

  constructor(maxDurationMs: number) {
    this.maxDurationMs = maxDurationMs;
  }

  push(chunk: ChunkEnvelope): void {
    const bufferedDuration = this.chunks.reduce((sum, item) => sum + item.durationMs, 0);
    if (this.chunks.length > 0 && bufferedDuration + chunk.durationMs > this.maxDurationMs) {
      throw new Error(`Audio buffer exceeded ${this.maxDurationMs}ms`);
    }
    this.chunks.push(chunk);
    this.chunks.sort((left, right) => left.sequence - right.sequence);
  }

  peek(): ChunkEnvelope | undefined {
    return this.chunks[0];
  }

  acknowledge(source: AudioSource, sequence: number): void {
    this.chunks = this.chunks.filter(
      (item) => !(item.source === source && item.sequence === sequence)
    );
  }

  clear(): void {
    this.chunks = [];
  }

  get size(): number {
    return this.chunks.length;
  }
}
