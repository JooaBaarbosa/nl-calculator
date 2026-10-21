import { friendlyMessage } from "./errors";

it.each([
  [
    "not_configured",
    "A chave da Anthropic não está configurada. Preencha ANTHROPIC_API_KEY no arquivo .env e reinicie.",
  ],
  ["rate_limited", "Muitas requisições à Anthropic. Tente de novo em instantes."],
  ["upstream_error", "A Anthropic não respondeu. Tente de novo."],
  ["invalid_question", "A pergunta precisa ter entre 1 e 500 caracteres."],
  ["network_error", "Não foi possível falar com o servidor. Ele está rodando?"],
])("friendly message for %s", (code, text) => {
  expect(friendlyMessage({ code, message: "ignorada" })).toBe(text);
});

it("falls back to the API message", () => {
  expect(friendlyMessage({ code: "refused", message: "O modelo recusou a pergunta." })).toBe(
    "O modelo recusou a pergunta.",
  );
});
