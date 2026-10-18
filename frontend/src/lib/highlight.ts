export type HighlightPart = { text: string; match: boolean };

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Split text so the words from `query` can be wrapped in <mark>. Words under 3 letters are ignored. */
export function splitHighlight(text: string, query: string): HighlightPart[] {
  const terms = Array.from(new Set(query.toLowerCase().match(/[\p{L}\p{N}]{3,}/gu) ?? []));
  if (terms.length === 0) return [{ text, match: false }];

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  // With a capturing group, split() puts the matches at the odd positions.
  return text
    .split(pattern)
    .map((part, index) => ({ text: part, match: index % 2 === 1 }))
    .filter((part) => part.text !== "");
}
