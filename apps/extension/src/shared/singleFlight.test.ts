import { describe, expect, it } from "vitest";

import { SingleFlight } from "./singleFlight";

describe("SingleFlight", () => {
  it("makes concurrent callers wait for the same operation", async () => {
    let finish!: (value: string) => void;
    let calls = 0;
    const gate = new SingleFlight<string>();
    const operation = () => {
      calls += 1;
      return new Promise<string>((resolve) => {
        finish = resolve;
      });
    };

    const first = gate.run(operation);
    const second = gate.run(operation);

    expect(calls).toBe(1);
    finish("stopped");
    await expect(Promise.all([first, second])).resolves.toEqual(["stopped", "stopped"]);

    await gate.run(async () => "next");
    expect(calls).toBe(1);
  });
});
