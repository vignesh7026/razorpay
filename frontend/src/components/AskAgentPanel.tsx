import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { askAgent, type AskMessage } from '../lib/api'

const SUGGESTIONS = [
  'What is the overall recovery rate?',
  'Which failure reason recovers best?',
  'Tell me about the escalated cases',
  'How much profit was recovered vs at risk?',
]

interface ChatMessage extends AskMessage {
  id: string
  provider?: 'real' | 'simulated'
}

export default function AskAgentPanel() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  async function send(question: string) {
    if (!question.trim() || loading) return
    const userMsg: ChatMessage = { id: `${Date.now()}-u`, role: 'user', content: question }
    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await askAgent(question, history)
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-a`, role: 'assistant', content: res.answer, provider: res.provider },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-err`, role: 'assistant', content: "Couldn't reach the agent. Is the backend running?" },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <motion.button
        className="ask-fab"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ scale: 1.06 }}
        whileTap={{ scale: 0.94 }}
        aria-label="Ask the agent"
      >
        {open ? (
          <span>×</span>
        ) : (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path
              d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H10l-4.5 4v-4h-1A2.5 2.5 0 0 1 2 13.5v0"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinejoin="round"
            />
            <circle cx="8" cy="9.5" r="1" fill="currentColor" />
            <circle cx="12" cy="9.5" r="1" fill="currentColor" />
            <circle cx="16" cy="9.5" r="1" fill="currentColor" />
          </svg>
        )}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="ask-panel glass"
            initial={{ opacity: 0, y: 24, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.96 }}
            transition={{ type: 'spring', stiffness: 340, damping: 30 }}
          >
            <div className="ask-panel-head">
              <div>
                <strong>Ask the Agent</strong>
                <p>Grounded in this run's live audit log</p>
              </div>
            </div>

            <div className="ask-panel-body" ref={bodyRef}>
              {messages.length === 0 && (
                <div className="ask-suggestions">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`ask-msg ${m.role}`}>
                  <div className="ask-msg-bubble">
                    {m.content}
                    {m.provider && (
                      <span className={`ask-provider-tag ${m.provider}`}>
                        {m.provider === 'real' ? 'Claude' : 'simulated'}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="ask-msg assistant">
                  <div className="ask-msg-bubble ask-typing">
                    <span /> <span /> <span />
                  </div>
                </div>
              )}
            </div>

            <form
              className="ask-panel-input"
              onSubmit={(e) => {
                e.preventDefault()
                send(input)
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about this run…"
              />
              <button type="submit" disabled={loading || !input.trim()}>
                Send
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
