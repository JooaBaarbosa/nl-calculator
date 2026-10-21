import { useRef, useState } from "react";
import { calculate } from "./api";
import { Examples } from "./components/Examples";
import { History } from "./components/History";
import { QuestionForm } from "./components/QuestionForm";
import { ResultCard } from "./components/ResultCard";
import { friendlyMessage } from "./errors";
import type { HistoryItem, SolveResult } from "./types";

export default function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState<SolveResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);
  // O estado do React só muda no próximo render; a ref barra um segundo Enter imediato.
  const inFlight = useRef(false);

  async function submit(raw: string) {
    const text = raw.trim();
    if (!text || inFlight.current) return;
    inFlight.current = true;
    setLoading(true);
    setError(null);
    setCurrent(null);
    const outcome = await calculate(text);
    if ("ok" in outcome) {
      setCurrent(outcome.ok);
      setHistory((items) => [
        { question: text, result: outcome.ok },
        ...items.filter((item) => item.question !== text),
      ]);
    } else {
      setError(friendlyMessage(outcome.error));
    }
    inFlight.current = false;
    setLoading(false);
  }

  function pickExample(example: string) {
    setQuestion(example);
    void submit(example);
  }

  function showFromHistory(item: HistoryItem) {
    setQuestion(item.question);
    setError(null);
    setCurrent(item.result);
  }

  return (
    <main className="app">
      <header>
        <h1>nl-calculator</h1>
        <p>Pergunte em português. O Claude interpreta, o código calcula.</p>
      </header>
      <QuestionForm
        value={question}
        loading={loading}
        onChange={setQuestion}
        onSubmit={() => void submit(question)}
      />
      <Examples onPick={pickExample} />
      <div aria-live="polite">{current && <ResultCard result={current} />}</div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <History items={history} onSelect={showFromHistory} />
    </main>
  );
}
