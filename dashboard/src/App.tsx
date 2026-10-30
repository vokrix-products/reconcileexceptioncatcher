import { useEffect, useMemo, useRef, useState } from 'react'

type Rec = {
  title: string
  status: string
  due_date: string | null
  details: { [key: string]: any }
}

type Payload = {
  source_file_name?: string
  count: number
  records: Rec[]
}

const PRODUCT_NAME = (import.meta.env.VITE_PRODUCT_NAME as string) || 'ReconcileExceptionCatcher'
const PRODUCT_DESCRIPTION =
  (import.meta.env.VITE_PRODUCT_DESCRIPTION as string) ||
  'Turn messy bank and ledger CSVs into a green/amber reconciliation exception dashboard with audit-ready evidence.'
const PAYWALL_TITLE = (import.meta.env.VITE_PAYWALL_TITLE as string) || 'You have used your 3 free Transactions'
const PAYWALL_DESCRIPTION =
  (import.meta.env.VITE_PAYWALL_DESCRIPTION as string) || 'Upgrade to get unlimited Transactions.'

const DEFAULT_API =
  (import.meta.env.VITE_API_URL as string) || 'https://reconcileexceptioncatcher-production.up.railway.app'
const FREE_LIMIT = 3
const USAGE_KEY = 'tieout_usage'
const API_KEY = 'tieout_api_base'

const SAMPLE_CSV = [
  'supplier,amount,date,memo',
  'Acme Industrial,1250.00,2024-01-15,Invoice 88213',
  'Northwind Freight,430.75,2024-01-18,Freight charge',
  'Contoso Supplies,,2024-01-19,Missing amount row',
  'Fabrikam Ltd,98.40,,Missing date row',
  'Acme Industrial,1250.00,2024-01-15,Invoice 88213 DUPLICATE',
  'Tailspin Toys,2210.10,01/22/2024,PO 4471',
  'Wingtip Traders,not-a-number,2024-01-24,Bad amount formatting',
].join('\n')

function fmtMoney(value: any): string {
  const n = typeof value === 'number' ? value : parseFloat(String(value ?? ''))
  if (!isFinite(n)) return '--'
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD' })
}

function readUsage(): number {
  try {
    const raw = window.localStorage.getItem(USAGE_KEY)
    const n = raw ? parseInt(raw, 10) : 0
    return isFinite(n) ? n : 0
  } catch (e) {
    return 0
  }
}

export default function App() {
  const [apiBase, setApiBase] = useState<string>(() => {
    try {
      return window.localStorage.getItem(API_KEY) || DEFAULT_API
    } catch (e) {
      return DEFAULT_API
    }
  })
  const [records, setRecords] = useState<Rec[]>([])
  const [sourceName, setSourceName] = useState<string>('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string>('')
  const [filter, setFilter] = useState<'all' | 'confirmed:good' | 'exception:warning'>('all')
  const [query, setQuery] = useState('')
  const [hot, setHot] = useState(false)
  const [usage, setUsage] = useState<number>(() => readUsage())
  const [paywall, setPaywall] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const fileRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    try {
      window.localStorage.setItem(API_KEY, apiBase)
    } catch (e) {}
  }, [apiBase])

  const stats = useMemo(() => {
    const total = records.length
    const good = records.filter((r) => r.status === 'confirmed:good').length
    const warnings = records.filter((r) => r.status === 'exception:warning').length
    const rate = total ? Math.round((warnings / total) * 100) : 0
    return { total, good, warnings, rate }
  }, [records])

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return records.filter((r) => {
      if (filter !== 'all' && r.status !== filter) return false
      if (!q) return true
      const hay = [
        r.title,
        r.due_date,
        String(r.details?.extracted_amount ?? ''),
        r.details?.memo,
        r.details?.description,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.indexOf(q) !== -1
    })
  }, [records, filter, query])

  async function send(blob: Blob, filename: string) {
    if (usage >= FREE_LIMIT) {
      setPaywall(true)
      return
    }
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', blob, filename)
      const base = apiBase.replace(/\/+$/, '')
      const res = await fetch(base + '/process', { method: 'POST', body: form })
      if (!res.ok) throw new Error('Processing service returned HTTP ' + res.status)
      const data: Payload = await res.json()
      setRecords(Array.isArray(data.records) ? data.records : [])
      setSourceName(data.source_file_name || filename)
      const next = usage + 1
      setUsage(next)
      try {
        window.localStorage.setItem(USAGE_KEY, String(next))
      } catch (e) {}
      if (next >= FREE_LIMIT) setPaywall(true)
    } catch (e: any) {
      setError(
        (e && e.message ? e.message : 'Request failed') +
          ' - confirm the worker URL in settings (it must point at the Railway service).'
      )
    } finally {
      setBusy(false)
    }
  }

  function onFiles(list: FileList | null) {
    if (!list || !list.length) return
    const file = list[0]
    send(file, file.name || 'upload.csv')
  }

  return (
    <div className="shell">
      <div className="topbar">
        <div>
          <div className="brand">TieOut / reconciliation evidence</div>
          <h1>{PRODUCT_NAME}</h1>
          <p className="sub">{PRODUCT_DESCRIPTION}</p>
        </div>
        <div className="row">
          <span className="pill">
            {usage}/{FREE_LIMIT} free runs used
          </span>
          <button className="btn secondary" onClick={() => setSettingsOpen((v) => !v)}>
            Worker settings
          </button>
        </div>
      </div>

      {settingsOpen ? (
        <div className="card" style={{ marginTop: 18 }}>
          <div className="label">Processing worker base URL</div>
          <div className="row" style={{ marginTop: 8 }}>
            <input
              type="url"
              value={apiBase}
              onChange={(e) => setApiBase(e.target.value)}
              placeholder="https://your-service.up.railway.app"
            />
          </div>
          <p className="sub" style={{ fontSize: 12, marginTop: 8 }}>
            Uploads are posted to <span className="mono">{apiBase.replace(/\/+$/, '')}/process</span>.</p>
        </div>
      ) : null}

      <div className="grid-2">
        <div className="card">
          <div className="label">Upload bank or ledger file</div>
          <div
            className={'drop' + (hot ? ' hot' : '')}
            style={{ marginTop: 10 }}
            onDragOver={(e) => {
              e.preventDefault()
              setHot(true)
            }}
            onDragLeave={() => setHot(false)}
            onDrop={(e) => {
              e.preventDefault()
              setHot(false)
              onFiles(e.dataTransfer.files)
            }}
          >
            <div className="row" style={{ justifyContent: 'center' }}>
              <button className="btn" disabled={busy} onClick={() => fileRef.current?.click()}>
                {busy ? 'Processing...' : 'Choose file'}
              </button>
              <button
                className="btn secondary"
                disabled={busy}
                onClick={() => send(new Blob([SAMPLE_CSV], { type: 'text/csv' }), 'sample_ledger.csv')}
              >
                Run sample ledger
              </button>
            </div>
            CSV, Excel, PDF or plain text. Rows are reconciled; exceptions are flagged amber.
            <input
              ref={fileRef}
              type="file"
              style={{ display: 'none' }}
              onChange={(e) => {
                onFiles(e.target.files)
                if (fileRef.current) fileRef.current.value = ''
              }}
            />
          </div>
          {error ? <div className="err">{error}</div> : null}
        </div>

        <div className="card">
          <div className="label">Reconciliation summary</div>
          <div className="stats" style={{ marginTop: 10 }}>
            <div className="stat">
              <div className="label">Rows</div>
              <div className="n blue">{stats.total}</div>
            </div>
            <div className="stat">
              <div className="label">Confirmed</div>
              <div className="n green">{stats.good}</div>
            </div>
            <div className="stat">
              <div className="label">Exceptions</div>
              <div className="n amber">{stats.warnings}</div>
            </div>
          </div>
          <p className="sub" style={{ fontSize: 12, marginTop: 12 }}>
            {sourceName ? 'Source: ' + sourceName : 'No file processed yet.'}
            {stats.total ? ' - exception rate ' + stats.rate + '%' : ''}</p>
        </div>
      </div>

      <div className="toolbar">
        <div className="tabs">
          <button className={'tab' + (filter === 'all' ? ' active' : '')} onClick={() => setFilter('all')}>
            All ({stats.total})
          </button>
          <button
            className={'tab' + (filter === 'confirmed:good' ? ' active' : '')}
            onClick={() => setFilter('confirmed:good')}
          >
            Confirmed ({stats.good})
          </button>
          <button
            className={'tab' + (filter === 'exception:warning' ? ' active' : '')}
            onClick={() => setFilter('exception:warning')}
          >
            Exceptions ({stats.warnings})
          </button>
        </div>
        <div className="search">
          <input
            type="text"
            placeholder="Search supplier, memo, amount or date..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="card" style={{ marginTop: 14, padding: 0 }}>
        {visible.length === 0 ? (
          <div className="empty">No rows to show. Upload a file or run the sample ledger.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Supplier / Title</th>
                <th>Status</th>
                <th>Amount</th>
                <th>Date</th>
                <th>Source</th>
                <th>Evidence</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((r, i) => (
                <tr key={String(r.details?.row_uid || i)}>
                  <td style={{ fontWeight: 600 }}>{r.title}</td>
                  <td>
                    <span className={'chip ' + (r.status === 'confirmed:good' ? 'good' : 'warn')}>
                      {r.status === 'confirmed:good' ? 'confirmed' : 'exception'}
                    </span>
                  </td>
                  <td className="mono">{fmtMoney(r.details?.extracted_amount)}</td>
                  <td className="mono">{r.due_date || '--'}</td>
                  <td className="mono">{String(r.details?.source_row_number ?? '--')}</td>
                  <td>
                    <details>
                      <summary>row_uid</summary>
                      <pre>{String(r.details?.row_uid || '')}</pre>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="foot">
        <span>{PRODUCT_NAME} / audit-ready exception evidence</span>
        <a
          href="https://reconcileexceptioncatcher.vokrix.co"
          style={{ color: '#7dd3fc', textDecoration: 'none' }}
        >
          reconcileexceptioncatcher.vokrix.co
        </a>
      </div>

      {paywall ? (
        <div className="modal-back" onClick={() => setPaywall(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="brand">Plan limit reached</div>
            <h2>{PAYWALL_TITLE}</h2>
            {PAYWALL_DESCRIPTION}
            <div className="row" style={{ marginTop: 18 }}>
              <a className="btn" href="https://vokrix.co" target="_blank" rel="noreferrer">
                Upgrade now
              </a>
              <button className="btn secondary" onClick={() => setPaywall(false)}>
                Not now
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
