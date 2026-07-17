import { useEffect, useRef, useState } from "react";
import { useChat } from "../hooks/useChat";

export function ChatView() {
  const { messages, sendMessage, sending } = useChat();
  const [input, setInput] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    sendMessage(input);
    setInput("");
  }

  return (
    <div>
      <div className="view-header">
        <h1>Chat</h1>
        <p>Ask the agent about recent readings, anomalies, or reports.</p>
      </div>

      <div className="chat-panel card">
        <div className="chat-messages" ref={listRef}>
          {messages.length === 0 && (
            <div className="chat-empty">
              Try: "Any anomalies at the Miami station this week?" or "Summarize the latest report."
            </div>
          )}
          {messages.map((m) => (
            <div
              key={m.id}
              className={`chat-bubble chat-bubble--${m.role}${m.pending ? " chat-bubble--pending" : ""}${
                m.error ? " chat-bubble--error" : ""
              }`}
            >
              {m.text}
            </div>
          ))}
        </div>
        <form className="chat-input-row" onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Message the agent..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
          />
          <button type="submit" className="btn" disabled={sending || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
