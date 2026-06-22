import { apiClient } from "@/api/client";
import type {
  AnalyzeJDResponse,
  CreateSessionResponse,
  SessionSummary,
} from "@/types/session";

export async function listSessions(): Promise<SessionSummary[]> {
  const { data } = await apiClient.get<SessionSummary[]>("/sessions");
  return data;
}

export async function createSession(jobTitle: string): Promise<CreateSessionResponse> {
  const { data } = await apiClient.post<CreateSessionResponse>("/sessions", {
    job_title: jobTitle,
  });
  return data;
}

export async function getSession(sessionId: string): Promise<SessionSummary> {
  const { data } = await apiClient.get<SessionSummary>(`/sessions/${sessionId}`);
  return data;
}

export async function analyzeJD(
  sessionId: string,
  jdText: string
): Promise<AnalyzeJDResponse> {
  const { data } = await apiClient.post<AnalyzeJDResponse>(
    `/sessions/${sessionId}/jd`,
    { jd_text: jdText }
  );
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiClient.delete(`/sessions/${sessionId}`);
}
