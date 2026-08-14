import { useEffect, useRef, useState } from 'react'

const API = (p) => `/api${p}`
const DEFAULT_PRODUCT =
  'Dark graphite set, crisp white bottle, teal orbital line, orange accent.'

const MEDIA_ORDER = { VIDEO: 0, IMAGE: 1, AUDIO: 2, DERIVED: 3, SOURCE: 4 }

function timeAgo(v) {
  if (!v) return ''
  const ms =
    typeof v === 'number' ? (v < 1e12 ? v * 1000 : v) : new Date(v).getTime()
  const s = (Date.now() - ms) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return `${Math.floor(s / 86400)}d ago`
}

function friendlySummary(s) {
  if (!s) return 'Build finished'
  const m = s.match(/(\d+) rebuild \/ (\d+) reuse/)
  if (m) return `${m[1]} assets rebuilt · ${m[2]} reused`
  return s
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

function Answer({ msg, graph }) {
  const video = msg.assets?.find((a) => a.node_type === 'VIDEO')
  const rest = (msg.assets || []).filter((a) => a.node_type !== 'VIDEO')
  const sorted = [...rest].sort(
    (x, y) => (MEDIA_ORDER[x.node_type] ?? 9) - (MEDIA_ORDER[y.node_type] ?? 9),
  )
  const rebuilt = new Set(msg.result?.rebuild || [])
  const reused = new Set(msg.result?.reuse || [])
  const order = graph?.order || []
  return (
    <div className="answer">
      {video && (
        <div className="hero">
          <video src={`/files/${video.path}`} controls autoPlay muted loop playsInline />
          <div className="hero-cap">Delivery ready</div>
        </div>
      )}
      <div className="sum">{friendlySummary(msg.text)}</div>
      {order.length > 0 && (
        <div className="proof">
          <div className="strip">
            {order.map((key) => {
              const st = rebuilt.has(key)
                ? 'rebuilt'
                : reused.has(key)
                  ? 'reused'
                  : 'blocked'
              return (
                <span
                  key={key}
                  className={`gnode ${st}`}
                  title={`${key} · ${st}`}
                />
              )
            })}
          </div>
          <div className="legend">
            <span>
              <i className="dot rebuilt" />
              rebuilt
            </span>
            <span>
              <i className="dot reused" />
              reused
            </span>
          </div>
        </div>
      )}
      {sorted.length > 0 && (
        <details className="more">
          <summary>All assets ({msg.assets.length})</summary>
          <div className="asset-grid">
            {sorted.map((a) => (
              <AssetCard key={a.stable_key} a={a} />
            ))}
          </div>
        </details>
      )}
    </div>
  )
}

export default function App() {
  const [messages, setMessages] = useState([])
  const [jobs, setJobs] = useState([])
  const [stats, setStats] = useState(null)
  const [graph, setGraph] = useState(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [thinking, setThinking] = useState(false)
  const bottomRef = useRef(null)

  async function loadHistory() {
    const [j, s, g] = await Promise.all([
      fetch(API('/jobs')).then((r) => r.json()),
      fetch(API('/stats')).then((r) => r.json()),
      fetch(API('/graph')).then((r) => r.json()),
    ])
    setJobs(j)
    setStats(s)
    setGraph(g)
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
        product: brief,
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

  async function openJob(job) {
    const text =
      job.result?.summary ||
      job.error ||
      (job.status === 'running' ? 'building…' : job.status)
    const assets = await fetch(API('/assets')).then((r) => r.json())
    setMessages([
      { role: 'user', text: job.payload?.brief || '(no brief)' },
      { role: 'assistant', text, assets },
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
                <span className="hist-brief">
                  {j.payload?.brief || '(untitled brief)'}
                </span>
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
                <Answer msg={m} graph={graph} />
              )}
            </div>
          ))}
          {thinking && (
            <div className="msg assistant">
              <div className="answer">
                <div className="sum thinking">
                  Generating your video<span className="dots" />
                </div>
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
