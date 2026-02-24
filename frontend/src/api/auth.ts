import { apiFetch } from "./client";

export type LoginRequest = { email: string; password: string };
export type LoginResponse = { access_token: string; refresh_token: string };
export type MeResponse = {
  id: string;
  name?: string | null;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getMe(): Promise<MeResponse> {
  return apiFetch<MeResponse>("/auth/me");
}
