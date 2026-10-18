import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyState } from "../components/EmptyState";
import { Badge } from "../components/ui/badge";
import { Spinner } from "../components/ui/spinner";
import { ApiError, api } from "../lib/api";
import { formatPercent, timeAgo } from "../lib/format";
import type { QuestionResult } from "../lib/types";

const MODES = [
  { key: "vector", label: "Meaning only", color: "#94A3B8" },
  { key: "keyword", label: "Keywords only", color: "#D9A441" },
  { key: "hybrid", label: "Hybrid", color: "#0F766E" },
] as const;

const METRICS = [
  { key: "hit_at_1", label: "Hit@1" },
  { key: "hit_at_3", label: "Hit@3" },
  { key: "hit_at_5", label: "Hit@5" },
  { key: "mrr", label: "MRR" },
] as const;

const pct = (value: number) => Math.round(value * 100);

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 shadow-card">
      <p className="text-xs text-navy-soft">{label}</p>
      <p className="mt-1 font-serif text-3xl font-semibold text-teal">{value}</p>
      <p className="mt-1 text-xs text-navy-soft">{hint}</p>
    </div>
  );
}

function Section({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-surface p-5 shadow-card">
      <h2 className="font-serif text-lg font-semibold">{title}</h2>
      <p className="mt-1 text-sm text-navy-soft">{description}</p>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function problemOf(q: QuestionResult): string | null {
  if (q.answerable) {
    if (q.hybrid_rank === null) return "Not retrieved";
    if (!q.answered) return "Wrongly refused";
    if (q.cited_evidence !== true) return "Wrong citation";
    return null;
  }
  return q.answered ? "Answered (should refuse)" : null;
}

const rank = (value: number | null) => (value === null ? "–" : String(value));

export default function EvaluationPage() {
  const [onlyProblems, setOnlyProblems] = useState(false);
  const report = useQuery({ queryKey: ["evaluation"], queryFn: api.getEvaluation, retry: false });

  if (report.isPending) {
    return (
      <div className="flex justify-center py-20" role="status">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  if (report.isError) {
    const missing = report.error instanceof ApiError && report.error.status === 404;
    return (
      <div className="mx-auto max-w-2xl">
        <h1 className="font-serif text-3xl font-semibold">Evaluation</h1>
        <div className="mt-6">
          <EmptyState
            icon={BarChart3}
            title={missing ? "No evaluation has been run yet" : "Couldn't load the report"}
            text={
              missing
                ? "Run the benchmark from the project folder: docker compose exec backend python -m app.evaluation.run"
                : report.error.message
            }
          />
        </div>
      </div>
    );
  }

  const data = report.data;
  const hybrid = data.retrieval.hybrid;

  const retrievalData = METRICS.map((metric) => ({
    name: metric.label,
    vector: pct(data.retrieval.vector[metric.key]),
    keyword: pct(data.retrieval.keyword[metric.key]),
    hybrid: pct(data.retrieval.hybrid[metric.key]),
  }));

  const thresholdData = data.threshold.points.map((point) => ({
    threshold: Math.round(point.threshold * 100),
    pass: pct(point.answerable_pass_rate),
    refusal: pct(point.unanswerable_refusal_rate),
    balanced: pct(point.balanced_accuracy),
  }));

  const rows = data.questions
    .map((question) => ({ question, problem: problemOf(question) }))
    .filter((row) => !onlyProblems || row.problem !== null);
  const problemCount = data.questions.filter((question) => problemOf(question) !== null).length;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Evaluation</h1>
        <p className="mt-1 text-sm text-navy-soft">
          Measured on a fixed benchmark of {data.dataset.questions} questions ({data.dataset.answerable} answerable,{" "}
          {data.dataset.unanswerable} not) over {data.dataset.documents} documents and {data.dataset.chunks} passages.
          Run {timeAgo(data.generated_at)}.
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          <Badge>Embeddings: {data.embedding_model}</Badge>
          <Badge>Answers: {data.llm_provider}</Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="Hybrid Hit@5" value={formatPercent(hybrid.hit_at_5)} hint="Answer is in the top 5 passages" />
        <MetricCard label="Hybrid MRR" value={hybrid.mrr.toFixed(2)} hint="Higher = right passage ranked first" />
        <MetricCard label="Cited the right passage" value={formatPercent(data.pipeline.cited_evidence_rate)} hint="End to end, answerable questions" />
        <MetricCard label="Correct refusals" value={formatPercent(data.pipeline.refusal_rate)} hint="Unanswerable questions refused" />
      </div>

      <Section
        title="Retrieval: meaning vs keywords vs hybrid"
        description="Share of questions whose answer appears in the top results, and how highly it is ranked (MRR). Hybrid combines both searches."
      >
        <div className="h-72 w-full" role="img" aria-label="Grouped bar chart comparing three retrieval methods">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={retrievalData} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
              <CartesianGrid vertical={false} stroke="#E8E2D8" />
              <XAxis dataKey="name" tickLine={false} axisLine={false} />
              <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} tickLine={false} axisLine={false} />
              <Tooltip formatter={(value) => `${value}%`} cursor={{ fill: "rgba(15, 27, 45, 0.05)" }} />
              <Legend />
              {MODES.map((mode) => (
                <Bar key={mode.key} dataKey={mode.key} name={mode.label} fill={mode.color} radius={[4, 4, 0, 0]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-navy-soft">
              <tr>
                <th className="py-2 pr-4 font-medium">Method</th>
                <th className="py-2 pr-4 font-medium">Latency p50</th>
                <th className="py-2 font-medium">Latency p95</th>
              </tr>
            </thead>
            <tbody>
              {MODES.map((mode) => (
                <tr key={mode.key} className="border-t border-line">
                  <td className="py-2 pr-4">{mode.label}</td>
                  <td className="py-2 pr-4">{data.retrieval[mode.key].latency_p50_ms} ms</td>
                  <td className="py-2">{data.retrieval[mode.key].latency_p95_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section
        title="Tuning the evidence gate"
        description={`Questions below the minimum similarity are refused without calling the model. Recommended MIN_SIMILARITY: ${data.threshold.recommended.toFixed(2)} (currently ${data.threshold.current.toFixed(2)}).`}
      >
        <div className="h-72 w-full" role="img" aria-label="Line chart of gate accuracy at different similarity thresholds">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={thresholdData} margin={{ top: 16, right: 16, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#E8E2D8" />
              <XAxis
                dataKey="threshold"
                type="number"
                domain={[0, 95]}
                ticks={[0, 20, 40, 60, 80]}
                tickFormatter={(value) => `${value}%`}
                tickLine={false}
              />
              <YAxis domain={[0, 100]} tickFormatter={(value) => `${value}%`} tickLine={false} axisLine={false} />
              <Tooltip formatter={(value) => `${value}%`} labelFormatter={(label) => `Minimum similarity ${label}%`} />
              <Legend />
              <ReferenceLine x={pct(data.threshold.current)} stroke="#4A5568" strokeDasharray="4 4" label={{ value: "current", position: "top", fontSize: 11 }} />
              <ReferenceLine x={pct(data.threshold.recommended)} stroke="#0F766E" label={{ value: "recommended", position: "top", fontSize: 11 }} />
              <Line type="monotone" dataKey="pass" name="Answerable questions allowed through" stroke="#0F766E" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="refusal" name="Unanswerable questions refused" stroke="#D9A441" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="balanced" name="Balanced accuracy" stroke="#0F1B2D" dot={false} strokeDasharray="5 3" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Section>

      <Section
        title="Answer pipeline"
        description="The full path a question takes: retrieve, gate, generate, validate citations."
      >
        <dl className="grid gap-3 text-sm sm:grid-cols-2">
          {[
            ["Answerable questions answered", formatPercent(data.pipeline.answered_rate)],
            ["Unanswerable questions refused", formatPercent(data.pipeline.refusal_rate)],
            ["Cited passage contains the evidence", formatPercent(data.pipeline.cited_evidence_rate)],
            ["Answers with an invented citation (stripped)", formatPercent(data.pipeline.invented_citation_rate)],
            ["Answer support (word overlap, heuristic)", data.pipeline.avg_support.toFixed(2)],
            ["Ask latency p50 / p95", `${data.pipeline.latency_p50_ms} / ${data.pipeline.latency_p95_ms} ms`],
            ["Model errors", String(data.pipeline.llm_errors)],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between gap-4 border-b border-line pb-2">
              <dt className="text-navy-soft">{label}</dt>
              <dd className="font-medium">{value}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section
        title="Question by question"
        description="Rank = position of the first passage containing the answer in the top 5 (– means not found)."
      >
        <label className="mb-3 inline-flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={onlyProblems}
            onChange={(event) => setOnlyProblems(event.target.checked)}
            className="h-4 w-4 accent-teal"
          />
          Show only problems ({problemCount})
        </label>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs text-navy-soft">
              <tr>
                <th className="py-2 pr-3 font-medium">Question</th>
                <th className="py-2 pr-3 font-medium">Meaning</th>
                <th className="py-2 pr-3 font-medium">Keyword</th>
                <th className="py-2 pr-3 font-medium">Hybrid</th>
                <th className="py-2 pr-3 font-medium">Best sim.</th>
                <th className="py-2 font-medium">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ question, problem }) => (
                <tr key={question.id} className="border-t border-line align-top">
                  <td className="py-2 pr-3">
                    {question.question}
                    {!question.answerable && <Badge className="ml-2">unanswerable</Badge>}
                  </td>
                  <td className="py-2 pr-3">{question.answerable ? rank(question.vector_rank) : ""}</td>
                  <td className="py-2 pr-3">{question.answerable ? rank(question.keyword_rank) : ""}</td>
                  <td className="py-2 pr-3">{question.answerable ? rank(question.hybrid_rank) : ""}</td>
                  <td className="py-2 pr-3">
                    {question.best_similarity === null ? "–" : question.best_similarity.toFixed(2)}
                  </td>
                  <td className="py-2">
                    <Badge tone={problem ? "amber" : "teal"}>{problem ?? "OK"}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}
