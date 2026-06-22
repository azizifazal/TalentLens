import { describe, expect, it, beforeEach } from "vitest";
import { useRankingStore } from "@/store/useRankingStore";
import { DEFAULT_WEIGHTS } from "@/types/ranking";

describe("useRankingStore", () => {
  beforeEach(() => {
    useRankingStore.setState({
      weights: DEFAULT_WEIGHTS,
      topN: 20,
      currentRanking: null,
      rankingJobId: null,
      isRanking: false,
      progressMessage: "",
      error: null,
      searchQuery: "",
    });
  });

  it("initializes with default weights that sum to 1.0", () => {
    const { weights } = useRankingStore.getState();
    const total = weights.semantic + weights.skills + weights.trajectory + weights.behavioral;
    expect(total).toBeCloseTo(1.0, 5);
  });

  it("default weights match the documented spec", () => {
    const { weights } = useRankingStore.getState();
    expect(weights.semantic).toBe(0.3);
    expect(weights.skills).toBe(0.25);
    expect(weights.trajectory).toBe(0.25);
    expect(weights.behavioral).toBe(0.2);
  });

  it("setWeight updates a single dimension without affecting others", () => {
    useRankingStore.getState().setWeight("semantic", 0.5);
    const { weights } = useRankingStore.getState();
    expect(weights.semantic).toBe(0.5);
    expect(weights.skills).toBe(0.25);
  });

  it("resetWeights restores defaults after modification", () => {
    useRankingStore.getState().setWeight("behavioral", 0.9);
    useRankingStore.getState().resetWeights();
    const { weights } = useRankingStore.getState();
    expect(weights).toEqual(DEFAULT_WEIGHTS);
  });

  it("runRanking rejects when weights do not sum to 1.0", async () => {
    useRankingStore.setState({
      weights: { semantic: 0.5, skills: 0.5, trajectory: 0.5, behavioral: 0.5 },
    });
    await useRankingStore.getState().runRanking("session-1");
    const { error, isRanking } = useRankingStore.getState();
    expect(error).toBe("Ranking weights must sum to 100%");
    expect(isRanking).toBe(false);
  });

  it("setTopN updates the top N selection", () => {
    useRankingStore.getState().setTopN(30);
    expect(useRankingStore.getState().topN).toBe(30);
  });

  it("setSearchQuery updates the search filter", () => {
    useRankingStore.getState().setSearchQuery("Jordan");
    expect(useRankingStore.getState().searchQuery).toBe("Jordan");
  });
});
