import { describe, expect, it } from "vitest";
import { HelperClient, HelperError, isFatalUploadError } from "./helperClient";

describe("HelperClient", () => {
  it("sends authenticated session creation to loopback", async () => {
    const requests: Request[] = [];
    const fetcher: typeof fetch = async (input, init) => {
      const request = new Request(input, init);
      requests.push(request);
      return Response.json({ id: "session-1", status: "recording" }, { status: 201 });
    };
    const client = new HelperClient("secret", fetcher);

    const session = await client.createSession("Daily", "https://meet.google.com/abc");

    expect(session.id).toBe("session-1");
    expect(requests[0].url).toBe("http://127.0.0.1:8765/v1/sessions");
    expect(requests[0].headers.get("Authorization")).toBe("Bearer secret");
    expect(await requests[0].json()).toEqual({
      title: "Daily",
      meet_url: "https://meet.google.com/abc",
      language: "vi"
    });
  });

  it("uploads chunks with a lowercase SHA-256 checksum", async () => {
    let form: FormData | null = null;
    const fetcher: typeof fetch = async (_input, init) => {
      form = init?.body as FormData;
      return Response.json({ source: "me", sequence: 0, bytes_written: 3 });
    };
    const client = new HelperClient("secret", fetcher);

    await client.uploadChunk("session-1", {
      source: "me",
      sequence: 0,
      durationMs: 5000,
      blob: new Blob(["abc"], { type: "audio/webm" })
    });

    expect(form).not.toBeNull();
    expect((form as FormData).get("sha256_hex")).toBe(
      "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    );
    expect((form as FormData).get("duration_ms")).toBe("5000");
  });

  it("turns helper error payloads into stable HelperError instances", async () => {
    const fetcher: typeof fetch = async () =>
      Response.json(
        { detail: { code: "insufficient_disk_space", message: "Ổ D không đủ dung lượng." } },
        { status: 507 }
      );
    const client = new HelperClient("secret", fetcher);

    const operation = client.createSession("Daily", null);

    await expect(operation).rejects.toEqual(
      expect.objectContaining<Partial<HelperError>>({
        name: "HelperError",
        code: "insufficient_disk_space",
        status: 507
      })
    );
  });

  it("treats the emergency disk guard as fatal instead of bufferable", () => {
    expect(isFatalUploadError(new HelperError(507, "disk_stop", "Ổ D dưới 1 GB"))).toBe(true);
    expect(isFatalUploadError(new TypeError("temporary network failure"))).toBe(false);
  });

  it("deletes a recoverable session without trying to parse a 204 body", async () => {
    const fetcher: typeof fetch = async () => new Response(null, { status: 204 });
    const client = new HelperClient("secret", fetcher);

    await expect(client.deleteSession("session-1")).resolves.toBeUndefined();
  });

  it("can bootstrap a pairing token without sending Authorization", async () => {
    const requests: Request[] = [];
    const fetcher: typeof fetch = async (input, init) => {
      const request = new Request(input, init);
      requests.push(request);
      return Response.json({ auth_token: "bootstrapped-token" });
    };
    const client = new HelperClient("", fetcher);

    const pairing = await client.pair();

    expect(pairing.auth_token).toBe("bootstrapped-token");
    expect(requests[0].url).toBe("http://127.0.0.1:8765/v1/pairing");
    expect(requests[0].headers.get("Authorization")).toBeNull();
  });
});
