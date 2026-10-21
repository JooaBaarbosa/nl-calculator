import { friendlyMessage } from "./errors";
import type { ApiError, CalculateOutcome, SolveResult } from "./types";

function failure(code: string, message?: string): CalculateOutcome {
  return { error: { code, message: message ?? friendlyMessage({ code, message: "" }) } };
}

function isApiError(value: unknown): value is ApiError {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Record<string, unknown>;
  return typeof candidate.code === "string" && typeof candidate.message === "string";
}

export async function calculate(question: string): Promise<CalculateOutcome> {
  let response: Response;
  try {
    response = await fetch("/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    return failure("network_error");
  }

  const unexpected = `Resposta inesperada do servidor (HTTP ${response.status}).`;
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    return failure("unexpected_response", unexpected);
  }

  if (response.ok) return { ok: body as SolveResult };
  if (typeof body === "object" && body !== null) {
    const record = body as Record<string, unknown>;
    if (isApiError(record.error)) return { error: record.error };
    if (response.status === 422 && "detail" in record) return failure("invalid_question");
  }
  return failure("unexpected_response", unexpected);
}
