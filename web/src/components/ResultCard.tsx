import type { SolveResult } from "../types";
import { StepList } from "./StepList";

interface Props {
  result: SolveResult;
}

export function ResultCard({ result }: Props) {
  const tokens = result.usage.input_tokens + result.usage.output_tokens;
  return (
    <article className="result-card">
      {result.result !== null && (
        <p className="result-value" data-testid="result-value">
          {result.result}
        </p>
      )}
      <p className="result-answer">{result.answer}</p>
      <StepList steps={result.steps} />
      <p className="result-meta">{`${result.model} · ${tokens} tokens`}</p>
    </article>
  );
}
