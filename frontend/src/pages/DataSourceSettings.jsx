import { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api/quant/datasource'

const DOMAIN_LABELS = {
  realtime: '实时行情（A股/港股）',
  factor: '因子数据',
  kline: 'K 线',
}

export default function DataSourceSettings() {
  const [config, setConfig] = useState(null)
  const [draft, setDraft] = useState({})
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/config`)
      if (res.ok) {
        const data = (await res.json()).domains || {}
        setConfig(data)
        const d = {}
        for (const [domain, info] of Object.entries(data)) {
          d[domain] = info.mode === 'fixed' ? info.source : 'auto'
        }
        setDraft(d)
      }
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const handleSave = async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '保存失败')
      setConfig(data.domains)
      setMessage('已保存：钉住的源将优先使用，失败仍自动降级')
      setTimeout(() => setMessage(''), 4000)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">⚙️ 数据源设置</h2>
      <p className="text-xs text-sent-dim">
        选择「自动」= 按内置优先级自动降级；选择具体数据源 = 该源优先使用（失败仍自动降级）。
        所有数据均为真实数据，不再提供演示假数据。
      </p>

      {message && <div className="text-xs text-sent-green bg-sent-green/10 px-3 py-2 rounded">{message}</div>}
      {error && <div className="text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded">{error}</div>}

      {!config ? (
        <div className="py-12 text-center text-sent-dim">加载中...</div>
      ) : (
        <div className="bg-sent-card border border-sent-border rounded-lg p-6 space-y-5 max-w-xl">
          {Object.entries(config).map(([domain, info]) => (
            <div key={domain} className="flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-bold text-white">{DOMAIN_LABELS[domain] || domain}</div>
                <div className="text-xs text-sent-dim mt-0.5">
                  可选：{['auto', ...info.options].join(' / ')}
                </div>
              </div>
              <select
                value={draft[domain] || 'auto'}
                onChange={(e) => setDraft((prev) => ({ ...prev, [domain]: e.target.value }))}
                className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
              >
                <option value="auto">自动（推荐）</option>
                {info.options.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
          ))}

          <div className="pt-3 border-t border-sent-border">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 bg-sent-blue text-white rounded hover:bg-sent-blue/80 transition-colors disabled:opacity-50 text-sm"
            >
              {saving ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
