import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { reply, sample } from "./test-data";

const fetchMock = vi.fn<typeof fetch>();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function answerFor(question: string, result = "1") {
  return reply(200, { ...sample, answer: `resposta de ${question}`, result });
}

function sentQuestions(): string[] {
  return fetchMock.mock.calls.map(([, init]) => JSON.parse(String(init?.body)).question);
}

async function ask(question: string) {
  const input = screen.getByLabelText("Pergunta");
  await userEvent.clear(input);
  await userEvent.type(input, `${question}{Enter}`);
}

function historyQuestions(): string[] {
  const section = screen.getByText("Histórico desta sessão").closest("section");
  return within(section as HTMLElement)
    .getAllByRole("button")
    .map((button) => button.textContent ?? "");
}

it("submits and shows the result", async () => {
  let resolve!: (response: Response) => void;
  fetchMock.mockReturnValue(new Promise((r) => (resolve = r)));
  render(<App />);
  await ask("15% de 3200");
  expect(screen.getByRole("button", { name: "Calculando…" })).toBeDisabled();
  resolve(reply(200, sample));
  expect(await screen.findByTestId("result-value")).toHaveTextContent("80");
});

it("trims the question before sending", async () => {
  fetchMock.mockResolvedValue(answerFor("2+2"));
  render(<App />);
  await ask("  2+2  ");
  await screen.findByTestId("result-value");
  expect(sentQuestions()).toEqual(["2+2"]);
});

it("ignores submit while loading", async () => {
  fetchMock.mockReturnValue(new Promise(() => {}));
  render(<App />);
  await ask("1+1");
  await userEvent.type(screen.getByLabelText("Pergunta"), "{Enter}{Enter}");
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("disables examples while a question is in flight", async () => {
  fetchMock.mockReturnValue(new Promise(() => {}));
  render(<App />);
  await ask("1+1");
  const example = screen.getByRole("button", { name: "2 elevado a 10" });
  expect(example).toBeDisabled();
  await userEvent.click(example);
  expect(screen.getByLabelText("Pergunta")).toHaveValue("1+1");
  expect(fetchMock).toHaveBeenCalledTimes(1);
});

it("submits an example on click", async () => {
  fetchMock.mockResolvedValue(answerFor("raiz"));
  render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Qual a raiz quadrada de 144?" }));
  await screen.findByTestId("result-value");
  expect(sentQuestions()).toEqual(["Qual a raiz quadrada de 144?"]);
  expect(screen.getByLabelText("Pergunta")).toHaveValue("Qual a raiz quadrada de 144?");
});

it("replays history without calling the API", async () => {
  fetchMock
    .mockResolvedValueOnce(answerFor("primeira", "10"))
    .mockResolvedValueOnce(answerFor("segunda", "20"));
  render(<App />);
  await ask("primeira");
  await screen.findByText("resposta de primeira");
  await ask("segunda");
  await screen.findByText("resposta de segunda");

  await userEvent.click(screen.getByRole("button", { name: "primeira" }));
  expect(screen.getByTestId("result-value")).toHaveTextContent("10");
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it("moves repeated question to top of history", async () => {
  fetchMock.mockImplementation(async (_url, init) =>
    answerFor(JSON.parse(String(init?.body)).question),
  );
  render(<App />);
  for (const question of ["a", "b", "a"]) {
    await ask(question);
    await screen.findByText(`resposta de ${question}`);
  }
  expect(historyQuestions()).toEqual(["a", "b"]);
});

it("shows API errors as alert", async () => {
  fetchMock.mockResolvedValue(reply(503, { error: { code: "not_configured", message: "x" } }));
  render(<App />);
  await ask("1+1");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "A chave da Anthropic não está configurada. Preencha ANTHROPIC_API_KEY no arquivo .env e reinicie.",
  );
  expect(screen.queryByTestId("result-value")).toBeNull();
});

it("keeps history after network error", async () => {
  fetchMock
    .mockResolvedValueOnce(answerFor("primeira"))
    .mockRejectedValueOnce(new TypeError("Failed to fetch"));
  render(<App />);
  await ask("primeira");
  await screen.findByText("resposta de primeira");
  await ask("segunda");
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Não foi possível falar com o servidor. Ele está rodando?",
  );
  expect(historyQuestions()).toEqual(["primeira"]);
});
