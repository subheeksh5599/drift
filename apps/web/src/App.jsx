import { useEffect, useState } from 'react'

const API = (p) => `/api${p}`

const MEDIA_ORDER = { VIDEO: 0, IMAGE: 1, AUDIO: 2, DERIVED: 3, SOURCE: 4 }

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

export default function App() {
  const [graph, setGraph] = useState(null)
  const [jobs, setJobs] = useState([])
  const [assets, setAssets] = useState([])
  const [stats, setStats] = useState(null)
  const [form, setForm] = useState({
    brief: 'Launch a hydration brand. Dark graphite set, crisp white bottle, teal orbital line, restrained orange accent. Four shots, cinematic.',
    product: 'Dark graphite set, crisp white bottle, teal orbital line, orange accent.',
    handle: '@creator',
  })
  const [busy, setBusy] = useState(false)

  async function refresh() {
    const [g, j, a, s] = await Promise.all([
      fetch(API('/graph')).then((r) => r.json()),
      fetch(API('/jobs')).then((r) => r.json()),
      fetch(API('/assets')).then((r) => r.json()),
      fetch(API('/stats')).then((r) => r.json()),
    ])
    setGraph(g)
    setJobs(j)
    setAssets(a)
    setStats(s)
  }

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2500)
    return () => clearInterval(t)
  }, [])

  async function commit() {
    setBusy(true)
    await fetch(API('/commit'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...form, submission_key: `ui-${Date.now()}` }),
    })
    setBusy(false)
    refresh()
  }

  const byType = {}
  for (const n of graph?.nodes || []) {
    ;(byType[n.type] ||= []).push(n)
  }

  const sorted = [...assets].sort(
    (x, y) => (MEDIA_ORDER[x.node_type] ?? 9) - (MEDIA_ORDER[y.node_type] ?? 9),
  )

  return (
    <div className="app">
      <header className="top">
        <div className="brand">DRIFT</div>
        <div className="stats">
          {stats && (
            <>
              <span className="stat">{stats.pending} pending</span>
              <span className="stat">{stats.running} running</span>
              <span className="stat ok">{stats.succeeded} succeeded</span>
              <span className="stat fail">{stats.failed} failed</span>
            </>
          )}
        </div>
      </header>

      <main>
        <section className="commit">
          <h2>Commit a build</h2>
          <label>Brief</label>
          <textarea
            value={form.brief}
            onChange={(e) => setForm({ ...form, brief: e.target.value })}
            rows={3}
          />
          <div className="row">
            <div className="field">
              <label>Product reference</label>
              <input
                value={form.product}
                onChange={(e) => setForm({ ...form, product: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Handle</label>
              <input
                value={form.handle}
                onChange={(e) => setForm({ ...form, handle: e.target.value })}
              />
            </div>
          </div>
          <button className="build" onClick={commit} disabled={busy}>
            {busy ? 'Committing…' : 'Build'}
          </button>
        </section>

        <section className="jobs">
          <h2>Builds</h2>
          {jobs.length === 0 && <p className="empty">No builds yet.</p>}
          {jobs.map((j) => (
            <div key={j.id} className={`job ${j.status}`}>
              <span className="status">{j.status}</span>
              <span className="summary">{j.result?.summary || j.error || '—'}</span>
              <span className="id">{j.id.slice(0, 8)}</span>
            </div>
          ))}
        </section>

        <section className="assets">
          <h2>Assets {assets.length > 0 && <span className="count">{assets.length}</span>}</h2>
          {assets.length === 0 && <p className="empty">Run a build to generate assets.</p>}
          <div className="asset-grid">
            {sorted.map((a) => (
              <div key={a.stable_key} className={`asset ${a.node_type.toLowerCase()}`}>
                {a.node_type === 'IMAGE' && (
                  <img src={`/files/${a.path}`} alt={a.stable_key} />
                )}
                {a.node_type === 'VIDEO' && (
                  <video src={`/files/${a.path}`} controls muted />
                )}
                {a.node_type === 'AUDIO' && (
                  <audio src={`/files/${a.path}`} controls />
                )}
                {(a.node_type === 'DERIVED' || a.node_type === 'SOURCE') && (
                  <TextAsset path={a.path} />
                )}
                <div className="cap">
                  <span>{a.stable_key}</span>
                  <code>{a.output_hash.slice(0, 10)}</code>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="graph">
          <h2>Graph — {graph?.order?.length || 0} nodes</h2>
          {Object.entries(byType).map(([type, nodes]) => (
            <div key={type} className="type-group">
              <div className="type-label">{type}</div>
              <div className="nodes">
                {nodes.map((n) => (
                  <div key={n.key} className="node" title={n.inputs.join(', ')}>
                    {n.key}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      </main>
    </div>
  )
}
