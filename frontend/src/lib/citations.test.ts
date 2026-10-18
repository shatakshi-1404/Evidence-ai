import { describe, expect, it } from "vitest";
import { parseAnswer } from "./citations";

describe("parseAnswer", () => {
  it("returns plain text untouched", () => {
    expect(parseAnswer("No citations here.")).toEqual([{ kind: "text", text: "No citations here." }]);
  });

  it("splits text around a citation", () => {
    expect(parseAnswer("Refunds take 5 days [1]. Done.")).toEqual([
      { kind: "text", text: "Refunds take 5 days " },
      { kind: "cite", markers: [1], raw: "[1]" },
      { kind: "text", text: ". Done." },
    ]);
  });

  it("handles combined and adjacent citations", () => {
    const segments = parseAnswer("A [1, 2][3]");
    expect(segments.filter((s) => s.kind === "cite")).toEqual([
      { kind: "cite", markers: [1, 2], raw: "[1, 2]" },
      { kind: "cite", markers: [3], raw: "[3]" },
    ]);
  });

  it("does not treat a year in brackets as a citation", () => {
    expect(parseAnswer("In [2024] it rose")).toEqual([{ kind: "text", text: "In [2024] it rose" }]);
  });

  it("handles empty input", () => {
    expect(parseAnswer("")).toEqual([]);
  });
});
