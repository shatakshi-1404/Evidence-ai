import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search as SearchIcon } from "lucide-react";
import { CollectionPicker } from "../components/CollectionPicker";
import { EmptyState } from "../components/EmptyState";
import { PassageCard } from "../components/PassageCard";
import { Button } from "../components/ui/button";
import { Input, Select } from "../components/ui/inputs";
import { Spinner } from "../components/ui/spinner";
import { api } from "../lib/api";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("");
  const [limit, setLimit] = useState(6);
  const [documentFilter, setDocumentFilter] = useState("");

  const search = useMutation({
    mutationFn: (values: { query: string; collection: string; limit: number }) =>
      api.search(values.query, values.collection || null, values.limit),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = query.trim();
    if (text) search.mutate({ query: text, collection, limit });
  }

  const results = search.data?.results ?? [];
  const visible = results.filter((passage) =>
    passage.filename.toLowerCase().includes(documentFilter.trim().toLowerCase()),
  );

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-3xl font-semibold">Search</h1>
      <p className="mt-1 text-sm text-navy-soft">
        Find passages by meaning and by keywords. No answer is generated here, just the evidence.
      </p>

      <form onSubmit={onSubmit} className="mt-6 space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <SearchIcon
              aria-hidden="true"
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-soft"
            />
            <Input
              aria-label="Search query"
              placeholder="Search your documents"
              className="pl-9"
              maxLength={500}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <Button type="submit" variant="accent" disabled={search.isPending || !query.trim()}>
            {search.isPending && <Spinner />}
            Search
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CollectionPicker className="w-auto" value={collection} onChange={setCollection} />
          <Select
            aria-label="Number of results"
            className="w-auto"
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value))}
          >
            {[3, 6, 10, 20].map((value) => (
              <option key={value} value={value}>
                Top {value}
              </option>
            ))}
          </Select>
          {results.length > 0 && (
            <Input
              aria-label="Filter results by document name"
              placeholder="Filter by document name"
              className="w-56"
              value={documentFilter}
              onChange={(event) => setDocumentFilter(event.target.value)}
            />
          )}
        </div>
      </form>

      {search.isError && (
        <p role="alert" className="mt-6 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {search.error.message}
        </p>
      )}

      {search.isSuccess && (
        <div className="mt-6">
          <p className="mb-3 text-xs text-navy-soft">
            {results.length} passage{results.length === 1 ? "" : "s"} · {search.data.timings.retrieval_ms ?? 0} ms
          </p>
          {results.length === 0 ? (
            <EmptyState
              icon={SearchIcon}
              title="No matching passages"
              text="Try different words, a broader collection, or check that your documents have finished processing."
            />
          ) : visible.length === 0 ? (
            <p className="text-sm text-navy-soft">No results match that document name.</p>
          ) : (
            <div className="space-y-3">
              {visible.map((passage) => (
                <PassageCard key={passage.chunk_id} passage={passage} highlight={search.variables?.query ?? ""} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
