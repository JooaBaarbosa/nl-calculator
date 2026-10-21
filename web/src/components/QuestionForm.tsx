import type { FormEvent } from "react";

interface Props {
  value: string;
  loading: boolean;
  onChange(value: string): void;
  onSubmit(): void;
}

export function QuestionForm({ value, loading, onChange, onSubmit }: Props) {
  const disabled = loading || !value.trim();

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!disabled) onSubmit();
  }

  return (
    <form className="question-form" onSubmit={handleSubmit}>
      <label htmlFor="question">Pergunta</label>
      <div className="question-row">
        <input
          id="question"
          type="text"
          autoComplete="off"
          maxLength={500}
          placeholder="quanto é 15% de 3.200 em 6 parcelas?"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="submit" disabled={disabled}>
          {loading ? "Calculando…" : "Calcular"}
        </button>
      </div>
    </form>
  );
}
