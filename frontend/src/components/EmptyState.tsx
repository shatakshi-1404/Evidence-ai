import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type Props = { icon: LucideIcon; title: string; text: string; action?: ReactNode };

export function EmptyState({ icon: Icon, title, text, action }: Props) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-line bg-surface/60 px-6 py-12 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-teal-light text-teal">
        <Icon aria-hidden="true" size={20} />
      </div>
      <h3 className="mt-4 font-medium">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-navy-soft">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
