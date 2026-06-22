import { create } from "zustand";
import { getRankings, pollRankingUntilComplete, startRanking } from "@/api/rankings";
import { DEFAULT_WEIGHTS, type RankingResult, type RankingWeights } from "@/types/ranking";

interface RankingState {
  weights: RankingWeights;
  topN: number;
  currentRanking: RankingResult | null;
  rankingJobId: string | null;
  isRanking: boolean;
  progressMessage: string;
  error: string | null;
  searchQuery: string;

  setWeight: (key: keyof RankingWeights, value: number) => void;
  resetWeights: () => void;
  setTopN: (n: number) => void;
  setSearchQuery: (q: string) => void;
  runRanking: (sessionId: string) => Promise<void>;
  loadExistingRanking: (sessionId: string, jobId: string) => Promise<void>;
  clearError: () => void;
}

const PROGRESS_MESSAGES = [
  "Scoring semantic fit...",
  "Matching success traits...",
  "Evaluating behavioral signals...",
  "Generating insights...",
];

export const useRankingStore = create<RankingState>((set, get) => ({
  weights: DEFAULT_WEIGHTS,
  topN: 20,
  currentRanking: null,
  rankingJobId: null,
  isRanking: false,
  progressMessage: "",
  error: null,
  searchQuery: "",

  setWeight: (key, value) =>
    set((state) => ({ weights: { ...state.weights, [key]: value } })),

  resetWeights: () => set({ weights: DEFAULT_WEIGHTS }),

  setTopN: (n: number) => set({ topN: n }),

  setSearchQuery: (q: string) => set({ searchQuery: q }),

  runRanking: async (sessionId: string) => {
    const { weights, topN } = get();
    const weightSum =
      weights.semantic + weights.skills + weights.trajectory + weights.behavioral;
    if (Math.abs(weightSum - 1.0) > 0.01) {
      set({ error: "Ranking weights must sum to 100%" });
      return;
    }

    set({ isRanking: true, error: null, progressMessage: PROGRESS_MESSAGES[0] });
    let messageIndex = 0;
    const progressInterval = setInterval(() => {
      messageIndex = (messageIndex + 1) % PROGRESS_MESSAGES.length;
      set({ progressMessage: PROGRESS_MESSAGES[messageIndex] });
    }, 4000);

    try {
      const { ranking_job_id } = await startRanking(sessionId, weights, topN);
      set({ rankingJobId: ranking_job_id });

      const result = await pollRankingUntilComplete(sessionId, ranking_job_id);
      clearInterval(progressInterval);

      if (result.status === "FAILED") {
        set({
          error: result.error_message || "Ranking failed. Please try again.",
          isRanking: false,
        });
        return;
      }

      set({ currentRanking: result, isRanking: false, progressMessage: "" });
    } catch (err) {
      clearInterval(progressInterval);
      const message = err instanceof Error ? err.message : "Ranking failed";
      set({ error: message, isRanking: false, progressMessage: "" });
    }
  },

  loadExistingRanking: async (sessionId: string, jobId: string) => {
    try {
      const result = await getRankings(sessionId, jobId);
      set({ currentRanking: result, rankingJobId: jobId });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load ranking";
      set({ error: message });
    }
  },

  clearError: () => set({ error: null }),
}));
