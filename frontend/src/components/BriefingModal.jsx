import { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api'

/** 轻量 markdown 渲染：支持 #/##/### 标题、- 列表、**加粗**、段落 */
function renderMarkdown(content) {
  const lines = (content || '').split('\n')
  const elements = []
  let listItems = []

  const flushList = (key) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key} className="list-disc pl-5 space-y-0.5 my-1.5 text-sm text-sent-dim">
          {listItems}
        </ul>
      )
      listItems = []
    }
  }

  const inline = (text, key) => {
    const parts = String(text).split(/\*\*(.+?)\*\*/g)
    return (
      <span key={key}>
        {parts.map((p, i) =>
          i % 2 === 1 ? (
            <strong key={i} className="text-white font-semibold">{p}</strong>
          ) : (
            <span key={i}>{p}</span>
          )
        )}
      </span>
    )
  }

  lines.forEach((line, i) => {
    const trimmed = line.trim()
    if (!trimmed) {
      flushList(`list-${i}`)
      return
    }
    if (trimmed.startsWith('### ')) {
      flushList(`list-${i}`)
      elements.push(<h4 key={`h3-${i}`} className="text-sm font-bold text-sent-blue mt-3 mb-1">{inline(trimmed.slice(4), `t-${i}`)}</h4>)
      return
    }
    if (trimmed.startsWith('## ')) {
      flushList(`list-${i}`)
      elements.push(<h3 key={`h2-${i}`} className="text-base font-bold text-white mt-4 mb-1.5">{inline(trimmed.slice(3), `t-${i}`)}</h3>)
      return
    }
    if (trimmed.startsWith('# ')) {
      flushList(`list-${i}`)
      elements.push(<h2 key={`h1-${i}`} className="text-lg font-bold text-white mt-1 mb-2">{inline(trimmed.slice(2), `t-${i}`)}</h2>)
      return
    }
    if (trimmed.startsWith('- ')) {
      listItems.push(<li key={`li-${i}`}>{inline(trimmed.slice(2), `t-${i}`)}</li>)
      return
    }
    flushList(`list-${i}`)
    elements.push(<p key={`p-${i}`} className="my-1 text-sm text-sent-dim leading-relaxed">{inline(trimmed, `t-${i}`)}</p>)
  })
  flushList('end')
  return elements
}

export default function BriefingModal({ onClose }) {
  const [briefing, setBriefing] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState('')

  const loadLatest = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/briefings/latest`)
      if (res.ok) setBriefing(await res.json())
      else setBriefing(null)
    } catch {
      setBriefing(null)
    }
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/briefings/`)
      if (res.ok) setHistory(await res.json())
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    ;(async () => {
      await Promise.all([loadHistory(), loadLatest()])
      setLoading(false)
    })()
  }, [loadHistory, loadLatest])

  const handleGenerate = async () => {
    setGenerating(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/briefings/generate`, { method: 'POST' })
      if (!res.ok) throw new Error('生成失败，请检查后端服务')
      const data = await res.json()
      setBriefing(data.briefing)
      await loadHistory()
    } catch (err) {
      setError(err.message || '生成失败，请稍后重试')
    } finally {
      setGenerating(false)
    }
  }

  const viewHistory = async (id) => {
    try {
      const res = await fetch(`${API_BASE}/briefings/${id}`)
      if (res.ok) setBriefing(await res.json())
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-sent-card border border-sent-border rounded-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-sent-border">
          <div className="flex items-center gap-3">
            <h3 className="text-lg font-semibold">📰 每日简报</h3>
            {briefing && (
              <>
                <span
                  className={`text-xs px-2 py-0.5 rounded ${
                    briefing.mode === 'llm'
                      ? 'bg-sent-blue/20 text-sent-blue'
                      : 'bg-sent-border/50 text-sent-dim'
                  }`}
                >
                  {briefing.mode === 'llm' ? '✨ AI 生成' : '📋 模板生成'}
                </span>
                <span className="text-xs text-sent-dim">
                  {briefing.created_at ? new Date(briefing.created_at.replace(' ', 'T')).toLocaleString('zh-CN') : ''}
                </span>
              </>
            )}
          </div>
          <button onClick={onClose} className="text-sent-dim hover:text-white text-xl">×</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-2 border-sent-blue border-t-transparent" />
            </div>
          ) : briefing ? (
            <div className="space-y-1">{renderMarkdown(briefing.content)}</div>
          ) : (
            <div className="text-center py-16 text-sent-dim">
              <div className="text-3xl mb-3">📭</div>
              <p>还没有简报</p>
              <p className="text-xs mt-1">点击下方"立即生成"，或等每日定时生成（默认北京时间 08:30）</p>
            </div>
          )}
          {error && (
            <div className="mt-3 text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{error}</div>
          )}
        </div>

        {/* History */}
        {history.length > 0 && (
          <div className="px-6 pb-2 pt-2 border-t border-sent-border">
            <div className="text-xs text-sent-dim mb-1.5">历史简报</div>
            <div className="flex flex-wrap gap-1.5">
              {history.slice(0, 10).map((h) => (
                <button
                  key={h.id}
                  onClick={() => viewHistory(h.id)}
                  className={`text-xs px-2 py-1 rounded-md transition-colors ${
                    briefing && briefing.id === h.id
                      ? 'bg-sent-blue text-white'
                      : 'bg-sent-border/30 text-sent-dim hover:text-white'
                  }`}
                >
                  {h.briefing_date}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-4 border-t border-sent-border">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full px-4 py-2 bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 transition-colors disabled:opacity-50 text-sm"
          >
            {generating ? '⏳ 生成中...' : '🔄 立即生成今日简报'}
          </button>
        </div>
      </div>
    </div>
  )
}
