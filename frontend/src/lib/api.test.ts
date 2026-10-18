import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, setUnauthorizedHandler } from "./api";

function mockFetch(status: number, body?: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  vi.unstubAllGlobals();
  setUnauthorizedHandler(null);
});

describe("api client", () => {
  it("sends the session cookie and never an Authorization header", async () => {
    const fetchMock = mockFetch(200, []);

    await api.listCollections();

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/collections");
    expect(init.credentials).toBe("same-origin");
    expect(init.headers.Authorization).toBeUndefined();
  });

  it("tells the app when the session is no longer valid", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetch(401, { detail: "Could not validate credentials" });

    await expect(api.listCollections()).rejects.toMatchObject({ status: 401 });

    expect(handler).toHaveBeenCalledOnce();
  });

  it("does not treat a wrong password as an expired session", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetch(401, { detail: "Incorrect email or password" });

    await expect(api.login("a@b.co", "wrong")).rejects.toThrow("Incorrect email or password");
    expect(handler).not.toHaveBeenCalled();
  });

  it("turns validation errors into a readable message", async () => {
    mockFetch(422, {
      detail: [{ loc: ["body", "password"], msg: "String should have at least 8 characters" }],
    });

    await expect(
      api.register({ email: "a@b.co", password: "short", full_name: "A" }),
    ).rejects.toThrow("password: String should have at least 8 characters");
  });

  it("returns undefined for 204 responses", async () => {
    mockFetch(204);
    await expect(api.deleteCollection("x")).resolves.toBeUndefined();
  });

  it("logs out through the API", async () => {
    const fetchMock = mockFetch(204);
    await api.logout();
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/auth/logout");
    expect(init.method).toBe("POST");
  });

  it("reports network failures as status 0", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await api.health().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
  });
});
