import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";
import { describe, expect, it } from "vitest";
import HelpButton from "./HelpButton";


describe("HelpButton", () => {
  it("shows a circular muted helper control and toggles the note", async () => {
    const user = userEvent.setup();

    render(<HelpButton label="Cell size" help="Smaller cells give more detail." />);

    const button = screen.getByRole("button", { name: /help for cell size/i });
    expect(button).toHaveClass("help-button");

    await user.click(button);
    expect(screen.getByRole("note")).toHaveTextContent(/smaller cells give more detail/i);
  });
});
