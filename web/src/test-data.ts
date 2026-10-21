import type { SolveResult } from "./types";

export const sample: SolveResult = {
  answer: "15% de 3.200 é 480; dividido em 6 parcelas, dá 80 por parcela.",
  result: "80",
  steps: [{ expression: "3200 * 15 / 100 / 6", result: "80", error: null }],
  model: "claude-opus-5-5",
  usage: { input_tokens: 812, output_tokens: 94 },
};

export function reply(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}
