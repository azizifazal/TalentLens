import { apiClient } from "@/api/client";
import type { RankingResult, RankingWeights, RankResponse } from "@/types/ranking";

export async function startRanking(
  sessionId: string,
  weights: RankingWeights,
  topN: number
): Promise<RankResponse> {
  const { data } = await apiClient.post<RankResponse>(
    `/sessions/${sessionId}/rank`,
    { weights, top_n: topN }
  );
  return data;
}

export async function getRankings(
  sessionId: string,
  jobId: string
): Promise<RankingResult> {
  const { data } = await apiClient.get<RankingResult>(
    `/sessions/${sessionId}/rankings`,
    { params: { job_id: jobId } }
  );
  return data;
}

export async function downloadExportCsv(sessionId: string, jobId: string): Promise<void> {
  const response = await apiClient.get(`/sessions/${sessionId}/export`, {
    params: { job_id: jobId },
    responseType: "blob",
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.setAttribute(
    "download",
    `talentlens_shortlist_${sessionId.slice(0, 8)}_${jobId.slice(0, 8)}.csv`
  );
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

export async function pollRankingUntilComplete(
  sessionId: string,
  jobId: string,
  onUpdate?: (result: RankingResult) => void,
  intervalMs: number = 3000,
  maxAttempts: number = 60
): Promise<RankingResult> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const result = await getRankings(sessionId, jobId);
    onUpdate?.(result);
    if (result.status === "COMPLETE" || result.status === "FAILED") {
      return result;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Ranking timed out. Please try again.");
}
