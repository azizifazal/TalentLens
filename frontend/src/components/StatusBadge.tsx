import type { ParseStatus } from "@/types/candidate";

interface StatusBadgeProps {
  status: ParseStatus | "uploading" | "queued" | "error" | "uploaded";
}

const STATUS_CONFIG: Record<string, { label: string; className: string; pulse?: boolean }> = {
  QUEUED: { label: "Queued", className: "bg-surface-raised text-text-secondary" },
  queued: { label: "Queued", className: "bg-surface-raised text-text-secondary" },
  uploading: { label: "Uploading", className: "bg-accent/20 text-accent", pulse: true },
  uploaded: { label: "Uploaded", className: "bg-accent/20 text-accent" },
  PARSING: { label: "Parsing", className: "bg-accent/20 text-accent", pulse: true },
  COMPUTING_SIGNALS: {
    label: "Computing Signals",
    className: "bg-behavioral/20 text-behavioral",
    pulse: true,
  },
  READY: { label: "Ready", className: "bg-success/20 text-success" },
  ERROR: { label: "Error", className: "bg-red-500/20 text-red-400" },
  error: { label: "Error", className: "bg-red-500/20 text-red-400" },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.QUEUED;
  return (
    <span
      className={`tag-chip ${config.className} text-[11px] font-medium`}
    >
      {config.pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-current opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-current" />
        </span>
      )}
      {config.label}
    </span>
  );
}
