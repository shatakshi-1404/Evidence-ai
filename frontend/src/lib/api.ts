import type {
  AskResponse,
  Chunk,
  Collection,
  DocumentItem,
  EvalReport,
  Health,
  HistoryDetail,
  HistoryItem,
  SearchResponse,
  User,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Called when the server says our token is no longer valid (expired, etc.).
let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

/** FastAPI errors are either {detail: "text"} or {detail: [{loc, msg}, ...]}. */
function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      const first = detail[0] as { msg?: unknown; loc?: unknown };
      if (typeof first?.msg === "string") {
        const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : null;
        return typeof field === "string" ? `${field}: ${first.msg}` : first.msg;
      }
    }
  }
  return fallback;
}

type RequestOptions = {
  method?: string;
  json?: unknown;
  body?: BodyInit;
  auth?: boolean;
};

async function request<T>(
  path: string,
  { method = "GET", json, body, auth = true }: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (json !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      headers,
      credentials: "same-origin", // sends the httpOnly session cookie
      body: json !== undefined ? JSON.stringify(json) : body,
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }

  if (response.status === 401 && auth) {
    unauthorizedHandler?.();
  }

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      // The error body wasn't JSON; use the generic message.
    }
    throw new ApiError(response.status, messageFrom(parsed, `Request failed (${response.status})`));
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<Health>("/health", { auth: false }),

  register: (payload: { email: string; password: string; full_name: string }) =>
    request<User>("/auth/register", { method: "POST", json: payload, auth: false }),

  login: async (email: string, password: string): Promise<void> => {
    // The login endpoint expects a form (OAuth2 style), with the email as "username".
    // On success the server sets the httpOnly session cookie; there is nothing to store.
    const form = new URLSearchParams({ username: email, password });
    await request<unknown>("/auth/login", { method: "POST", body: form, auth: false });
  },

  logout: () => request<void>("/auth/logout", { method: "POST", auth: false }),

  getEvaluation: () => request<EvalReport>("/evaluation/latest"),

  me: () => request<User>("/auth/me"),

  listCollections: () => request<Collection[]>("/collections"),
  createCollection: (name: string) =>
    request<Collection>("/collections", { method: "POST", json: { name } }),
  deleteCollection: (id: string) => request<void>(`/collections/${id}`, { method: "DELETE" }),

  listDocuments: (collectionId: string) =>
    request<DocumentItem[]>(`/collections/${collectionId}/documents`),
  uploadDocument: (collectionId: string, file: File) => {
    const form = new FormData();
    form.append("file", file); // the browser sets the multipart Content-Type itself
    return request<DocumentItem>(`/collections/${collectionId}/documents`, {
      method: "POST",
      body: form,
    });
  },
  getDocument: (id: string) => request<DocumentItem>(`/documents/${id}`),
  listChunks: (id: string, limit: number, offset: number) =>
    request<Chunk[]>(`/documents/${id}/chunks?limit=${limit}&offset=${offset}`),
  retryDocument: (id: string) => request<DocumentItem>(`/documents/${id}/retry`, { method: "POST" }),
  deleteDocument: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),

  search: (query: string, collectionId: string | null, limit: number) =>
    request<SearchResponse>("/search", {
      method: "POST",
      json: { query, collection_id: collectionId, limit },
    }),
  ask: (question: string, collectionId: string | null) =>
    request<AskResponse>("/ask", {
      method: "POST",
      json: { question, collection_id: collectionId },
    }),

  listHistory: (limit: number, offset: number) =>
    request<HistoryItem[]>(`/history?limit=${limit}&offset=${offset}`),
  getHistory: (id: string) => request<HistoryDetail>(`/history/${id}`),
  deleteHistory: (id: string) => request<void>(`/history/${id}`, { method: "DELETE" }),
  clearHistory: () => request<void>("/history", { method: "DELETE" }),
};
