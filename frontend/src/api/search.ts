import { apiFetch } from "./client";

export type SearchItem = {
  id: string;
  thumb_url: string;
  medium_url: string;
  keywords: string[];
  shot_at?: string | null;
  orientation: string;
};

export type SearchResponse = {
  items: SearchItem[];
  next_cursor?: string | null;
  total?: number | null;
  total_all?: number | null;
  returned?: number | null;
};

export async function searchPhotos(
  query: string,
  offset: number,
  limit = 10000
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    offset: String(offset),
    limit: String(limit),
  });
  return apiFetch<SearchResponse>(`/search?${params.toString()}`);
}

export type AsyncSearchResponse = SearchResponse & { job_id?: string };

export async function startAsyncSearch(
  query: string,
  limit = 200
): Promise<AsyncSearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: String(limit),
  });
  return apiFetch<AsyncSearchResponse>(`/search/async/start?${params.toString()}`, {
    method: "POST",
  });
}

export async function asyncSearchPage(
  jobId: string,
  offset: number,
  limit = 200
): Promise<AsyncSearchResponse> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit),
  });
  return apiFetch<AsyncSearchResponse>(
    `/search/async/${jobId}?${params.toString()}`
  );
}

export async function asyncSearchStatus(jobId: string): Promise<{ total_found: number; status: string }> {
  return apiFetch(`/search/async/${jobId}/status`);
}

export async function suggestKeywords(prefix: string, limit = 20): Promise<Array<{ value: string; count: number }>> {
  const params = new URLSearchParams({ prefix, limit: String(limit) });
  return apiFetch(`/keywords/suggest?${params.toString()}`);
}
