interface ScoreBarProps {
  label: string;
  value: number;
  color?: string;
  delayMs?: number;
}

export default function ScoreBar({ label, value, color = "#6C63FF", delayMs = 0 }: ScoreBarProps) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-text-secondary w-24 shrink-0">{label}</span>
      <div className="flex-1 h-1.5 bg-surface-raised rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all ease-out"
          style={{
            width: `${Math.max(0, Math.min(100, value))}%`,
            backgroundColor: color,
            transitionDuration: "600ms",
            transitionDelay: `${delayMs}ms`,
          }}
        />
      </div>
      <span className="font-mono text-text-secondary w-7 text-right shrink-0">
        {Math.round(value)}
      </span>
    </div>
  );
}
