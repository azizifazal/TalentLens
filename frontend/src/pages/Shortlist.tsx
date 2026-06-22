import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import CandidateCard from "@/components/CandidateCard";
import CandidateDrawer from "@/components/CandidateDrawer";
import WeightPanel from "@/components/WeightPanel";
import { downloadExportCsv } from "@/api/rankings";
import { useRankingStore } from "@/store/useRankingStore";
import { useSessionStore } from "@/store/useSessionStore";
import type { RankedCandidate } from "@/types/ranking";

export default function Shortlist() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { currentSession, loadSession } = useSessionStore();
  const {
    currentRanking,
    rankingJobId,
    isRanking,
    progressMessage,
    runRanking,
    loadExistingRanking,
    searchQuery,
    setSearchQuery,
    topN,
    setTopN,
    error,
  } = useRankingStore();

  const [selectedCandidate, setSelectedCandidate] = useState<RankedCandidate | null>(
    null
  );

  useEffect(() => {
    if (sessionId && !currentSession) {
      loadSession(sessionId);
    }
  }, [sessionId, currentSession, loadSession]);

  useEffect(() => {
    if (sessionId && rankingJobId && !currentRanking) {
      loadExistingRanking(sessionId, rankingJobId);
    }
  }, [sessionId, rankingJobId, currentRanking, loadExistingRanking]);

  const filteredCandidates = useMemo(() => {
    if (!currentRanking) return [];
    const query = searchQuery.trim().toLowerCase();
    if (!query) return currentRanking.ranked_candidates;
    return currentRanking.ranked_candidates.filter((c) =>
      c.full_name.toLowerCase().includes(query)
    );
  }, [currentRanking, searchQuery]);

  async function handleRerank() {
    if (!sessionId) return;
    await runRanking(sessionId);
  }

  async function handleExport() {
    if (!sessionId || !rankingJobId) return;
    await downloadExportCsv(sessionId, rankingJobId);
  }

  if (isRanking && !currentRanking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 mx-auto mb-4 relative">
            <div className="absolute inset-0 border-4 border-surface-raised rounded-full" />
            <div className="absolute inset-0 border-4 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
          <p className="text-text-primary font-medium">{progressMessage}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-white/5 px-6 py-4 sticky top-0 bg-bg/95 backdrop-blur z-20">
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-4 flex-wrap">
          <div>
            <button
              onClick={() => navigate("/dashboard")}
              className="text-xs text-text-secondary hover:text-text-primary mb-1"
            >
              ← All sessions
            </button>
            <h1 className="font-display font-semibold text-text-primary">
              {currentSession?.job_title || "Shortlist"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <input
              type="text"
              placeholder="Search by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field text-sm w-48"
            />
            <select
              value={topN}
              onChange={(e) => setTopN(Number(e.target.value))}
              className="input-field text-sm"
            >
              <option value={10}>Top 10</option>
              <option value={20}>Top 20</option>
              <option value={30}>Top 30</option>
            </select>
            <button onClick={handleExport} className="btn-secondary text-sm">
              Export CSV
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {error && (
          <div className="card p-4 border border-red-500/30 text-red-400 text-sm mb-6">
            {error}
          </div>
        )}

        {currentRanking && currentRanking.ranked_candidates.length === 0 && (
          <div className="card p-12 text-center text-text-secondary">
            No candidates matched this search.
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6">
          <div className="space-y-4">
            {filteredCandidates.map((candidate) => (
              <CandidateCard
                key={candidate.candidate_id}
                candidate={candidate}
                onClick={() => setSelectedCandidate(candidate)}
              />
            ))}
          </div>

          <div>
            <WeightPanel onRerank={handleRerank} isRanking={isRanking} />
          </div>
        </div>
      </div>

      {selectedCandidate && sessionId && (
        <CandidateDrawer
          sessionId={sessionId}
          rankedCandidate={selectedCandidate}
          onClose={() => setSelectedCandidate(null)}
        />
      )}
    </div>
  );
}
