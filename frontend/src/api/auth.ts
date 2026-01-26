import { apiFetch } from "./client";

export type LoginRequest = { email: string; password: string };
export type LoginResponse = { access_token: string; refresh_token: string };

export async function login(payload: LoginRequest): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
