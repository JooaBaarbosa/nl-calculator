export const EXAMPLES: readonly string[] = [
  "Quanto é 15% de 3.200?",
  "Qual a raiz quadrada de 144?",
  "15% de 3.200 dividido em 6 parcelas",
  "2 elevado a 10",
];

interface Props {
  onPick(question: string): void;
}

export function Examples({ onPick }: Props) {
  return (
    <div className="examples">
      <span>Exemplos:</span>
      {EXAMPLES.map((example) => (
        <button key={example} type="button" onClick={() => onPick(example)}>
          {example}
        </button>
      ))}
    </div>
  );
}
