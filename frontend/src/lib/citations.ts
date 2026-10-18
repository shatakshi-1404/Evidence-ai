export type AnswerSegment =
  | { kind: "text"; text: string }
  | { kind: "cite"; markers: number[]; raw: string };

// [1] or [1, 2]. One to three digits, so a year like [2024] is not a citation.
const MARKER = /\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]/g;

export function parseAnswer(text: string): AnswerSegment[] {
  const segments: AnswerSegment[] = [];
  let last = 0;
  for (const match of text.matchAll(MARKER)) {
    const index = match.index ?? 0;
    if (index > last) segments.push({ kind: "text", text: text.slice(last, index) });
    segments.push({
      kind: "cite",
      markers: (match[1] ?? "").split(",").map((part) => Number(part.trim())),
      raw: match[0],
    });
    last = index + match[0].length;
  }
  if (last < text.length) segments.push({ kind: "text", text: text.slice(last) });
  return segments;
}
