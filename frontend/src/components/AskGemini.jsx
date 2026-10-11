import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { GeminiIcon, SparkIcon } from "../icons.jsx";
import RichText from "./RichText.jsx";

// Starter questions, Google-style suggestion chips. These lean on the rich
// context the backend sends (product cost/price, customers, shipments, events).
const SUGGESTIONS = [
  "Explain this whole plan simply",
  "What is my margin impact?",
  "Which customer is affected and why does it matter?",
  "Why were the other suppliers rejected?",
  "What caused this disruption?",
  "What happens if we do nothing?",
];

export default function AskGemini({ sku, loc }) {
  const [open, setOpen] = useState(false);
  const [thread, setThread] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [thread, busy]);

  async function send(question) {
    const q = (question ?? input).trim();
    if (!q || busy) return;
    setInput("");
    setThread((t) => [...t, { who: "me", text: q }]);
    setBusy(true);
    try {
      const out = await api.ask(sku, loc, q);
      setThread((t) => [...t, { who: "ai", text: out.text, source: out.source }]);
    } catch (e) {
      setThread((t) => [...t, { who: "ai", text: "Could not reach Gemini: " + e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div className="ask-cta">
        <GeminiIcon size={24} id="ask-cta-gem" />
        <div style={{ flex: 1 }}>
          <strong>Have a question about this plan?</strong>
          <p>Gemini has the full plan as context — ask anything.</p>
        </div>
        <button className="btn gemini" onClick={() => { setOpen(true); setTimeout(() => inputRef.current?.focus(), 60); }}>
          <SparkIcon size={15} />
          Ask Gemini
        </button>
      </div>
    );
  }

  return (
    <div>
      {thread.length === 0 && (
        <>
          <p className="card-sub">Try one of these, or type your own question:</p>
          <div className="chips">
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip-btn" onClick={() => send(s)}>{s}</button>
            ))}
          </div>
        </>
      )}

      <div className="thread">
        {thread.map((m, i) =>
          m.who === "me" ? (
            <div className="msg me" key={i}>
              <div className="bubble">{m.text}</div>
            </div>
          ) : (
            <div className="msg" key={i}>
              <span className="avatar"><GeminiIcon size={18} id={"a" + i} /></span>
              <div className={"bubble" + (m.error ? " err" : "")}>
                <RichText text={m.text} />
                {m.source && <div className="ai-src">source: {m.source}</div>}
              </div>
            </div>
          )
        )}

        {busy && (
          <div className="msg">
            <span className="avatar"><GeminiIcon size={18} id="typing-gem" /></span>
            <div className="bubble">
              <span className="typing"><i /><i /><i /></span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="ask-bar">
        <input
          ref={inputRef}
          className="ask-input"
          placeholder="Ask about this recovery plan…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          disabled={busy}
        />
        <button className="btn gemini" onClick={() => send()} disabled={busy || !input.trim()}>
          <SparkIcon size={15} />
          {busy ? "Thinking…" : "Ask"}
        </button>
      </div>
      <p className="card-sub" style={{ marginTop: 8 }}>
        Answers are grounded in this plan's data only. Gemini can be slow on the free tier.
      </p>
    </div>
  );
}
