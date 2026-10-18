import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History as HistoryIcon, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState } from "../components/EmptyState";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Spinner } from "../components/ui/spinner";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import type { HistoryItem } from "../lib/types";

export default function HistoryPage() {
  const queryClient = useQueryClient();
  const [confirmClear, setConfirmClear] = useState(false);

  const history = useQuery({ queryKey: ["history"], queryFn: () => api.listHistory(100, 0) });
  const collections = useQuery({ queryKey: ["collections"], queryFn: api.listCollections });
  const collectionName = (id: string | null) =>
    id ? (collections.data?.find((collection) => collection.id === id)?.name ?? "Deleted collection") : "All collections";

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteHistory(id),
    onSuccess: (_data, id) =>
      queryClient.setQueryData<HistoryItem[]>(["history"], (old) => old?.filter((item) => item.id !== id)),
  });

  const clear = useMutation({
    mutationFn: () => api.clearHistory(),
    onSuccess: () => {
      queryClient.setQueryData<HistoryItem[]>(["history"], []);
      setConfirmClear(false);
    },
  });

  const items = history.data ?? [];

  return (
    <div className="mx-auto max-w-3xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">History</h1>
          <p className="mt-1 text-sm text-navy-soft">Your earlier questions. Open one to see its answer and sources.</p>
        </div>
        {items.length > 0 && (
          <Button variant="outline" size="sm" onClick={() => setConfirmClear(true)}>
            <Trash2 aria-hidden="true" size={14} /> Clear all
          </Button>
        )}
      </div>

      {history.isPending && <Spinner className="m-6" />}
      {history.isError && <p className="mt-6 text-sm text-red-700">{history.error.message}</p>}

      {history.isSuccess && items.length === 0 && (
        <div className="mt-6">
          <EmptyState
            icon={HistoryIcon}
            title="No questions yet"
            text="Questions you ask appear here, so you can come back to an answer and its evidence."
            action={
              <Link to="/ask">
                <Button variant="accent">Ask a question</Button>
              </Link>
            }
          />
        </div>
      )}

      <ul className="mt-6 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-2 rounded-xl border border-line bg-surface p-4">
            <Link to={`/ask?history=${item.id}`} className="min-w-0 flex-1">
              <p className="line-clamp-2 text-sm font-medium">{item.question}</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-navy-soft">
                <span>{timeAgo(item.created_at)}</span>
                <span>· {collectionName(item.collection_id)}</span>
                <Badge tone={item.sufficient_evidence ? "teal" : "amber"}>
                  {item.sufficient_evidence ? "Answered" : "Not enough evidence"}
                </Badge>
              </div>
            </Link>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Delete this entry"
              onClick={() => remove.mutate(item.id)}
              disabled={remove.isPending}
            >
              <Trash2 aria-hidden="true" size={15} />
            </Button>
          </li>
        ))}
      </ul>

      <ConfirmDialog
        open={confirmClear}
        title="Clear all history?"
        description="Every saved question and answer will be permanently deleted."
        confirmLabel="Clear history"
        busy={clear.isPending}
        onConfirm={() => clear.mutate()}
        onCancel={() => setConfirmClear(false)}
      />
    </div>
  );
}
