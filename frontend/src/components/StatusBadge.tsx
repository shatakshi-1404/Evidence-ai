import { AlertCircle, CheckCircle2, Clock, Loader2, type LucideIcon } from "lucide-react";
import type { DocumentStatus } from "../lib/types";
import { Badge } from "./ui/badge";

const CONFIG: Record<
  DocumentStatus,
  { label: string; tone: "neutral" | "teal" | "amber" | "red"; icon: LucideIcon; spin?: boolean }
> = {
  queued: { label: "Queued", tone: "neutral", icon: Clock },
  processing: { label: "Processing", tone: "amber", icon: Loader2, spin: true },
  ready: { label: "Ready", tone: "teal", icon: CheckCircle2 },
  failed: { label: "Failed", tone: "red", icon: AlertCircle },
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  const { label, tone, icon: Icon, spin } = CONFIG[status];
  return (
    <Badge tone={tone}>
      <Icon aria-hidden="true" className={spin ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
      {label}
    </Badge>
  );
}
