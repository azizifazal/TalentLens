import { useRankingStore } from "@/store/useRankingStore";
import type { RankingWeights } from "@/types/ranking";

interface SliderConfig {
  key: keyof RankingWeights;
  label: string;
  color: string;
}

const SLIDERS: SliderConfig[] = [
  { key: "semantic", label: "Semantic Fit", color: "#6C63FF" },
  { key: "skills", label: "Skills Match", color: "#FF9F43" },
  { key: "trajectory", label: "Career Trajectory", color: "#2ECC71" },
  { key: "behavioral", label: "Behavioral", color: "#38BDF8" },
];

interface WeightPanelProps {
  onRerank: () => void;
  isRanking: boolean;
}

export default function WeightPanel({ onRerank, isRanking }: WeightPanelProps) {
  const { weights, setWeight, resetWeights } = useRankingStore();

  const total = weights.semantic + weights.skills + weights.trajectory + weights.behavioral;
  const totalPct = Math.round(total * 100);
  const isValid = Math.abs(total - 1.0) < 0.01;

  return (
    <div className="card p-5 sticky top-4">
      <h3 className="font-display font-semibold text-text-primary mb-1">
        Adjust Ranking Weights
      </h3>
      <p className="text-xs text-text-secondary mb-4">
        Tune how candidates are scored across each dimension.
      </p>

      <div className="space-y-5">
        {SLIDERS.map((slider) => (
          <div key={slider.key}>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-text-primary font-medium">{slider.label}</span>
              <span className="font-mono text-text-secondary">
                {Math.round(weights[slider.key] * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={Math.round(weights[slider.key] * 100)}
              onChange={(e) => setWeight(slider.key, Number(e.target.value) / 100)}
              className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-surface-raised"
              style={{
                accentColor: slider.color,
              }}
              aria-label={`${slider.label} weight`}
            />
          </div>
        ))}
      </div>

      <div className="mt-5 pt-4 border-t border-white/5 flex items-center justify-between">
        <span className="text-sm text-text-secondary">Total</span>
        <span
          className={`font-mono font-semibold text-sm ${
            isValid ? "text-success" : "text-red-400"
          }`}
        >
          {totalPct}% {isValid ? "✓" : "✗"}
        </span>
      </div>

      <div className="mt-4 flex flex-col gap-2">
        <button
          onClick={onRerank}
          disabled={!isValid || isRanking}
          className="btn-primary w-full"
        >
          {isRanking ? "Ranking..." : "Re-rank"}
        </button>
        <button
          onClick={resetWeights}
          className="text-xs text-text-secondary hover:text-text-primary transition-colors text-center"
        >
          Reset to defaults
        </button>
      </div>
    </div>
  );
}
