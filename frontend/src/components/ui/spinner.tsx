import { Loader2 } from "lucide-react";
import { cn } from "../../lib/cn";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden="true" className={cn("h-4 w-4 animate-spin", className)} />;
}

export function FullPageSpinner() {
  return (
    <div className="flex min-h-screen items-center justify-center text-navy-soft" role="status">
      <Spinner className="h-6 w-6" />
      <span className="sr-only">Loading</span>
    </div>
  );
}
