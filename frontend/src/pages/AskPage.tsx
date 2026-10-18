import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUp, MessageSquarePlus, ShieldAlert, Sparkles } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { AnswerText } from "../components/AnswerText";
import { CollectionPicker } from "../components/CollectionPicker";
import { EvidencePanel } from "../components/EvidencePanel";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/inputs";
import { Spinner } from "../components/ui/spinner";
import { ApiError, api } from "../lib/api";
import { cn } from "../lib/cn";
import type { AskResponse } from "../lib/types";

type Turn = {
  id: string;
  question: string;
  status: "pending" | "done" | "error";
  response?: AskResponse;
  error?: string;
};

type AnswerCardProps = {
  response: AskResponse;
  active: boolean;
  activeMarker: number | null;
  onCite: (marker: number) => void;
  onShowEvidence: () => void;
};

function AnswerCard({ response, active, activeMarker, onCite, onShowEvidence }: AnswerCardProps) {
  return (
    <div className={cn("rounded-2xl rounded-tl-sm border bg-surface p-5 shadow-card", active ? "border-teal/50" : "border-line")}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {response.sufficient_evidence ? (
          <Badge tone="teal">
            <Sparkles aria-hidden="true" size={12} /> Grounded in {response.citations.length} source
            {response.citations.length === 1 ? "" : "s"}
          </Badge>
        ) : (
          <Badge tone="amber">
            <ShieldAlert aria-hidden="true" size={12} /> Not enough evidence
          </Badge>
        )}
        <span className="text-xs text-navy-soft">{response.timings.total_ms ?? 0} ms</span>
      </div>

      {response.sufficient_evidence ? (
        <AnswerText text={response.answer} onCite={onCite} activeMarker={activeMarker} />
      ) : (
        <p className="text-[15px] leading-relaxed text-navy-soft">{response.answer}</p>
      )}

      {response.citations.length > 0 && (
        <ul className="mt-4 flex flex-wrap gap-2">
          {response.citations.map((citation) => (
            <li key={citation.marker}>
              <button
                type="button"
                onClick={() => onCite(citation.marker)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1 text-xs text-navy-soft transition hover:border-teal hover:text-navy"
              >
                <span className="font-semibold text-teal">[{citation.marker}]</span>
                <span className="max-w-[10rem] truncate">{citation.filename}</span>
                {citation.page_number !== null && <span>· p.{citation.page_number}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {!response.sufficient_evidence && response.sources.length > 0 && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onShowEvidence}>
          View closest passages
        </Button>
      )}
    </div>
  );
}

export default function AskPage() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const historyId = params.get("history");
  const collectionParam = params.get("collection") ?? "";

  const collections = useQuery({ queryKey: ["collections"], queryFn: api.listCollections });
  // Ignore a stale collection id (for example one that was deleted).
  const scope =
    collections.data && !collections.data.some((collection) => collection.id === collectionParam)
      ? ""
      : collectionParam;

  const [turns, setTurns] = useState<Turn[]>([]);
  const [selected, setSelected] = useState<{ turnId: string; marker: number | null } | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  // Reopen an earlier answer from History (/ask?history=<id>).
  const history = useQuery({
    queryKey: ["history", historyId],
    queryFn: () => api.getHistory(historyId as string),
    enabled: Boolean(historyId),
  });
  const loadedHistory = useRef<string | null>(null);
  useEffect(() => {
    const item = history.data;
    if (!item || loadedHistory.current === item.id) return;
    loadedHistory.current = item.id;
    setTurns([{ id: item.id, question: item.question, status: "done", response: item.response }]);
    setSelected({ turnId: item.id, marker: null });
  }, [history.data]);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [turns.length]);

  function updateParams(change: (next: URLSearchParams) => void) {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        change(next);
        return next;
      },
      { replace: true },
    );
  }

  async function submit() {
    const text = question.trim();
    if (!text || busy) return;
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setTurns((previous) => [...previous, { id, question: text, status: "pending" }]);
    setQuestion("");
    setBusy(true);
    try {
      const response = await api.ask(text, scope || null);
      setTurns((previous) =>
        previous.map((turn) => (turn.id === id ? { ...turn, status: "done", response } : turn)),
      );
      setSelected({ turnId: id, marker: null });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong. Please try again.";
      setTurns((previous) =>
        previous.map((turn) => (turn.id === id ? { ...turn, status: "error", error: message } : turn)),
      );
    } finally {
      setBusy(false);
      void queryClient.invalidateQueries({ queryKey: ["history"] });
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submit();
    }
  }

  function newChat() {
    setTurns([]);
    setSelected(null);
    loadedHistory.current = null;
    updateParams((next) => next.delete("history"));
  }

  const activeTurn = turns.find((turn) => turn.id === selected?.turnId);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Ask</h1>
          <p className="mt-1 text-sm text-navy-soft">
            Answers come only from your documents, and every claim points to its source.
          </p>
        </div>
        {turns.length > 0 && (
          <Button variant="outline" size="sm" onClick={newChat}>
            <MessageSquarePlus aria-hidden="true" size={14} /> New chat
          </Button>
        )}
      </div>

      <div className="mt-6 gap-6 lg:grid lg:grid-cols-[minmax(0,1fr)_24rem]">
        {/* Conversation */}
        <section aria-label="Conversation" className="min-w-0">
          <div className="space-y-6">
            {turns.length === 0 && (
              <div className="rounded-xl border border-dashed border-line bg-surface/60 p-8 text-center">
                <Sparkles aria-hidden="true" className="mx-auto text-teal" size={22} />
                <h2 className="mt-3 font-medium">Ask a question about your documents</h2>
                <p className="mx-auto mt-1 max-w-md text-sm text-navy-soft">
                  If the documents don't contain the answer, you'll be told so instead of getting a guess.
                  No documents yet?{" "}
                  <Link to="/library" className="font-medium text-teal hover:underline">
                    Upload some
                  </Link>
                  .
                </p>
              </div>
            )}

            {turns.map((turn) => (
              <div key={turn.id} className="space-y-3">
                <div className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-navy px-4 py-2.5 text-sm text-white">
                    {turn.question}
                  </div>
                </div>

                {turn.status === "pending" && (
                  <div className="flex items-center gap-2 text-sm text-navy-soft" role="status">
                    <Spinner /> Searching your documents…
                  </div>
                )}

                {turn.status === "error" && (
                  <div role="alert" className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {turn.error}
                  </div>
                )}

                {turn.response && (
                  <AnswerCard
                    response={turn.response}
                    active={selected?.turnId === turn.id}
                    activeMarker={selected?.turnId === turn.id ? selected.marker : null}
                    onCite={(marker) => setSelected({ turnId: turn.id, marker })}
                    onShowEvidence={() => setSelected({ turnId: turn.id, marker: null })}
                  />
                )}
              </div>
            ))}
            <div ref={endRef} />
          </div>

          {/* Composer */}
          <div className="sticky bottom-14 mt-6 bg-paper/95 pb-3 pt-3 backdrop-blur md:bottom-0">
            <div className="mb-2 flex items-center gap-2 text-sm text-navy-soft">
              <span>Searching in</span>
              <CollectionPicker
                className="h-8 w-auto py-0"
                value={scope}
                onChange={(value) =>
                  updateParams((next) => (value ? next.set("collection", value) : next.delete("collection")))
                }
              />
            </div>
            <div className="flex items-end gap-2">
              <Textarea
                aria-label="Your question"
                rows={2}
                maxLength={1000}
                placeholder="Ask a question…"
                className="resize-none"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={onKeyDown}
              />
              <Button
                variant="accent"
                size="icon"
                className="h-10 w-10 shrink-0"
                aria-label="Send question"
                onClick={() => void submit()}
                disabled={busy || !question.trim()}
              >
                {busy ? <Spinner /> : <ArrowUp aria-hidden="true" size={18} />}
              </Button>
            </div>
            <p className="mt-1.5 text-xs text-navy-soft">Enter to send · Shift+Enter for a new line</p>
          </div>
        </section>

        {/* Evidence */}
        <aside
          aria-label="Evidence"
          className="mt-6 lg:sticky lg:top-4 lg:mt-0 lg:max-h-[calc(100vh-2rem)] lg:self-start lg:overflow-y-auto lg:pr-1"
        >
          <EvidencePanel
            response={activeTurn?.response ?? null}
            activeMarker={selected?.marker ?? null}
            onSelectMarker={(marker) => selected && setSelected({ turnId: selected.turnId, marker })}
          />
        </aside>
      </div>
    </div>
  );
}
