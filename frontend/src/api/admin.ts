import { apiFetch } from "./client";

export type AdminUser = {
  id: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
};

export type AuditLog = {
  id: string;
  user_id: string;
  action: string;
  meta: Record<string, unknown>;
  created_at: string;
};

export async function listUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/users");
}

export async function createUser(payload: {
  email: string;
  password: string;
  role: string;
}): Promise<AdminUser> {
  return apiFetch<AdminUser>("/admin/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateUser(
  id: string,
  payload: { role?: string; is_active?: boolean; password?: string }
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deleteUser(id: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/admin/users/${id}`, {
    method: "DELETE",
  });
}

export async function fetchAudit(limit = 100, offset = 0): Promise<AuditLog[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return apiFetch<AuditLog[]>(`/admin/audit?${params.toString()}`);
}

export async function rescanIndex(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/index/rescan", { method: "POST" });
}

export async function reindexSearch(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/index/reindex", { method: "POST" });
}

export async function gcPreviews(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/index/gc-previews", { method: "POST" });
}

export async function rebuildPreviews(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/index/rebuild-previews", { method: "POST" });
}

export async function indexStatus(): Promise<{ files: number }> {
  return apiFetch<{ files: number }>("/admin/index/status");
}
