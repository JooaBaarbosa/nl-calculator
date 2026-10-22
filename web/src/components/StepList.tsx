import type { Step } from "../types";

interface Props {
  steps: Step[];
}

export function StepList({ steps }: Props) {
  if (steps.length === 0) return null;
  return (
    <div className="steps">
      <h3>Passos</h3>
      <ul>
        {steps.map((step, index) =>
          step.error === null ? (
            <li key={index}>{`${step.expression} = ${step.result}`}</li>
          ) : (
            <li key={index} className="step-error">
              {`${step.expression} → erro: ${step.error}`}
            </li>
          ),
        )}
      </ul>
    </div>
  );
}
