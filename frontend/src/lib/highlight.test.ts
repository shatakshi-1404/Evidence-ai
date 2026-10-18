import { describe, expect, it } from "vitest";
import { splitHighlight } from "./highlight";

describe("splitHighlight", () => {
  it("marks query words case-insensitively", () => {
    expect(splitHighlight("Refunds take five days", "refund policy")).toEqual([
      { text: "Refund", match: true },
      { text: "s take five days", match: false },
    ]);
  });

  it("returns the text unchanged when nothing can be highlighted", () => {
    expect(splitHighlight("Some text", "a is")).toEqual([{ text: "Some text", match: false }]);
  });

  it("treats regex characters in the query as plain text", () => {
    expect(() => splitHighlight("Costs (approx.) 5", "(approx.) [x]+")).not.toThrow();
  });
});
