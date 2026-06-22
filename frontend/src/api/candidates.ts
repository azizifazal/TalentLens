import { apiClient } from "@/api/client";
import type { Candidate, CandidateListItem, UploadUrlResponse } from "@/types/candidate";

export async function listCandidates(sessionId: string): Promise<CandidateListItem[]> {
  const { data } = await apiClient.get<CandidateListItem[]>(
    `/sessions/${sessionId}/resumes`
  );
  return data;
}

export async function getUploadUrl(
  sessionId: string,
  fileName: string,
  fileSizeBytes: number
): Promise<UploadUrlResponse> {
  const { data } = await apiClient.post<UploadUrlResponse>(
    `/sessions/${sessionId}/resumes/upload-url`,
    { file_name: fileName, file_size_bytes: fileSizeBytes }
  );
  return data;
}

export async function uploadFileToS3(uploadUrl: string, file: File): Promise<void> {
  await fetch(uploadUrl, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": "application/octet-stream" },
  });
}

export async function confirmUpload(
  sessionId: string,
  candidateId: string
): Promise<void> {
  await apiClient.post(`/sessions/${sessionId}/resumes/confirm`, {
    candidate_id: candidateId,
  });
}

export async function getCandidate(
  sessionId: string,
  candidateId: string
): Promise<Candidate> {
  const { data } = await apiClient.get<Candidate>(
    `/sessions/${sessionId}/candidates/${candidateId}`
  );
  return data;
}

export async function uploadResume(sessionId: string, file: File): Promise<string> {
  const { candidate_id, upload_url } = await getUploadUrl(
    sessionId,
    file.name,
    file.size
  );
  await uploadFileToS3(upload_url, file);
  await confirmUpload(sessionId, candidate_id);
  return candidate_id;
}
