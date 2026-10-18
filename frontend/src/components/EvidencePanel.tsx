import { FileSearch, ShieldAlert } from "lucide-react";
import type { AskResponse } from "../lib/types";
import { PassageCard } from "./PassageCard";
import { SimilarityChart } from "./SimilarityChart";
import { Badge } from "./ui/badge";

const REASONS: Record<string, string> = {
  no_relevant_passages: "Nothing in your documents was similar enough to this question.",
  model_declined: "The model judged these passages insufficient to answer.",
  uncited_answer: "The model's answer didn't cite any retrieved passage, so it was rejected.",
};

type Props = {
  response: AskResponse | null;
  activeMarker: number | null;
  onSelectMarker: (marker: number) => void;
};

export function EvidencePanel({ response, activeMarker, onSelectMarker }: Props) {
  if (!response) {
    return (
      <div className="flex flex-col items-center rounded-xl border border-dashed border-line px-6 py-12 text-center">
        <FileSearch aria-hidden="true" className="text-navy-soft" size={24} />
        <h2 className="mt-3 font-medium">Evidence</h2>
        <p className="mt-1 text-sm text-navy-soft">
          The passages behind each answer appear here. Click a citation number to jump to its source.
        </p>
      </div>
    );
  }

  const cited = new Set(response.citations.map((citation) => citation.marker));
  const { retrieval_ms, generation_ms } = response.timings;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-serif text-lg font-semibold">
          {response.sufficient_evidence ? "Evidence" : "Closest passages"}
        </h2>
        <Badge tone={response.sufficient_evidence ? "teal" : "amber"}>
          {response.sufficient_evidence ? `${cited.size} cited` : "Not used"}
        </Badge>
      </div>

      {!response.sufficient_evidence && (
        <p className="flex gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
          {REASONS[response.reason ?? ""] ?? "The documents don't contain enough evidence."}
        </p>
      )}

      {response.removed_markers.length > 0 && (
        <p className="flex gap-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
          <ShieldAlert aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
          {response.removed_markers.length} citation
          {response.removed_markers.length === 1 ? "" : "s"} that didn't match a retrieved passage{" "}
          {response.removed_markers.length === 1 ? "was" : "were"} removed.
        </p>
      )}

      <SimilarityChart sources={response.sources} cited={cited} />

      <div className="space-y-3">
        {response.sources.map((source) => (
          <PassageCard
            key={source.chunk_id}
            passage={source}
            cited={source.marker !== null && cited.has(source.marker)}
            active={source.marker === activeMarker}
            onSelect={source.marker === null ? undefined : () => onSelectMarker(source.marker as number)}
          />
        ))}
      </div>

      <p className="text-xs text-navy-soft">
        Retrieval {retrieval_ms ?? 0} ms · Generation {generation_ms ?? 0} ms
      </p>
    </div>
  );
}
