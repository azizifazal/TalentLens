import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import FileDropzone from "@/components/FileDropzone";
import StatusBadge from "@/components/StatusBadge";
import TraitsEditor from "@/components/TraitsEditor";
import { useRankingStore } from "@/store/useRankingStore";
import { useSessionStore } from "@/store/useSessionStore";

type WizardStep = 1 | 2 | 3;

const STEP_LABELS = ["Define Role", "Upload Candidates", "View Rankings"];

export default function Session() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const {
    currentSession,
    jdText,
    jdRequirements,
    candidates,
    uploadQueue,
    isLoading,
    error,
    loadSession,
    setJdText,
    submitJD,
    updateRequirements,
    uploadFiles,
    refreshCandidates,
    clearError,
  } = useSessionStore();
  const { runRanking, isRanking, progressMessage, error: rankingError } =
    useRankingStore();

  const [step, setStep] = useState<WizardStep>(1);

  useEffect(() => {
    if (sessionId) loadSession(sessionId);
  }, [sessionId, loadSession]);

  useEffect(() => {
    if (jdRequirements) setStep((s) => (s < 2 ? 2 : s));
  }, [jdRequirements]);

  // Poll candidate statuses while on step 2
  useEffect(() => {
    if (step !== 2 || !sessionId) return;
    const interval = setInterval(() => {
      refreshCandidates(sessionId);
    }, 3000);
    return () => clearInterval(interval);
  }, [step, sessionId, refreshCandidates]);

  const handleAnalyzeJD = useCallback(async () => {
    if (!sessionId) return;
    clearError();
    try {
      await submitJD(sessionId);
    } catch {
      // error already captured in store
    }
  }, [sessionId, submitJD, clearError]);

  const handleFilesAccepted = useCallback(
    (files: File[]) => {
      if (!sessionId) return;
      uploadFiles(sessionId, files);
    },
    [sessionId, uploadFiles]
  );

  const handleStartRanking = useCallback(async () => {
    if (!sessionId) return;
    setStep(3);
    await runRanking(sessionId);
    navigate(`/session/${sessionId}/shortlist`);
  }, [sessionId, runRanking, navigate]);

  const readyCount = candidates.filter((c) => c.parse_status === "READY").length;
  const errorCount = candidates.filter((c) => c.parse_status === "ERROR").length;

  if (!currentSession) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-pulse text-text-secondary">Loading session...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen max-w-4xl mx-auto px-6 py-10">
      <button
        onClick={() => navigate("/dashboard")}
        className="text-sm text-text-secondary hover:text-text-primary mb-6"
      >
        ← All sessions
      </button>

      <h1 className="font-display font-bold text-2xl text-text-primary mb-2">
        {currentSession.job_title}
      </h1>

      <div className="flex items-center gap-3 mb-8">
        {STEP_LABELS.map((label, i) => {
          const stepNum = (i + 1) as WizardStep;
          const isActive = step === stepNum;
          const isComplete = step > stepNum;
          return (
            <div key={label} className="flex items-center gap-3">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
                  isActive
                    ? "bg-accent text-white"
                    : isComplete
                    ? "bg-success/15 text-success"
                    : "bg-surface-raised text-text-secondary"
                }`}
              >
                <span>{isComplete ? "✓" : stepNum}</span>
                <span>{label}</span>
              </div>
              {i < STEP_LABELS.length - 1 && (
                <div className="w-8 h-px bg-white/10" />
              )}
            </div>
          );
        })}
      </div>

      {(error || rankingError) && (
        <div className="card p-4 border border-red-500/30 text-red-400 text-sm mb-6">
          {error || rankingError}
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4">
          <div className="card p-5">
            <label className="block text-sm font-medium text-text-primary mb-2">
              Job Description
            </label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              rows={14}
              className="input-field w-full font-mono text-sm resize-y"
              placeholder="Paste the full job description here. The more detail you provide, the more accurate the AI's understanding of required skills, experience level, and behavioral success traits..."
              disabled={!!jdRequirements}
            />
            <div className="flex justify-between items-center mt-2">
              <span className="text-xs text-muted">
                {jdText.length} characters {jdText.length < 50 && "(minimum 50)"}
              </span>
              {!jdRequirements && (
                <button
                  onClick={handleAnalyzeJD}
                  disabled={jdText.length < 50 || isLoading}
                  className="btn-primary"
                >
                  {isLoading ? "Analyzing..." : "Analyze Job Description"}
                </button>
              )}
            </div>
          </div>

          {jdRequirements && (
            <>
              <TraitsEditor requirements={jdRequirements} onChange={updateRequirements} />
              <div className="flex justify-end">
                <button
                  onClick={() => setStep(2)}
                  disabled={jdRequirements.required_skills.length < 1}
                  className="btn-primary"
                >
                  Confirm & Continue
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="space-y-4">
          <FileDropzone onFilesAccepted={handleFilesAccepted} />

          {(uploadQueue.length > 0 || candidates.length > 0) && (
            <div className="card p-4">
              <h3 className="text-sm font-medium text-text-primary mb-3">
                Candidates ({candidates.length})
              </h3>
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {candidates.map((c) => (
                  <div
                    key={c.candidate_id}
                    className="flex items-center justify-between py-2 px-3 bg-surface-raised rounded-lg"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-text-primary truncate">
                        {c.full_name || c.file_name}
                      </p>
                      {c.current_title && (
                        <p className="text-xs text-text-secondary truncate">
                          {c.current_title}
                        </p>
                      )}
                    </div>
                    <StatusBadge status={c.parse_status} />
                  </div>
                ))}
                {uploadQueue
                  .filter((u) => u.status === "uploading" || u.status === "queued")
                  .map((u, i) => (
                    <div
                      key={`upload-${i}`}
                      className="flex items-center justify-between py-2 px-3 bg-surface-raised rounded-lg"
                    >
                      <p className="text-sm text-text-primary truncate">{u.fileName}</p>
                      <StatusBadge status={u.status} />
                    </div>
                  ))}
              </div>
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-sm text-text-secondary">
              {readyCount} of {candidates.length} candidates ready
              {errorCount > 0 && (
                <span className="text-red-400"> · {errorCount} failed</span>
              )}
            </span>
            <button
              onClick={handleStartRanking}
              disabled={readyCount === 0}
              className="btn-primary"
            >
              Rank Candidates
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="card p-12 text-center">
          <div className="w-12 h-12 mx-auto mb-4 relative">
            <div className="absolute inset-0 border-4 border-surface-raised rounded-full" />
            <div className="absolute inset-0 border-4 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
          <p className="text-text-primary font-medium mb-1">
            {isRanking ? progressMessage || "Starting ranking engine..." : "Finalizing..."}
          </p>
          <p className="text-xs text-text-secondary">
            This usually takes under 60 seconds for {candidates.length} candidates
          </p>
        </div>
      )}
    </div>
  );
}
