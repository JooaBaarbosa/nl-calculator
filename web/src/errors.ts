import type { ApiError } from "./types";

const MESSAGES: Record<string, string> = {
  not_configured:
    "A chave da Anthropic não está configurada. Preencha ANTHROPIC_API_KEY no arquivo .env e reinicie.",
  rate_limited: "Muitas requisições à Anthropic. Tente de novo em instantes.",
  upstream_error: "A Anthropic não respondeu. Tente de novo.",
  invalid_question: "A pergunta precisa ter entre 1 e 500 caracteres.",
  network_error: "Não foi possível falar com o servidor. Ele está rodando?",
};

export function friendlyMessage(error: ApiError): string {
  return MESSAGES[error.code] ?? error.message;
}
