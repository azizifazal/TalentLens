import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ScoreRing from "@/components/ScoreRing";

describe("ScoreRing", () => {
  it("renders an accessible label with the rounded score", () => {
    render(<ScoreRing score={87} />);
    expect(
      screen.getByRole("img", { name: /composite score: 87 out of 100/i })
    ).toBeInTheDocument();
  });

  it("renders the /100 label by default", () => {
    render(<ScoreRing score={50} />);
    expect(screen.getByText("/100")).toBeInTheDocument();
  });

  it("accepts a custom label", () => {
    render(<ScoreRing score={50} label="pts" />);
    expect(screen.getByText("pts")).toBeInTheDocument();
  });

  it("renders an svg element sized according to the size prop", () => {
    const { container } = render(<ScoreRing score={75} size={120} />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("width", "120");
    expect(svg).toHaveAttribute("height", "120");
  });
});
