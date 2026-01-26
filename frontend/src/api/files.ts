import { apiFetch } from "./client";

export type FileDetail = {
  id: string;
  filename: string;
  original_key: string;
  size_bytes: number;
  mime: string;
  width?: number | null;
  height?: number | null;
  orientation: string;
  shot_at?: string | null;
  title?: string | null;
  description?: string | null;
  keywords: string[];
  thumb_url: string;
  medium_url: string;
};

export type KeywordUpdateRequest = {
  add: string[];
  remove: string[];
};

export async function getFile(id: string): Promise<FileDetail> {
  return apiFetch<FileDetail>(`/files/${id}`);
}

export async function updateKeywords(
  id: string,
  payload: KeywordUpdateRequest
): Promise<FileDetail> {
  return apiFetch<FileDetail>(`/files/${id}/keywords`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getDownloadToken(id: string): Promise<{ token: string }> {
  return apiFetch<{ token: string }>(`/files/${id}/download-token`, {
    method: "POST",
  });
}
