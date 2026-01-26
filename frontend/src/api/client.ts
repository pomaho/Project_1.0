const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";

function getAccessToken(): string | null {
  const tokens = getStoredTokens();
  return tokens?.accessToken ?? null;
}

export function withAccessToken(url: string): string {
  const token = getAccessToken();
  if (!token) return url;
  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(token)}`;
}

type StoredTokens = {
  accessToken: string;
  refreshToken: string;
};

function getStoredTokens(): StoredTokens | null {
  const raw = localStorage.getItem("photo_search_tokens");
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredTokens;
  } catch {
    return null;
  }
}

function setStoredTokens(tokens: StoredTokens | null) {
  if (!tokens) {
    localStorage.removeItem("photo_search_tokens");
    return;
  }
  localStorage.setItem("photo_search_tokens", JSON.stringify(tokens));
}

async function refreshAccessToken(): Promise<string | null> {
  const tokens = getStoredTokens();
  if (!tokens?.refreshToken) return null;
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refreshToken }),
  });
  if (!response.ok) {
    setStoredTokens(null);
    return null;
  }
  const data = (await response.json()) as { access_token: string };
  setStoredTokens({ ...tokens, accessToken: data.access_token });
  return data.access_token;
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const makeRequest = async (tokenOverride?: string) => {
    const token = tokenOverride ?? getAccessToken();
    return fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {}),
      },
    });
  };

  let response = await makeRequest();
  if (response.status === 401) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await makeRequest(newToken);
    }
  }

  if (!response.ok) {
    throw new Error(`API error ${response.status}`);
  }

  return (await response.json()) as T;
}
