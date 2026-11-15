/** Client HTTP unique : jeton Bearer, sérialisation JSON, erreurs normalisées en français. */

const TOKEN_KEY = "bibliotrack.token";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const tokenStore = {
  get: (): string | null => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

type Query = Record<string, string | number | boolean | null | undefined>;

export function buildQuery(params: Query = {}): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

interface ValidationIssue {
  loc?: (string | number)[];
  msg?: string;
}

export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return (detail as ValidationIssue[])
      .map((d) => `${(d.loc ?? []).slice(1).join(".") || "champ"} : ${d.msg ?? "invalide"}`)
      .join(" ; ");
  }
  if (status === 503) return "Service temporairement indisponible, réessayez dans un instant.";
  if (status >= 500) return "Erreur interne du serveur.";
  return `Erreur ${status}`;
}

let onUnauthorized: () => void = () => undefined;
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

interface RequestOptions {
  body?: unknown;
  query?: Query;
  auth?: boolean;
}

function buildHeaders(options: RequestOptions): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json" };
  const token = tokenStore.get();
  if (token && options.auth !== false) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  return headers;
}

async function send(method: string, path: string, options: RequestOptions): Promise<Response> {
  try {
    return await fetch(`/api${path}${buildQuery(options.query)}`, {
      method,
      headers: buildHeaders(options),
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "Serveur injoignable : vérifiez votre connexion.");
  }
}

export async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const response = await send(method, path, options);
  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);
  if (response.ok) return body as T;
  if (response.status === 401 && options.auth !== false) onUnauthorized();
  throw new ApiError(response.status, errorMessage(response.status, body), body?.code);
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>("GET", path, { query }),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, { body }),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, { body }),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, { body }),
  del: (path: string) => request<void>("DELETE", path),
};
