import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  FileText,
  Folder,
  FolderPlus,
  Library,
  RotateCcw,
  Search,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { Button } from "../components/ui/button";
import { Input, Select } from "../components/ui/inputs";
import { Spinner } from "../components/ui/spinner";
import { ApiError, api } from "../lib/api";
import { cn } from "../lib/cn";
import { formatBytes, timeAgo } from "../lib/format";
import type { Collection, DocumentItem, DocumentStatus } from "../lib/types";

export default function LibraryPage() {
  const { collectionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [confirmCollectionDelete, setConfirmCollectionDelete] = useState(false);
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [filterText, setFilterText] = useState("");
  const [filterStatus, setFilterStatus] = useState<"" | DocumentStatus>("");
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState<{ name: string; message: string }[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const collections = useQuery({ queryKey: ["collections"], queryFn: api.listCollections });
  const list = collections.data;
  const selected = list?.find((collection) => collection.id === collectionId);

  // Land on a real collection: the first one if none (or a stale one) is in the URL.
  useEffect(() => {
    if (!list) return;
    const exists = Boolean(collectionId) && list.some((collection) => collection.id === collectionId);
    if (list.length > 0 && !exists) navigate(`/library/${list[0].id}`, { replace: true });
    else if (list.length === 0 && collectionId) navigate("/library", { replace: true });
  }, [list, collectionId, navigate]);

  const documents = useQuery({
    queryKey: ["documents", collectionId],
    queryFn: () => api.listDocuments(collectionId as string),
    enabled: Boolean(selected),
    // Poll while anything is still being processed; stop once everything has settled.
    refetchInterval: (query) =>
      query.state.data?.some((doc) => doc.status === "queued" || doc.status === "processing")
        ? 2000
        : false,
  });

  const createCollection = useMutation({
    mutationFn: (name: string) => api.createCollection(name),
    onSuccess: (collection) => {
      // Add it to the cache first, so the redirect effect sees it immediately.
      queryClient.setQueryData<Collection[]>(["collections"], (old) => [collection, ...(old ?? [])]);
      setNewName("");
      setCreating(false);
      navigate(`/library/${collection.id}`);
    },
  });

  const deleteCollection = useMutation({
    mutationFn: (id: string) => api.deleteCollection(id),
    onSuccess: (_data, id) => {
      queryClient.setQueryData<Collection[]>(["collections"], (old) =>
        old?.filter((collection) => collection.id !== id),
      );
      queryClient.removeQueries({ queryKey: ["documents", id] });
      setConfirmCollectionDelete(false);
      navigate("/library", { replace: true });
    },
  });

  const refreshDocuments = () => queryClient.invalidateQueries({ queryKey: ["documents", collectionId] });

  const retryDocument = useMutation({
    mutationFn: (id: string) => api.retryDocument(id),
    onSuccess: refreshDocuments,
  });

  const deleteDocument = useMutation({
    mutationFn: (id: string) => api.deleteDocument(id),
    onSuccess: () => {
      setDocToDelete(null);
      return refreshDocuments();
    },
  });

  async function uploadFiles(files: File[]) {
    if (!selected || files.length === 0) return;
    setUploading(true);
    setUploadErrors([]);
    const errors: { name: string; message: string }[] = [];
    for (const file of files) {
      try {
        await api.uploadDocument(selected.id, file);
      } catch (err) {
        errors.push({
          name: file.name,
          message: err instanceof ApiError ? err.message : "Upload failed",
        });
      }
      await queryClient.invalidateQueries({ queryKey: ["documents", selected.id] });
    }
    setUploadErrors(errors);
    setUploading(false);
  }

  const allDocs = documents.data ?? [];
  const visibleDocs = allDocs.filter(
    (doc) =>
      doc.filename.toLowerCase().includes(filterText.trim().toLowerCase()) &&
      (filterStatus === "" || doc.status === filterStatus),
  );
  const counts = allDocs.reduce<Record<string, number>>((acc, doc) => {
    acc[doc.status] = (acc[doc.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="font-serif text-3xl font-semibold">Library</h1>
      <p className="mt-1 text-sm text-navy-soft">Your documents, organized in collections.</p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[16rem_1fr]">
        {/* Collections */}
        <section aria-label="Collections">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium text-navy-soft">Collections</h2>
            <Button variant="ghost" size="sm" onClick={() => setCreating((value) => !value)}>
              <FolderPlus aria-hidden="true" size={14} /> New
            </Button>
          </div>

          {creating && (
            <form
              className="mb-3 space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                if (newName.trim()) createCollection.mutate(newName.trim());
              }}
            >
              <Input
                autoFocus
                aria-label="Collection name"
                placeholder="Collection name"
                maxLength={120}
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
              />
              {createCollection.isError && (
                <p role="alert" className="text-xs text-red-700">
                  {createCollection.error.message}
                </p>
              )}
              <Button type="submit" size="sm" variant="accent" disabled={createCollection.isPending || !newName.trim()}>
                {createCollection.isPending && <Spinner />}
                Create
              </Button>
            </form>
          )}

          {collections.isPending && <Spinner className="m-3" />}
          {collections.isError && <p className="text-sm text-red-700">{collections.error.message}</p>}

          <ul className="space-y-1">
            {list?.map((collection) => (
              <li key={collection.id}>
                <Link
                  to={`/library/${collection.id}`}
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
                    collection.id === collectionId
                      ? "bg-surface font-medium shadow-card"
                      : "text-navy-soft hover:bg-surface hover:text-navy",
                  )}
                >
                  <Folder aria-hidden="true" size={15} className="shrink-0 text-teal" />
                  <span className="truncate">{collection.name}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        {/* Documents */}
        <section aria-label="Documents" className="min-w-0">
          {list && list.length === 0 && (
            <EmptyState
              icon={Library}
              title="Create your first collection"
              text="Collections group related documents. Create one, then drop files into it."
              action={
                <Button variant="accent" onClick={() => setCreating(true)}>
                  <FolderPlus aria-hidden="true" size={16} /> New collection
                </Button>
              }
            />
          )}

          {selected && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate font-serif text-xl font-semibold">{selected.name}</h2>
                  {selected.description && <p className="text-sm text-navy-soft">{selected.description}</p>}
                </div>
                <Button variant="outline" size="sm" onClick={() => setConfirmCollectionDelete(true)}>
                  <Trash2 aria-hidden="true" size={14} /> Delete collection
                </Button>
              </div>

              {/* Upload */}
              <div
                onDragOver={(event) => {
                  event.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDragging(false);
                  void uploadFiles(Array.from(event.dataTransfer.files));
                }}
                className={cn(
                  "mt-4 rounded-xl border-2 border-dashed p-6 text-center transition",
                  dragging ? "border-teal bg-teal-light/40" : "border-line bg-surface/60",
                )}
              >
                <input
                  ref={fileInput}
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md"
                  className="hidden"
                  onChange={(event) => {
                    void uploadFiles(Array.from(event.target.files ?? []));
                    event.target.value = ""; // allow choosing the same file again
                  }}
                />
                <Button variant="outline" onClick={() => fileInput.current?.click()} disabled={uploading}>
                  {uploading ? <Spinner /> : <Upload aria-hidden="true" size={16} />}
                  {uploading ? "Uploading…" : "Choose files"}
                </Button>
                <p className="mt-2 text-sm text-navy-soft">or drag and drop. PDF, TXT or Markdown.</p>
              </div>

              {uploadErrors.length > 0 && (
                <div role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">Some files couldn't be uploaded:</p>
                    <button type="button" aria-label="Dismiss" onClick={() => setUploadErrors([])}>
                      <X aria-hidden="true" size={14} />
                    </button>
                  </div>
                  <ul className="mt-1 list-disc pl-5">
                    {uploadErrors.map((item, index) => (
                      <li key={index}>
                        {item.name}: {item.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Filters */}
              {allDocs.length > 0 && (
                <div className="mt-6 flex flex-wrap items-center gap-2">
                  <div className="relative min-w-[12rem] flex-1">
                    <Search
                      aria-hidden="true"
                      size={14}
                      className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-soft"
                    />
                    <Input
                      aria-label="Filter documents by name"
                      placeholder="Filter by name"
                      className="pl-9"
                      value={filterText}
                      onChange={(event) => setFilterText(event.target.value)}
                    />
                  </div>
                  <Select
                    aria-label="Filter by status"
                    className="w-auto"
                    value={filterStatus}
                    onChange={(event) => setFilterStatus(event.target.value as "" | DocumentStatus)}
                  >
                    <option value="">All statuses</option>
                    {(["ready", "processing", "queued", "failed"] as const).map((status) => (
                      <option key={status} value={status}>
                        {status[0].toUpperCase() + status.slice(1)} ({counts[status] ?? 0})
                      </option>
                    ))}
                  </Select>
                </div>
              )}

              {documents.isPending && <Spinner className="m-4" />}
              {documents.isError && <p className="mt-4 text-sm text-red-700">{documents.error.message}</p>}

              {documents.isSuccess && allDocs.length === 0 && (
                <div className="mt-6">
                  <EmptyState
                    icon={FileText}
                    title="No documents yet"
                    text="Upload a PDF or text file above. Once it's processed you can search it and ask questions."
                  />
                </div>
              )}

              {allDocs.length > 0 && visibleDocs.length === 0 && (
                <p className="mt-6 text-sm text-navy-soft">No documents match your filters.</p>
              )}

              <ul className="mt-3 space-y-2" aria-live="polite">
                {visibleDocs.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-line bg-surface p-4"
                  >
                    <FileText aria-hidden="true" size={20} className="shrink-0 text-teal" />
                    <div className="min-w-0 flex-1">
                      {doc.status === "ready" ? (
                        <Link to={`/documents/${doc.id}`} className="block truncate font-medium hover:underline">
                          {doc.filename}
                        </Link>
                      ) : (
                        <span className="block truncate font-medium">{doc.filename}</span>
                      )}
                      <p className="text-xs text-navy-soft">
                        {formatBytes(doc.size_bytes)}
                        {doc.page_count ? ` · ${doc.page_count} page${doc.page_count === 1 ? "" : "s"}` : ""}
                        {doc.status === "ready" ? ` · ${doc.chunk_count} passages` : ""} · {timeAgo(doc.created_at)}
                      </p>
                      {doc.error_message && (
                        <p className={cn("mt-1 text-xs", doc.status === "failed" ? "text-red-700" : "text-amber-700")}>
                          {doc.error_message}
                        </p>
                      )}
                    </div>
                    <StatusBadge status={doc.status} />
                    <div className="flex items-center gap-1">
                      {doc.status === "failed" && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => retryDocument.mutate(doc.id)}
                          disabled={retryDocument.isPending}
                        >
                          <RotateCcw aria-hidden="true" size={13} /> Retry
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Delete ${doc.filename}`}
                        onClick={() => setDocToDelete(doc)}
                      >
                        <Trash2 aria-hidden="true" size={15} />
                      </Button>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={confirmCollectionDelete}
        title="Delete this collection?"
        description="All of its documents and passages will be permanently deleted. This can't be undone."
        confirmLabel="Delete collection"
        busy={deleteCollection.isPending}
        onConfirm={() => selected && deleteCollection.mutate(selected.id)}
        onCancel={() => setConfirmCollectionDelete(false)}
      />
      <ConfirmDialog
        open={docToDelete !== null}
        title="Delete this document?"
        description={`"${docToDelete?.filename ?? ""}" and its passages will be permanently deleted.`}
        confirmLabel="Delete document"
        busy={deleteDocument.isPending}
        onConfirm={() => docToDelete && deleteDocument.mutate(docToDelete.id)}
        onCancel={() => setDocToDelete(null)}
      />
    </div>
  );
}
