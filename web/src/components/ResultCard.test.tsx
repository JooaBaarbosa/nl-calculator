import { render, screen } from "@testing-library/react";
import { sample } from "../test-data";
import { ResultCard } from "./ResultCard";

it("highlights the result", () => {
  render(<ResultCard result={sample} />);
  expect(screen.getByTestId("result-value")).toHaveTextContent("80");
  expect(screen.getByText(sample.answer)).toBeInTheDocument();
  expect(screen.getByText("3200 * 15 / 100 / 6 = 80")).toBeInTheDocument();
  expect(screen.getByText("claude-opus-5-5 · 906 tokens")).toBeInTheDocument();
});

it("omits highlight when result is null", () => {
  render(<ResultCard result={{ ...sample, result: null, steps: [] }} />);
  expect(screen.queryByTestId("result-value")).toBeNull();
  expect(screen.getByText(sample.answer)).toBeInTheDocument();
});

it("marks failed steps", () => {
  const failed = {
    ...sample,
    result: null,
    steps: [{ expression: "1 / 0", result: null, error: "division_by_zero: Divisão por zero." }],
  };
  render(<ResultCard result={failed} />);
  const step = screen.getByText("1 / 0 → erro: division_by_zero: Divisão por zero.");
  expect(step).toHaveClass("step-error");
});
