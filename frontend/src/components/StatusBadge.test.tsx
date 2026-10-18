import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["queued", "Queued"],
    ["processing", "Processing"],
    ["ready", "Ready"],
    ["failed", "Failed"],
  ] as const)("shows a readable label for %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
