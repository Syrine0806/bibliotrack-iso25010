import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, request, setUnauthorizedHandler, tokenStore } from "./client";

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

describe("client HTTP", () => {
  beforeEach(() => tokenStore.clear());
  afterEach(() => vi.unstubAllGlobals());

  it("[EF-01] ajoute le jeton Bearer et sérialise le corps JSON", async () => {
    tokenStore.set("abc");
    const fetchMock = mockFetch(201, { id: 1 });
    const result = await api.post<{ id: number }>("/loans", { user_id: 3 });
    expect(result).toEqual({ id: 1 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/loans");
    expect(init.headers.Authorization).toBe("Bearer abc");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"user_id":3}');
  });

  it("n'envoie pas le jeton quand auth=false (connexion)", async () => {
    tokenStore.set("abc");
    const fetchMock = mockFetch(200, {});
    await request("POST", "/auth/login", { body: {}, auth: false });
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBeUndefined();
  });

  it("construit la query string", async () => {
    const fetchMock = mockFetch(200, { items: [] });
    await api.get("/books", { q: "dune", page: 2, empty: "" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/books?q=dune&page=2");
  });

  it("retourne undefined pour une réponse 204", async () => {
    mockFetch(204);
    await expect(api.del("/books/1")).resolves.toBeUndefined();
  });

  it("transforme une erreur métier 409 en ApiError avec code de règle", async () => {
    mockFetch(409, { detail: "Quota atteint", code: "RG-02" });
    const err = (await api.post("/loans", {}).catch((e) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.code).toBe("RG-02");
    expect(err.message).toBe("Quota atteint");
  });

  it("[EQ-SEC-02] déclenche la déconnexion sur 401", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    mockFetch(401, { detail: "Jeton invalide" });
    await expect(api.get("/auth/me")).rejects.toThrow("Jeton invalide");
    expect(handler).toHaveBeenCalledOnce();
  });

  it("[EQ-FIA-03] signale un serveur injoignable (panne réseau)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.get("/books")).rejects.toMatchObject({ status: 0, message: expect.stringMatching(/injoignable/) });
  });

  it("[EQ-FIA-03] gère une réponse d'erreur non JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })));
    await expect(api.get("/books")).rejects.toMatchObject({ status: 502, message: "Erreur interne du serveur." });
  });
});
