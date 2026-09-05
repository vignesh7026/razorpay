import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { fetchOnePager } from '../lib/api'

interface OnePagerModalProps {
  open: boolean
  onClose: () => void
}

export default function OnePagerModal({ open, onClose }: OnePagerModalProps) {
  const [html, setHtml] = useState<string | null>(null)
  const [provider, setProvider] = useState<'real' | 'simulated' | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    setError(false)
    fetchOnePager()
      .then((res) => {
        setHtml(res.html)
        setProvider(res.provider)
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [open])

  function handlePrint() {
    iframeRef.current?.contentWindow?.print()
  }

  function handleOpenInNewTab() {
    if (!html) return
    const blob = new Blob([html], { type: 'text/html' })
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="onepager-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="onepager-modal glass"
            initial={{ opacity: 0, scale: 0.95, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 16 }}
            transition={{ type: 'spring', stiffness: 320, damping: 30 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="onepager-head">
              <div>
                <strong>One-pager export</strong>
                {provider && (
                  <span className={`narrative-provider-badge ${provider}`} style={{ marginLeft: 10 }}>
                    {provider === 'real' ? 'Written by Claude' : 'Template-generated'}
                  </span>
                )}
              </div>
              <div className="onepager-actions">
                <button onClick={handleOpenInNewTab} disabled={!html}>
                  Open in new tab
                </button>
                <button className="primary" onClick={handlePrint} disabled={!html}>
                  Print / Save as PDF
                </button>
                <button onClick={onClose} aria-label="Close">
                  ×
                </button>
              </div>
            </div>
            <div className="onepager-body">
              {loading && (
                <div className="loading-state">
                  <span className="spinner large" />
                  <p>Generating one-pager…</p>
                </div>
              )}
              {error && <div className="audit-empty">Couldn't generate the one-pager. Is the backend running?</div>}
              {html && !loading && (
                <iframe ref={iframeRef} title="One-pager" srcDoc={html} className="onepager-iframe" />
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
