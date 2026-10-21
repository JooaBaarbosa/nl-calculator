// Espelham os modelos Pydantic de src/nl_calculator/solver.py.

export interface Step {
  expression: string;
  result: string | null;
  error: string | null;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
}

export interface SolveResult {
  answer: string;
  result: string | null;
  steps: Step[];
  model: string;
  usage: Usage;
}

export interface ApiError {
  code: string;
  message: string;
}

export type CalculateOutcome = { ok: SolveResult } | { error: ApiError };

export interface HistoryItem {
  question: string;
  result: SolveResult;
}
