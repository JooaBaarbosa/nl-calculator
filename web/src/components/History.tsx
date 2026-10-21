import type { HistoryItem } from "../types";

interface Props {
  items: HistoryItem[];
  onSelect(item: HistoryItem): void;
}

export function History({ items, onSelect }: Props) {
  if (items.length === 0) return null;
  return (
    <section className="history">
      <h2>Histórico desta sessão</h2>
      <ul>
        {items.map((item) => (
          <li key={item.question}>
            <button type="button" onClick={() => onSelect(item)}>
              {item.question}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
