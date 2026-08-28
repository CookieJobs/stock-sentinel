import { useState } from 'react'

const API_BASE = '/api'

async function apiError(response, fallback) {
  const body = await response.json().catch(() => ({}))
  return body.detail || fallback
}

export default function AssignStocksToGroupsModal({ groups, stockIds, onClose, onGroupsChanged }) {
  const [selectedGroupIds, setSelectedGroupIds] = useState(new Set())
  const [newGroupName, setNewGroupName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const toggleGroup = (groupId) => {
    setSelectedGroupIds((previous) => {
      const next = new Set(previous)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  const submit = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const targetGroupIds = [...selectedGroupIds]
      if (newGroupName.trim()) {
        const created = await fetch(`${API_BASE}/stock-groups/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newGroupName }),
        })
        if (!created.ok) throw new Error(await apiError(created, '创建分组失败'))
        targetGroupIds.push((await created.json()).id)
      }
      if (targetGroupIds.length === 0) throw new Error('请至少选择或创建一个分组')

      const results = await Promise.all(targetGroupIds.map(async (groupId) => {
        const response = await fetch(`${API_BASE}/stock-groups/${groupId}/stocks`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ stock_ids: stockIds }),
        })
        if (!response.ok) throw new Error(await apiError(response, '加入分组失败'))
      }))
      void results
      await onGroupsChanged()
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="assign-groups-title">
      <div className="absolute inset-0 bg-black/60" onClick={busy ? undefined : onClose} />
      <form onSubmit={submit} className="relative w-full max-w-md mx-4 bg-sent-card border border-sent-border rounded-xl p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 id="assign-groups-title" className="text-lg font-semibold">加入分组</h3>
            <p className="text-xs text-sent-dim mt-1">将 {stockIds.length} 只股票加入一个或多个分组。</p>
          </div>
          <button type="button" onClick={onClose} disabled={busy} className="text-sent-dim hover:text-white disabled:opacity-50" aria-label="关闭加入分组">✕</button>
        </div>

        {groups.length > 0 && (
          <div className="max-h-48 overflow-y-auto space-y-2 mb-4">
            {groups.map((group) => (
              <label key={group.id} className="flex items-center gap-3 px-3 py-2.5 bg-sent-bg rounded-lg cursor-pointer">
                <input type="checkbox" checked={selectedGroupIds.has(group.id)} onChange={() => toggleGroup(group.id)} className="accent-sent-blue" />
                <span className="min-w-0 flex-1 text-sm text-white truncate">{group.name}</span>
                <span className="text-xs text-sent-dim">{group.stock_count} 只</span>
              </label>
            ))}
          </div>
        )}

        <label className="block text-xs text-sent-dim mb-1" htmlFor="assign-new-group">同时新建分组（可选）</label>
        <input id="assign-new-group" value={newGroupName} onChange={(event) => setNewGroupName(event.target.value)} placeholder="例如：重点观察" className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue" />
        {error && <p className="mt-3 text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{error}</p>}
        <div className="flex gap-3 pt-5">
          <button type="submit" disabled={busy} className="flex-1 px-4 py-2 bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 disabled:opacity-50 text-sm">{busy ? '处理中…' : '加入分组'}</button>
          <button type="button" onClick={onClose} disabled={busy} className="px-4 py-2 border border-sent-border text-sent-dim rounded-lg hover:text-white hover:border-sent-dim disabled:opacity-50 text-sm">取消</button>
        </div>
      </form>
    </div>
  )
}
