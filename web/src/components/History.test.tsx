import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { sample } from "../test-data";
import { EXAMPLES, Examples } from "./Examples";
import { History } from "./History";

it("renders nothing when empty", () => {
  const { container } = render(<History items={[]} onSelect={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

it("selects an item", async () => {
  const onSelect = vi.fn();
  const item = { question: "15% de 3200", result: sample };
  render(<History items={[item]} onSelect={onSelect} />);
  expect(screen.getByText("Histórico desta sessão")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "15% de 3200" }));
  expect(onSelect).toHaveBeenCalledWith(item);
});

it("lists the four spec examples and picks one", async () => {
  expect(EXAMPLES).toEqual([
    "Quanto é 15% de 3.200?",
    "Qual a raiz quadrada de 144?",
    "15% de 3.200 dividido em 6 parcelas",
    "2 elevado a 10",
  ]);
  const onPick = vi.fn();
  render(<Examples onPick={onPick} />);
  await userEvent.click(screen.getByRole("button", { name: "2 elevado a 10" }));
  expect(onPick).toHaveBeenCalledWith("2 elevado a 10");
});
