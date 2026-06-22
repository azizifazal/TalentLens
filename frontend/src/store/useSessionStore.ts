import { create } from "zustand";
import { analyzeJD, createSession, getSession, listSessions } from "@/api/sessions";
import { listCandidates, uploadResume } from "@/api/candidates";
import type { CandidateListItem } from "@/types/candidate";
import type { JDRequirements, SessionSummary } from "@/types/session";

interface FileUploadState {
  fileName: string;
  candidateId: string | null;
  status: "queued" | "uploading" | "uploaded" | "error";
  error?: string;
}

interface SessionState {
  sessions: SessionSummary[];
  currentSession: SessionSummary | null;
  jdText: string;
  jdRequirements: JDRequirements | null;
  candidates: CandidateListItem[];
  uploadQueue: FileUploadState[];
  isLoading: boolean;
  error: string | null;

  fetchSessions: () => Promise<void>;
  startNewSession: (jobTitle: string) => Promise<string>;
  loadSession: (sessionId: string) => Promise<void>;
  setJdText: (text: string) => void;
  submitJD: (sessionId: string) => Promise<void>;
  updateRequirements: (requirements: JDRequirements) => void;
  uploadFiles: (sessionId: string, files: File[]) => Promise<void>;
  refreshCandidates: (sessionId: string) => Promise<void>;
  clearError: () => void;
  reset: () => void;
}

export const useSessionStore = create<SessionState>((set, get) => ({
  sessions: [],
  currentSession: null,
  jdText: "",
  jdRequirements: null,
  candidates: [],
  uploadQueue: [],
  isLoading: false,
  error: null,

  fetchSessions: async () => {
    set({ isLoading: true, error: null });
    try {
      const sessions = await listSessions();
      set({ sessions, isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load sessions";
      set({ error: message, isLoading: false });
    }
  },

  startNewSession: async (jobTitle: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await createSession(jobTitle);
      const summary: SessionSummary = {
        session_id: response.session_id,
        job_title: response.job_title,
        status: response.status,
        candidate_count: 0,
        created_at: response.created_at,
        updated_at: response.created_at,
      };
      set((state) => ({
        currentSession: summary,
        sessions: [summary, ...state.sessions],
        jdText: "",
        jdRequirements: null,
        candidates: [],
        uploadQueue: [],
        isLoading: false,
      }));
      return response.session_id;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to create session";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  loadSession: async (sessionId: string) => {
    set({ isLoading: true, error: null });
    try {
      const session = await getSession(sessionId);
      const candidates = await listCandidates(sessionId);
      set({ currentSession: session, candidates, isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load session";
      set({ error: message, isLoading: false });
    }
  },

  setJdText: (text: string) => set({ jdText: text }),

  submitJD: async (sessionId: string) => {
    set({ isLoading: true, error: null });
    try {
      const response = await analyzeJD(sessionId, get().jdText);
      set({
        jdRequirements: response.jd_requirements,
        isLoading: false,
      });
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to analyze job description";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  updateRequirements: (requirements: JDRequirements) =>
    set({ jdRequirements: requirements }),

  uploadFiles: async (sessionId: string, files: File[]) => {
    const initialQueue: FileUploadState[] = files.map((f) => ({
      fileName: f.name,
      candidateId: null,
      status: "queued",
    }));
    set((state) => ({ uploadQueue: [...state.uploadQueue, ...initialQueue] }));

    for (const file of files) {
      set((state) => ({
        uploadQueue: state.uploadQueue.map((u) =>
          u.fileName === file.name && u.status === "queued"
            ? { ...u, status: "uploading" }
            : u
        ),
      }));
      try {
        const candidateId = await uploadResume(sessionId, file);
        set((state) => ({
          uploadQueue: state.uploadQueue.map((u) =>
            u.fileName === file.name
              ? { ...u, status: "uploaded", candidateId }
              : u
          ),
        }));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Upload failed";
        set((state) => ({
          uploadQueue: state.uploadQueue.map((u) =>
            u.fileName === file.name ? { ...u, status: "error", error: message } : u
          ),
        }));
      }
    }
    await get().refreshCandidates(sessionId);
  },

  refreshCandidates: async (sessionId: string) => {
    try {
      const candidates = await listCandidates(sessionId);
      set({ candidates });
    } catch {
      // Polling failures are non-fatal; the next interval will retry.
    }
  },

  clearError: () => set({ error: null }),

  reset: () =>
    set({
      currentSession: null,
      jdText: "",
      jdRequirements: null,
      candidates: [],
      uploadQueue: [],
      error: null,
    }),
}));
