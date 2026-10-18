import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnswerText } from "./AnswerText";

describe("AnswerText", () => {
  it("turns each citation number into a button", () => {
    render(<AnswerText text="Refunds take five days [1]. Free shipping [2, 3]." />);
    expect(screen.getAllByRole("button")).toHaveLength(3);
    expect(screen.getByText(/Refunds take five days/)).toBeInTheDocument();
  });

  it("tells the parent which source was clicked", async () => {
    const onCite = vi.fn();
    render(<AnswerText text="Claim [2]." onCite={onCite} />);

    await userEvent.click(screen.getByRole("button", { name: "Show source 2" }));

    expect(onCite).toHaveBeenCalledWith(2);
  });

  it("renders plain text without any buttons", () => {
    render(<AnswerText text="Nothing cited here." />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
