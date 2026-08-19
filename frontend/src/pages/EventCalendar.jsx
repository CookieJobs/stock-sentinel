import { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api/quant'

const TYPE_META = {
  dividend: { label: '分红送转', cls: 'bg-sent-green/20 text-sent-green' },
  share_float: { label: '限售解禁', cls: 'bg-sent-yellow/20 text-sent-yellow' },
}

function todayStr(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

export default function EventCalendar() {
  const [start, setStart] = useState(todayStr())
  const [end, setEnd] = useState(todayStr(30))
  const [eventType, setEventType] = useState('')
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ start, end })
      if (eventType) params.set('event_type', eventType)
      const res = await fetch(`${API_BASE}/events?${params}`)
      if (!res.ok) throw new Error('加载失败')
      const data = await res.json()
      setEvents(data.events || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [start, end, eventType])

  useEffect(() => {
    load()
  }, [load])

  const handleRefresh = async () => {
    setRefreshing(true)
    setError('')
    setMessage('')
    try {
      const params = new URLSearchParams({ start, end })
      const res = await fetch(`${API_BASE}/events/refresh?${params}`, { method: 'POST' })
      if (!res.ok) {
        const d = await res.json().catch(() => ({}))
        throw new Error(d.detail || '刷新失败')
      }
      const data = await res.json()
      setMessage(
        `已拉取 ${data.inserted} 条事件（分红送转 ${data.dividend} / 限售解禁 ${data.share_float}）`
      )
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  const byDate = {}
  for (const e of events) {
    ;(byDate[e.event_date] = byDate[e.event_date] || []).push(e)
  }
  const dates = Object.keys(byDate).sort()

  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-xl font-bold">📅 事件日历</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="bg-sent-card border border-sent-border rounded px-2 py-1 text-sent-dim"
          />
          <span className="text-sent-dim">至</span>
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="bg-sent-card border border-sent-border rounded px-2 py-1 text-sent-dim"
          />
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="bg-sent-card border border-sent-border rounded px-2 py-1 text-sent-dim"
          >
            <option value="">全部</option>
            <option value="dividend">分红送转</option>
            <option value="share_float">限售解禁</option>
          </select>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="px-3 py-1.5 bg-sent-blue text-white rounded hover:bg-sent-blue/80 transition-colors disabled:opacity-50"
          >
            {refreshing ? '⏳ 拉取中...' : '🔄 拉取区间数据'}
          </button>
        </div>
      </div>

      {message && (
        <div className="mb-3 text-xs text-sent-green bg-sent-green/10 px-3 py-2 rounded">{message}</div>
      )}
      {error && (
        <div className="mb-3 text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded">{error}</div>
      )}

      {loading ? (
        <div className="py-16 text-center text-sent-dim">加载中...</div>
      ) : dates.length === 0 ? (
        <div className="py-16 text-center text-sent-dim">
          <div className="text-3xl mb-3">📭</div>
          <p>该区间暂无事件</p>
          <p className="text-xs mt-1">
            点击「拉取区间数据」从 Tushare 获取分红/解禁事件（免费档限 1 次/小时）
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {dates.map((d) => (
            <div key={d} className="bg-sent-card border border-sent-border rounded-lg p-4">
              <div className="text-sm font-bold text-sent-blue mb-2">{d}</div>
              <div className="space-y-1.5">
                {byDate[d].map((e, i) => {
                  const meta = TYPE_META[e.event_type] || {
                    label: e.event_type,
                    cls: 'bg-sent-border/50 text-sent-dim',
                  }
                  return (
                    <div key={`${e.id}-${i}`} className="flex items-center gap-3 text-sm">
                      <span className="font-mono text-white w-20 shrink-0">{e.ticker}</span>
                      <span className={`text-xs px-2 py-0.5 rounded shrink-0 ${meta.cls}`}>
                        {meta.label}
                      </span>
                      <span className="text-sent-dim">{e.title}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
