import { useEffect, useRef, useState } from 'react'

const API = (p) => `/api${p}`
const DEFAULT_PRODUCT =
  'Dark graphite set, crisp white bottle, teal orbital line, orange accent.'

const MEDIA_ORDER = { VIDEO: 0, IMAGE: 1, AUDIO: 2, DERIVED: 3, SOURCE: 4 }

function timeAgo(iso) {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function TextAsset({ path }) {
  const [text, setText] = useState('')
  useEffect(() => {
    fetch(`/files/${path}`)
      .then((r) => r.text())
      .then(setText)
      .catch(() => setText(''))
  }, [path])
  return <pre className="text">{text}</pre>
}

function AssetCard({ a }) {
  return (
    <div className={`asset ${a.node_type.toLowerCase()}`}>
      {a.node_type === 'IMAGE' && <img src={`/files/${a.path}`} alt={a.stable_key} />}
      {a.node_type === 'VIDEO' && <video src={`/files/${a.path}`} controls muted />}
      {a.node_type === 'AUDIO' && <audio src={`/files/${a.path}`} controls />}
      {(a.node_type === 'DERIVED' || a.node_type === 'SOURCE') && (
        <TextAsset path={a.path} />
      )}
      <div className="cap">
        <span>{a.stable_key}</span>
        <code>{a.output_hash.slice(0, 8)}</code>
      </div>
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const bottomRef = useRef(null)

  async function loadHistory() {
    const [j, s] = await Promise.all([
      fetch(API('/jobs')).then((r) => r.json()),
      fetch(API('/stats')).then((r) => r.json()),
    ])
    setJobs(j)
    setStats(s)
  }

  useEffect(() => {
    loadHistory()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  async function commitBrief(brief) {
    const res = await fetch(API('/commit'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        brief,
        product: DEFAULT_PRODUCT,
        handle: '@creator',
        submission_key: `chat-${Date.now()}`,
      }),
    })
    return (await res.json()).job_id
  }

  async function send() {
    const brief = input.trim()
    if (!brief || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [...m, { role: 'user', text: brief }])
    setThinking(true)
    try {
      const jobId = await commitBrief(brief)
      let job = null
      for (let i = 0; i < 60; i++) {
        await new Promise((r) => setTimeout(r, 2000))
        job = await fetch(API(`/jobs/${jobId}`)).then((r) => r.json())
        if (job.status === 'succeeded' || job.status === 'failed') break
      }
      const assets = await fetch(API('/assets')).then((r) => r.json())
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: job?.result?.summary || job?.error || 'build finished',
          result: job?.result,
          assets,
        },
      ])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', text: 'build failed' }])
    } finally {
      setThinking(false)
      setBusy(false)
      loadHistory()
    }
  }

  function newChat() {
    setMessages([])
  }

  function openJob(job) {
    const text =
      job.result?.summary ||
      job.error ||
      (job.status === 'running' ? 'building…' : job.status)
    setMessages([
      { role: 'user', text: job.payload?.brief || '(no brief)' },
      { role: 'assistant', text, result: job.result },
    ])
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="side-head">
          <div className="brand">DRIFT</div>
          <button className="new" onClick={newChat}>
            + New build
          </button>
        </div>
        <div className="history">
          <div className="hist-label">History</div>
          {jobs.length === 0 && <div className="empty">No builds yet.</div>}
          {jobs.map((j) => (
            <button key={j.id} className="hist-item" onClick={() => openJob(j)}>
              <span className={`dot ${j.status}`} />
              <span className="hist-text">
                <span className="hist-brief">{j.payload?.brief || j.id.slice(0, 8)}</span>
                <span className="hist-meta">
                  {j.status} · {timeAgo(j.created_at)}
                </span>
              </span>
            </button>
          ))}
        </div>
        <div className="side-foot">
          {stats && (
            <span className="foot-stat">
              {stats.succeeded} built · {stats.failed} failed
            </span>
          )}
        </div>
      </aside>

      <main className="chat">
        <div className="thread">
          {messages.length === 0 && !thinking && (
            <div className="welcome">
              <h1>What are you shipping?</h1>
              <p>
                Describe your brief. Drift turns it into an 18-node content
                pipeline — copy, captions, tags, poster, keyframes, narration and
                a delivery video — and rebuilds only what changed.
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === 'user' ? (
                <div className="bubble">{m.text}</div>
              ) : (
                <div className="answer">
                  <div className="sum">{m.text}</div>
                  {m.assets && m.assets.length > 0 && (
                    <div className="asset-grid">
                      {[...m.assets]
                        .sort(
                          (x, y) =>
                            (MEDIA_ORDER[x.node_type] ?? 9) -
                            (MEDIA_ORDER[y.node_type] ?? 9),
                        )
                        .map((a) => (
                          <AssetCard key={a.stable_key} a={a} />
                        ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          {thinking && (
            <div className="msg assistant">
              <div className="answer">
                <div className="sum thinking">building the pipeline…</div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            rows={1}
            placeholder="Describe your brief…"
          />
          <button className="send" onClick={send} disabled={busy || !input.trim()}>
            {busy ? '…' : '↑'}
          </button>
        </div>
      </main>
    </div>
  )
}
