import { createContext, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type Tokens = {
  accessToken: string;
  refreshToken: string;
};

type AuthContextValue = {
  tokens: Tokens | null;
  setTokens: (tokens: Tokens | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = "photo_search_tokens";

function loadTokens(): Tokens | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokensState] = useState<Tokens | null>(() => loadTokens());

  const setTokens = (next: Tokens | null) => {
    setTokensState(next);
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  const logout = () => setTokens(null);
  const value = useMemo(() => ({ tokens, setTokens, logout }), [tokens]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("AuthProvider missing");
  }
  return ctx;
}
