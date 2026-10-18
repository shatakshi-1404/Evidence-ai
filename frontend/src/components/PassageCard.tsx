import { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "../lib/cn";
import { splitHighlight } from "../lib/highlight";
import type { Passage } from "../lib/types";
import { Badge } from "./ui/badge";

type Props = {
  passage: Passage;
  cited?: boolean;
  active?: boolean;
  highlight?: string;
  onSelect?: () => void;
};

export function PassageCard({ passage, cited = false, active = false, highlight = "", onSelect }: Props) {
  const [expanded, setExpanded] = useState(false);
  const card = useRef<HTMLElement>(null);

  useEffect(() => {
    if (active) card.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [active]);

  const long = passage.content.length > 280;

  return (
    <article
      ref={card}
      onClick={onSelect}
      className={cn(
        "rounded-xl border bg-surface p-4 transition",
        onSelect && "cursor-pointer hover:border-teal/50",
        active ? "border-teal ring-2 ring-teal/25" : "border-line",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        {passage.marker !== null && (
          <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-teal px-1 text-xs font-semibold text-white">
            {passage.marker}
          </span>
        )}
        <span className="min-w-0 truncate text-sm font-medium">{passage.filename}</span>
        {passage.page_number !== null && <Badge>Page {passage.page_number}</Badge>}
        {cited && <Badge tone="teal">Cited</Badge>}
      </div>

      <p className={cn("mt-2 whitespace-pre-wrap text-sm leading-relaxed", !expanded && long && "line-clamp-4")}>
        {splitHighlight(passage.content, highlight).map((part, index) =>
          part.match ? (
            <mark key={index} className="rounded bg-teal-light px-0.5 text-navy">
              {part.text}
            </mark>
          ) : (
            <span key={index}>{part.text}</span>
          ),
        )}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-navy-soft">
        {passage.similarity !== null && <span>Similarity {Math.round(passage.similarity * 100)}%</span>}
        {passage.matched_by.includes("vector") && <Badge>Meaning</Badge>}
        {passage.matched_by.includes("keyword") && <Badge>Keyword</Badge>}
        <span className="ml-auto flex items-center gap-3">
          {long && (
            <button
              type="button"
              className="font-medium text-teal hover:underline"
              onClick={(event) => {
                event.stopPropagation();
                setExpanded((value) => !value);
              }}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
          <Link
            to={`/documents/${passage.document_id}?chunk=${passage.chunk_index}`}
            onClick={(event) => event.stopPropagation()}
            className="inline-flex items-center gap-1 font-medium text-teal hover:underline"
          >
            Open in document <ExternalLink aria-hidden="true" size={12} />
          </Link>
        </span>
      </div>
    </article>
  );
}
