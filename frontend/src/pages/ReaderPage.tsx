import { useEffect, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, FileText } from "lucide-react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Spinner } from "../components/ui/spinner";
import { api } from "../lib/api";
import { cn } from "../lib/cn";
import { formatBytes } from "../lib/format";

const PAGE_SIZE = 50;

export default function ReaderPage() {
  const { documentId = "" } = useParams();
  const [params] = useSearchParams();

  // ?chunk=N means "open at passage N" (used by citations).
  const rawTarget = params.get("chunk");
  const parsed = rawTarget === null ? NaN : Number(rawTarget);
  const target = Number.isInteger(parsed) && parsed >= 0 ? parsed : null;

  const [offset, setOffset] = useState(() => (target === null ? 0 : Math.floor(target / PAGE_SIZE) * PAGE_SIZE));

  useEffect(() => {
    if (target !== null) setOffset(Math.floor(target / PAGE_SIZE) * PAGE_SIZE);
  }, [target]);

  const document_ = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => api.getDocument(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "processing" ? 2000 : false;
    },
  });
  const doc = document_.data;

  const chunks = useQuery({
    queryKey: ["chunks", documentId, offset],
    queryFn: () => api.listChunks(documentId, PAGE_SIZE, offset),
    enabled: doc?.status === "ready",
    placeholderData: keepPreviousData,
  });

  // Scroll to the cited passage once it's on screen.
  useEffect(() => {
    if (target === null || !chunks.data) return;
    window.document
      .getElementById(`chunk-${target}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [chunks.data, target]);

  if (document_.isPending) {
    return (
      <div className="flex justify-center py-20" role="status">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (document_.isError || !doc) {
    return (
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="font-serif text-2xl font-semibold">Document not found</h1>
        <p className="mt-2 text-sm text-navy-soft">It may have been deleted.</p>
        <Link to="/library" className="mt-4 inline-block text-sm font-medium text-teal hover:underline">
          Back to library
        </Link>
      </div>
    );
  }

  const total = doc.chunk_count;
  const shown = chunks.data ?? [];

  return (
    <div className="mx-auto max-w-3xl">
      <Link
        to={`/library/${doc.collection_id}`}
        className="inline-flex items-center gap-1 text-sm text-navy-soft hover:text-navy"
      >
        <ChevronLeft aria-hidden="true" size={14} /> Library
      </Link>

      <div className="mt-3 flex flex-wrap items-center gap-3">
        <FileText aria-hidden="true" className="text-teal" size={24} />
        <h1 className="min-w-0 flex-1 truncate font-serif text-2xl font-semibold">{doc.filename}</h1>
        <StatusBadge status={doc.status} />
      </div>
      <p className="mt-1 text-sm text-navy-soft">
        {formatBytes(doc.size_bytes)}
        {doc.page_count ? ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}` : ""} · {total} passages
      </p>

      {doc.status !== "ready" && (
        <p className="mt-6 rounded-xl border border-line bg-surface p-5 text-sm text-navy-soft">
          {doc.status === "failed"
            ? (doc.error_message ?? "Processing failed.")
            : "This document is still being processed. It will appear here when it's ready."}
        </p>
      )}

      {doc.status === "ready" && (
        <>
          <p className="mt-4 text-xs text-navy-soft">
            Passages overlap slightly by design, so a sentence near the end of one passage may start the next.
          </p>

          {chunks.isPending && <Spinner className="m-6" />}
          {chunks.isError && <p className="mt-4 text-sm text-red-700">{chunks.error.message}</p>}

          <div className="mt-4 space-y-3">
            {shown.map((chunk) => {
              const highlighted = chunk.chunk_index === target;
              return (
                <article
                  key={chunk.id}
                  id={`chunk-${chunk.chunk_index}`}
                  className={cn(
                    "scroll-mt-24 rounded-xl border bg-surface p-5",
                    highlighted ? "border-teal ring-2 ring-teal/30" : "border-line",
                  )}
                >
                  <div className="mb-2 flex items-center gap-2 text-xs text-navy-soft">
                    <span className="font-medium text-navy">Passage {chunk.chunk_index + 1}</span>
                    {chunk.page_number !== null && <Badge>Page {chunk.page_number}</Badge>}
                    <span>{chunk.char_count} characters</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{chunk.content}</p>
                </article>
              );
            })}
          </div>

          {total > PAGE_SIZE && (
            <div className="mt-6 flex items-center justify-between">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                <ChevronLeft aria-hidden="true" size={14} /> Previous
              </Button>
              <span className="text-sm text-navy-soft">
                {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next <ChevronRight aria-hidden="true" size={14} />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
