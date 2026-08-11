import { useEffect, useRef, useState } from 'react';
import { assistantApi, errorMessage } from '../api/client';

const SUGGESTIONS = [
  'I have a headache and feel nauseous when I stand up',
  'I have had a dry cough for two weeks, what could cause it?',
  'Why do I feel pain in my lower right abdomen?',
];

const LIKELIHOOD_STYLE = {
  common: 'badge-ok',
  possible: 'badge-warn',
  'less common': 'badge-muted',
};

const URGENCY_STYLE = {
  'self-care': 'badge-ok',
  'see-doctor-soon': 'badge-warn',
  emergency: 'badge-danger',
};

const URGENCY_LABEL = {
  'self-care': 'Self-care may be enough',
  'see-doctor-soon': 'See a doctor soon',
  emergency: 'Seek urgent care',
};

const GREETING = {
  role: 'assistant',
  content:
    "Hello. I can share general health information — for example what commonly causes a symptom, " +
    "or what a term means.\n\nI can't diagnose you, and I'm separate from MediScan AI's scan " +
    'analysis. If something feels urgent, please contact emergency services rather than asking me.',
  meta: { source: 'greeting' },
};

/** Renders **bold** and preserves line breaks without pulling in a markdown lib. */
function renderText(text) {
  return text.split('\n').map((line, lineIndex) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g).filter(Boolean);
    return (
      <span key={`${lineIndex}-${line.slice(0, 12)}`}>
        {parts.map((part, partIndex) =>
          part.startsWith('**') && part.endsWith('**') ? (
            <strong key={partIndex}>{part.slice(2, -2)}</strong>
          ) : (
            <span key={partIndex}>{part}</span>
          ),
        )}
        <br />
      </span>
    );
  });
}

function AnalysisCard({ analysis }) {
  if (!analysis) return null;
  return (
    <div
      style={{
        maxWidth: '82%',
        marginBottom: 12,
        background: '#f8fafc',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: '12px 14px',
      }}
    >
      <div className="row spread" style={{ marginBottom: 10 }}>
        <span className="tiny muted" style={{ fontWeight: 700, textTransform: 'uppercase' }}>
          Possible conditions
        </span>
        <span className={`badge ${URGENCY_STYLE[analysis.urgency] ?? 'badge-warn'}`}>
          {URGENCY_LABEL[analysis.urgency] ?? analysis.urgency}
        </span>
      </div>

      {analysis.summary && (
        <p className="small muted" style={{ marginTop: 0, marginBottom: 10 }}>
          {analysis.summary}
        </p>
      )}

      <div className="grid" style={{ gap: 8 }}>
        {analysis.conditions.map((condition, index) => (
          <div
            key={index}
            style={{
              background: '#fff',
              border: '1px solid var(--border)',
              borderRadius: 8,
              padding: '8px 10px',
            }}
          >
            <div className="row spread" style={{ marginBottom: 4 }}>
              <span className="small" style={{ fontWeight: 700 }}>
                {condition.name}
              </span>
              <span className={`badge ${LIKELIHOOD_STYLE[condition.likelihood] ?? 'badge-muted'}`}>
                {condition.likelihood}
              </span>
            </div>
            {condition.briefExplanation && (
              <p className="tiny muted" style={{ margin: 0 }}>
                {condition.briefExplanation}
              </p>
            )}
          </div>
        ))}
      </div>

      {analysis.recommendedAction && (
        <p className="small" style={{ marginBottom: 0, marginTop: 10 }}>
          <strong>Recommended:</strong> {analysis.recommendedAction}
        </p>
      )}
    </div>
  );
}

function Bubble({ message }) {
  const isUser = message.role === 'user';
  const emergency = message.meta?.emergency;
  const unavailable = message.meta?.modelUnavailable;

  const background = isUser
    ? 'var(--brand)'
    : emergency
      ? 'var(--danger-bg)'
      : unavailable
        ? 'var(--warn-bg)'
        : '#fff';

  const border = emergency
    ? '1px solid var(--danger-border)'
    : unavailable
      ? '1px solid var(--warn-border)'
      : '1px solid var(--border)';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 12,
      }}
    >
      <div
        style={{
          maxWidth: '78%',
          background,
          color: isUser ? '#fff' : 'var(--ink)',
          border: isUser ? 'none' : border,
          borderRadius: 12,
          padding: '10px 14px',
          fontSize: 14,
          lineHeight: 1.55,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {emergency && (
          <div
            className="tiny"
            style={{ fontWeight: 800, color: 'var(--danger)', marginBottom: 6 }}
          >
            URGENT — SAFETY RESPONSE
          </div>
        )}
        {renderText(message.content)}
      </div>
    </div>
  );
}

export default function Assistant() {
  const [messages, setMessages] = useState([GREETING]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const endRef = useRef(null);

  useEffect(() => {
    assistantApi
      .status()
      .then(setStatus)
      .catch(() => setStatus({ configured: false }));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending]);

  const send = async (event, preset) => {
    event?.preventDefault();
    const text = (preset ?? input).trim();
    if (!text || sending) return;

    const history = messages
      .filter((message) => message.meta?.source !== 'greeting')
      .map(({ role, content }) => ({ role, content }));

    setMessages((current) => [...current, { role: 'user', content: text }]);
    setInput('');
    setSending(true);
    setError('');

    try {
      const response = await assistantApi.chat(text, history);
      setMessages((current) => [
        ...current,
        {
          role: 'assistant',
          content: response.reply,
          meta: {
            emergency: response.emergency,
            source: response.source,
            modelUnavailable: response.modelUnavailable,
            analysis: response.analysis,
          },
        },
      ]);
    } catch (err) {
      setError(errorMessage(err, 'Could not reach the assistant.'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: 780 }}>
      <h1 style={{ marginBottom: 4 }}>Medical Assistant</h1>
      <p className="muted">
        General health information. Separate from MediScan AI's image analysis — this assistant
        does not read scans and cannot diagnose.
      </p>

      {status && !status.configured && (
        <div className="alert alert-warn">
          <strong>Assistant not configured.</strong> The server has no LLM API key set
          (<code>MEDISCAN_ASSISTANT_API_KEY</code>). The safety guard still works, but general
          questions cannot be answered.
        </div>
      )}

      {error && <div className="alert alert-danger">{error}</div>}

      <div
        className="card"
        style={{
          marginTop: 16,
          padding: 16,
          height: 460,
          overflowY: 'auto',
          background: '#fbfcfe',
        }}
      >
        {messages.map((message, index) => (
          <div key={index}>
            <Bubble message={message} />
            {message.role === 'assistant' && message.meta?.analysis && (
              <AnalysisCard analysis={message.meta.analysis} />
            )}
          </div>
        ))}

        {sending && (
          <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
            <div
              style={{
                background: '#fff',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: '10px 14px',
              }}
            >
              <span className="tiny muted">Thinking…</span>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {messages.length === 1 && (
        <div className="row" style={{ flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              className="btn-ghost"
              style={{ padding: '6px 12px', fontSize: 12 }}
              onClick={(event) => send(event, suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={send} className="row" style={{ gap: 10, marginTop: 14 }}>
        <input
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Describe a symptom or ask a general health question…"
          maxLength={4000}
          disabled={sending}
          style={{ flex: 1 }}
          aria-label="Message"
        />
        <button type="submit" className="btn-primary" disabled={sending || !input.trim()}>
          {sending ? <span className="spinner" /> : 'Send'}
        </button>
      </form>

      <div className="alert alert-warn" style={{ marginTop: 16, marginBottom: 0 }}>
        <strong>This is not a replacement for professional medical advice.</strong> Information
        here is general and educational only. For diagnosis or treatment consult a qualified
        healthcare professional. In an emergency call your local emergency number (108 or 112
        in India).
      </div>
    </div>
  );
}
