import { describe, expect, it } from "vitest";
import { formatBytes, formatPercent, timeAgo } from "./format";

describe("formatBytes", () => {
  it("formats common sizes", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(10 * 1024 * 1024)).toBe("10 MB");
  });
});

describe("timeAgo", () => {
  const now = new Date("2026-01-01T12:00:00Z");

  it("describes recent and older times", () => {
    expect(timeAgo("2026-01-01T11:59:50Z", now)).toBe("just now");
    expect(timeAgo("2026-01-01T11:55:00Z", now)).toBe("5 min ago");
    expect(timeAgo("2026-01-01T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo("2025-12-30T12:00:00Z", now)).toBe("2 d ago");
  });

  it("returns an empty string for an invalid date", () => {
    expect(timeAgo("not a date", now)).toBe("");
  });
});

describe("formatPercent", () => {
  it("formats fractions as percentages", () => {
    expect(formatPercent(0.857)).toBe("86%");
    expect(formatPercent(1)).toBe("100%");
    expect(formatPercent(0.1234, 1)).toBe("12.3%");
  });
});
