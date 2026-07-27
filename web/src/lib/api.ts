const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "";

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  const data = (await res.json().catch(() => ({}))) as T;
  if (!res.ok) {
    throw new Error(
      (data as { error?: string }).error || `HTTP ${res.status}`,
    );
  }
  return data;
}

export const api = {
  login: (username: string, password: string) =>
    apiFetch<import("./api-types").LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () =>
    apiFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  me: () => apiFetch<import("./api-types").AuthMeResponse>("/api/auth/me"),
  register: (username: string, password: string, role?: string) =>
    apiFetch<{ ok: boolean }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password, role }),
    }),
  health: () => apiFetch<import("./api-types").HealthResponse>("/health"),
  capabilities: () =>
    apiFetch<import("./api-types").BackendCapabilities>(
      "/api/backend/capabilities",
    ),
  candidates: () =>
    apiFetch<import("./api-types").CandidatesResponse>(
      "/v1/accounts/candidates",
    ),
  quota: () => apiFetch<import("./api-types").QuotaResponse>("/v1/quota"),
  listUsers: () =>
    apiFetch<import("./api-types").UsersListResponse>("/api/admin/users"),
  setUserDisabled: (userId: string, disabled: boolean) =>
    apiFetch<{ ok: boolean }>(`/api/admin/users/${userId}/disabled`, {
      method: "POST",
      body: JSON.stringify({ disabled }),
    }),
  chat: async (
    messages: { role: string; content: string }[],
    stream = false,
  ) => {
    const body = JSON.stringify({
      model: "gpt-4o-mini",
      messages,
      stream,
    });
    if (stream) {
      return fetch(`${API_BASE}/v1/chat/completions`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body,
      });
    }
    return apiFetch<{ choices?: { message?: { content?: string } }[] }>(
      "/v1/chat/completions",
      { method: "POST", body },
    );
  },
  image: (prompt: string, size = "1024x1024") =>
    apiFetch<{ data?: { b64_json?: string }[] }>("/v1/images/generations", {
      method: "POST",
      body: JSON.stringify({
        model: "gpt-image-2",
        prompt,
        n: 1,
        size,
        response_format: "b64_json",
      }),
    }),
};
