import { useEffect, useRef, useState } from "react";
import { api, day } from "../api.js";
import { GeminiIcon, SparkIcon, IconClose, IconRefresh } from "../icons.jsx";
import RichText from "./RichText.jsx";

// Use cases a manager actually has. Each is answerable from SignalBridge data.
const USE_CASES = [
  { tag: "Daily briefing", icon: "☀️", text: "Give me today's supply-chain briefing" },
  { tag: "Shipment risk", icon: "🚢", text: "Which shipments are at risk right now, and why?" },
  { tag: "Weather", icon: "⛈️", text: "Is there severe weather along any of our shipping routes?" },
  { tag: "Port news", icon: "📰", text: "Any strikes, closures or congestion reported at our ports?" },
  { tag: "Revenue", icon: "💰", text: "How much revenue is at risk, and from which customers?" },
  { tag: "Customers", icon: "⭐", text: "Which VIP customers could miss their delivery date?" },
  { tag: "Inventory", icon: "📦", text: "Where do we have spare stock we could move today?" },
  { tag: "Recoveries", icon: "✅", text: "What recovery actions have been approved so far?" },
];

// Mirrors the backend's news trigger, only to show the right loading message.
const NEWS_RE = /\b(news|headlines?|strikes?|closures?|closed|protests?|congestion|suspend\w*|blockade|disrupt\w*|reported|latest|happening|briefing)\b/i;

const isSafeUrl = (url) => /^https?:\/\//i.test(String(url || ""));

export default function GeminiPanel({ open, onClose }) {
  const [thread, setThread] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [stages, setStages] = useState([]);
  const [suggested, setSuggested] = useState([]);
  const bodyRef = useRef(null);
  const inputRef = useRef(null);

  // Personalised prompts from the live incident list, fetched once.
  useEffect(() => {
    if (!open || suggested.length) return;
    api.incidents()
      .then((d) =>
        setSuggested(
          (d.incidents || []).slice(0, 2).map(
            (i) => `Explain the ${i.sku} shortage at ${i.location_id} (due ${day(i.deadline)}) and what I should do`
          )
        )
      )
      .catch(() => {});
  }, [open, suggested.length]);

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => inputRef.current?.focus(), 250);
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(t);
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: "smooth" });
  }, [thread, busy]);

  // Advance the loading narration while we wait.
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStage((s) => Math.min(s + 1, stages.length - 1)), 1300);
    return () => clearInterval(t);
  }, [busy, stages.length]);

  async function send(text) {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    const history = thread
      .filter((m) => !m.error)
      .slice(-8)
      .map((m) => ({ role: m.role, text: m.text }));
    setThread((t) => [...t, { role: "user", text: question }]);
    setStages([
      "Reading shipments, stock, orders and recovery plans",
      "Checking live weather along every route",
      ...(NEWS_RE.test(question) ? ["Searching port and disruption news"] : []),
      "Asking Gemini",
    ]);
    setStage(0);
    setBusy(true);
    try {
      const out = await api.askAll(question, history);
      setThread((t) => [
        ...t,
        { role: "model", text: out.text, source: out.source, sources: out.sources || [], articles: out.articles || [] },
      ]);
    } catch (e) {
      setThread((t) => [...t, { role: "model", text: "I couldn't reach the SignalBridge API: " + e.message, error: true }]);
    } finally {
      setBusy(false);
    }
  }

  function autoGrow(el) {
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  }

  return (
    <aside className={"gpanel" + (open ? " open" : "")} aria-label="Ask Gemini" aria-hidden={!open}>
      <header className="gpanel-head">
        <GeminiIcon size={24} id="gpanel-gem" />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="gpanel-title">Gemini</div>
          <div className="gpanel-sub">Sees shipments, routes, stock, orders, plans, live weather & news</div>
        </div>
        {thread.length > 0 && (
          <button className="icon-btn" onClick={() => setThread([])} title="New chat" aria-label="New chat">
            <IconRefresh size={20} />
          </button>
        )}
        <button className="icon-btn" onClick={onClose} title="Close" aria-label="Close Gemini">
          <IconClose size={20} />
        </button>
      </header>

      <div className="gpanel-body" ref={bodyRef}>
        {thread.length === 0 ? (
          <>
            <div className="g-greet">Hello</div>
            <div className="g-greet-sub">How can I help with your supply chain today?</div>

            {suggested.length > 0 && (
              <>
                <div className="g-label">Suggested for you</div>
                <div className="g-suggested">
                  {suggested.map((s) => (
                    <button key={s} className="chip-btn g-suggest" onClick={() => send(s)}>
                      <SparkIcon size={13} /> {s}
                    </button>
                  ))}
                </div>
              </>
            )}

            <div className="g-label">Things you can ask</div>
            <div className="g-grid">
              {USE_CASES.map((u) => (
                <button key={u.text} className="g-card" onClick={() => send(u.text)}>
                  <span className="g-tag"><span aria-hidden="true">{u.icon}</span>{u.tag}</span>
                  <span className="g-text">{u.text}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="g-thread">
            {thread.map((m, i) =>
              m.role === "user" ? (
                <div className="msg me" key={i}>
                  <div className="bubble">{m.text}</div>
                </div>
              ) : (
                <div className="g-answer" key={i}>
                  <GeminiIcon size={22} id={"ga" + i} />
                  <div className={"g-answer-body" + (m.error ? " err" : "")}>
                    <RichText text={m.text} />
                    {m.sources?.length > 0 && (
                      <div className="g-sources">
                        {m.sources.map((s) => (
                          <span key={s.label} className={"g-src " + s.kind}>{s.label}</span>
                        ))}
                      </div>
                    )}
                    {m.articles?.filter((a) => isSafeUrl(a.url)).length > 0 && (
                      <div className="g-articles">
                        {m.articles.filter((a) => isSafeUrl(a.url)).slice(0, 4).map((a) => (
                          <a key={a.url} href={a.url} target="_blank" rel="noopener noreferrer">
                            {a.title || a.url}
                            <span className="g-dom"> · {a.domain}</span>
                          </a>
                        ))}
                      </div>
                    )}
                    {m.source && <div className="ai-src">{m.source}</div>}
                  </div>
                </div>
              )
            )}

            {busy && (
              <div className="g-answer">
                <span className="g-spin"><GeminiIcon size={22} id="g-busy" /></span>
                <div className="g-answer-body">
                  <div className="g-status">{stages[stage]}…</div>
                  <div className="g-lines"><span /><span /><span /></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <footer className="gpanel-foot">
        <div className="g-inputbox">
          <textarea
            ref={inputRef}
            rows={1}
            value={input}
            placeholder="Ask about shipments, weather, ports, stock…"
            onChange={(e) => {
              setInput(e.target.value);
              autoGrow(e.target);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            disabled={busy}
            aria-label="Message Gemini"
          />
          <button className="g-send" onClick={() => send()} disabled={busy || !input.trim()} aria-label="Send">
            <SparkIcon size={16} />
          </button>
        </div>
        <div className="g-disclaimer">Gemini uses your SignalBridge data plus live public sources. Check important decisions.</div>
      </footer>
    </aside>
  );
}
