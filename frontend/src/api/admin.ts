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
  return apiFetch<{ status: string; run_id?: string }>("/admin/index/rescan", {
    method: "POST",
  });
}

export async function refreshAll(): Promise<{ status: string; run_id?: string }> {
  return apiFetch<{ status: string; run_id?: string }>("/admin/index/refresh-all", {
    method: "POST",
  });
}

export async function reindexSearch(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/index/reindex", {
    method: "POST",
  });
}

export type ReindexStatus = {
  status: string;
  count: number;
  updated_at: string;
  started_at?: string;
};

export async function reindexStatus(): Promise<ReindexStatus> {
  return apiFetch<ReindexStatus>("/admin/index/reindex/status");
}

export type IndexRunStatus = {
  id: string;
  status: string;
  scanned: number;
  created: number;
  updated: number;
  restored: number;
  deleted: number;
  started_at?: string | null;
  finished_at?: string | null;
  error?: string | null;
};

export async function indexStatus(): Promise<{ files: number; run?: IndexRunStatus | null }> {
  return apiFetch<{ files: number; run?: IndexRunStatus | null }>("/admin/index/status");
}

export async function cancelIndex(): Promise<{ status: string; run_id?: string }> {
  return apiFetch<{ status: string; run_id?: string }>("/admin/index/cancel", {
    method: "POST",
  });
}

export type PreviewStatus = {
  status: string;
  round: number;
  max_rounds: number;
  total_files: number;
  total_previews: number;
  missing_previews: number;
  progress: number;
  updated_at: string;
  started_at?: string;
};

export type OrphanPreviewStatus = {
  status: string;
  total_orphans: number;
  deleted: number;
  processed: number;
  updated_at: string;
  started_at?: string;
};

export async function refreshPreviews(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/previews/refresh", {
    method: "POST",
  });
}

export async function previewStatus(): Promise<PreviewStatus> {
  return apiFetch<PreviewStatus>("/admin/previews/status");
}

export async function cleanupOrphanPreviews(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/admin/previews/orphans/cleanup", {
    method: "POST",
  });
}

export async function orphanPreviewStatus(): Promise<OrphanPreviewStatus> {
  return apiFetch<OrphanPreviewStatus>("/admin/previews/orphans/status");
}
