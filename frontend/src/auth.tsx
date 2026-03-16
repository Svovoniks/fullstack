import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useState } from "react";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

type UserData = {
  id: string;
  username: string;
  created_at: string;
};

type AuthSession = {
  accessToken: string;
  refreshToken: string;
  expiresAt: string;
  username: string;
};

type LoginPayload = {
  username: string;
  password: string;
};

type SignupPayload = LoginPayload;

type AuthApiResponse = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_at: string;
  user: UserData;
};

type AuthContextValue = {
  status: AuthStatus;
  session: AuthSession | null;
  login: (payload: LoginPayload) => Promise<void>;
  signup: (payload: SignupPayload) => Promise<void>;
  logout: () => Promise<void>;
  authFetch: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
};

const AUTH_STORAGE_KEY = "redaction.auth.session";
const REFRESH_THRESHOLD_MS = 1000 * 60 * 2;

const AuthContext = createContext<AuthContextValue | null>(null);

function parseSession(raw: string | null): AuthSession | null {
  if (!raw) {
    return null;
  }

  try {
    const parsed = JSON.parse(raw) as AuthSession;
    if (
      typeof parsed.accessToken !== "string" ||
      typeof parsed.refreshToken !== "string" ||
      typeof parsed.username !== "string" ||
      typeof parsed.expiresAt !== "string"
    ) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}

function readStoredSession() {
  const session = parseSession(window.localStorage.getItem(AUTH_STORAGE_KEY));
  if (session === null) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }

  return session;
}

function persistSession(session: AuthSession | null) {
  if (session === null) {
    window.localStorage.removeItem(AUTH_STORAGE_KEY);
    return;
  }

  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

function toSession(payload: AuthApiResponse): AuthSession {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresAt: payload.expires_at,
    username: payload.user.username,
  };
}

async function parseApiResponse(response: Response) {
  const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
  if (!response.ok) {
    throw new Error(payload?.detail ?? `Request failed (${response.status})`);
  }

  return payload;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const storedSession = readStoredSession();
      if (storedSession === null) {
        if (!cancelled) {
          setSession(null);
          setStatus("unauthenticated");
        }
        return;
      }

      try {
        const validSession = await refreshWithToken(storedSession.refreshToken);
        if (!cancelled) {
          setSession(validSession);
          setStatus("authenticated");
        }
      } catch {
        persistSession(null);
        if (!cancelled) {
          setSession(null);
          setStatus("unauthenticated");
        }
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  async function authenticate(endpoint: "/api/v1/auth/login" | "/api/v1/auth/signup", payload: LoginPayload | SignupPayload) {
    setStatus("loading");

    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = (await parseApiResponse(response)) as AuthApiResponse;
    const nextSession = toSession(data);
    persistSession(nextSession);
    setSession(nextSession);
    setStatus("authenticated");
  }

  async function refreshWithToken(refreshToken: string) {
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data = (await parseApiResponse(response)) as AuthApiResponse;
    const nextSession = toSession(data);
    persistSession(nextSession);
    return nextSession;
  }

  async function login(payload: LoginPayload) {
    await authenticate("/api/v1/auth/login", payload);
  }

  async function signup(payload: SignupPayload) {
    await authenticate("/api/v1/auth/signup", payload);
  }

  async function logout() {
    const currentSession = readStoredSession();
    persistSession(null);
    setSession(null);
    setStatus("unauthenticated");

    if (currentSession === null) {
      return;
    }

    await fetch("/api/v1/auth/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: currentSession.refreshToken }),
    }).catch(() => undefined);
  }

  async function authFetch(input: RequestInfo | URL, init?: RequestInit) {
    let activeSession = readStoredSession();

    if (activeSession === null) {
      setSession(null);
      setStatus("unauthenticated");
      throw new Error("Authentication required");
    }

    const expiresInMs = new Date(activeSession.expiresAt).getTime() - Date.now();
    if (expiresInMs <= REFRESH_THRESHOLD_MS) {
      try {
        activeSession = await refreshWithToken(activeSession.refreshToken);
        setSession(activeSession);
        setStatus("authenticated");
      } catch {
        await logout();
        throw new Error("Session expired. Please sign in again.");
      }
    }

    const headers = new Headers(init?.headers);
    headers.set("Authorization", `Bearer ${activeSession.accessToken}`);

    const response = await fetch(input, { ...init, headers });

    if (response.status === 401) {
      await logout();
      throw new Error("Session expired. Please sign in again.");
    }

    return response;
  }

  return (
    <AuthContext.Provider value={{ status, session, login, signup, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within AuthProvider");
  }

  return context;
}
