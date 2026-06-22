import { useEffect, useRef, useState } from "react";

interface ScoreRingProps {
  score: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

function interpolateColor(score: number): string {
  // 0   -> warm (#FF9F43)
  // 50  -> accent (#6C63FF)
  // 100 -> success (#2ECC71)
  const warm = { r: 255, g: 159, b: 67 };
  const accentColor = { r: 108, g: 99, b: 255 };
  const success = { r: 46, g: 204, b: 113 };

  let start = warm;
  let end = accentColor;
  let t = score / 50;

  if (score > 50) {
    start = accentColor;
    end = success;
    t = (score - 50) / 50;
  }

  const r = Math.round(start.r + (end.r - start.r) * t);
  const g = Math.round(start.g + (end.g - start.g) * t);
  const b = Math.round(start.b + (end.b - start.b) * t);
  return `rgb(${r}, ${g}, ${b})`;
}

export default function ScoreRing({
  score,
  size = 84,
  strokeWidth = 7,
  label = "/100",
}: ScoreRingProps) {
  const [animatedScore, setAnimatedScore] = useState(0);
  const frameRef = useRef<number | null>(null);

  useEffect(() => {
    const duration = 800;
    const startTime = performance.now();
    const startScore = 0;

    function step(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      setAnimatedScore(startScore + (score - startScore) * eased);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(step);
      }
    }
    frameRef.current = requestAnimationFrame(step);
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [score]);

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - animatedScore / 100);
  const color = interpolateColor(score);

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Composite score: ${Math.round(score)} out of 100`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#22263A"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          style={{ transition: "stroke 200ms ease" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-display font-bold text-xl text-text-primary leading-none">
          {Math.round(animatedScore)}
        </span>
        <span className="font-mono text-[10px] text-text-secondary mt-0.5">{label}</span>
      </div>
    </div>
  );
}
