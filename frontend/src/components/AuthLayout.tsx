import type { ReactNode } from "react";
import { FileText, Quote, ShieldCheck } from "lucide-react";

type Props = { title: string; subtitle: string; children: ReactNode; footer: ReactNode };

export function AuthLayout({ title, subtitle, children, footer }: Props) {
  return (
    <div className="grid min-h-screen md:grid-cols-[1fr_1.1fr]">
      <div className="hidden flex-col justify-between bg-navy p-12 text-white md:flex">
        <div className="font-serif text-2xl font-semibold">EvidenceAI</div>
        <div>
          <h1 className="font-serif text-5xl font-semibold leading-tight">
            Search less.
            <br />
            <span className="text-teal-light">Know more.</span>
          </h1>
          <p className="mt-5 max-w-md text-white/70">
            Ask questions of your documents and get answers that point back to the exact passage they
            came from.
          </p>
        </div>
        <ul className="space-y-3 text-sm text-white/70">
          <li className="flex items-center gap-3">
            <FileText aria-hidden="true" size={16} /> Upload PDFs and text, organized in collections
          </li>
          <li className="flex items-center gap-3">
            <Quote aria-hidden="true" size={16} /> Every claim cites a real, retrieved passage
          </li>
          <li className="flex items-center gap-3">
            <ShieldCheck aria-hidden="true" size={16} /> Your documents are visible only to you
          </li>
        </ul>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8 font-serif text-2xl font-semibold md:hidden">EvidenceAI</div>
          <h2 className="font-serif text-3xl font-semibold">{title}</h2>
          <p className="mt-2 text-sm text-navy-soft">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <p className="mt-6 text-sm text-navy-soft">{footer}</p>
        </div>
      </div>
    </div>
  );
}
