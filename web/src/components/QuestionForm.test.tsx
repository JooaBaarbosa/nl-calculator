import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QuestionForm } from "./QuestionForm";

function renderForm(props: Partial<Parameters<typeof QuestionForm>[0]> = {}) {
  const onSubmit = vi.fn();
  render(
    <QuestionForm value="" loading={false} onChange={() => {}} onSubmit={onSubmit} {...props} />,
  );
  return onSubmit;
}

it("disables submit for blank question", () => {
  renderForm({ value: "   " });
  expect(screen.getByRole("button", { name: "Calcular" })).toBeDisabled();
});

it("shows loading label and disables", () => {
  renderForm({ value: "1+1", loading: true });
  expect(screen.getByRole("button", { name: "Calculando…" })).toBeDisabled();
});

it("calls onSubmit on Enter", async () => {
  const onSubmit = renderForm({ value: "1+1" });
  await userEvent.type(screen.getByLabelText("Pergunta"), "{Enter}");
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

it("does not submit blank question on Enter", async () => {
  const onSubmit = renderForm({ value: "  " });
  await userEvent.type(screen.getByLabelText("Pergunta"), "{Enter}");
  expect(onSubmit).not.toHaveBeenCalled();
});

it("reports typed text", async () => {
  const onChange = vi.fn();
  renderForm({ onChange });
  await userEvent.type(screen.getByLabelText("Pergunta"), "a");
  expect(onChange).toHaveBeenCalledWith("a");
});

it("limits question to 500 characters", () => {
  renderForm();
  expect(screen.getByLabelText("Pergunta")).toHaveAttribute("maxLength", "500");
});
