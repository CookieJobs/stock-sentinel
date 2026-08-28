import { useState } from 'react'

const API_BASE = '/api'

async function apiError(response, fallback) {
  const body = await response.json().catch(() => ({}))
  return body.detail || fallback
}

export default function GroupManagerModal({ groups, onClose, onGroupsChanged }) {
  const [newName, setNewName] = useState('')
  const [editingGroup, setEditingGroup] = useState(null)
  const [editingName, setEditingName] = useState('')
  const [deletingGroupId, setDeletingGroupId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const createGroup = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/stock-groups/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName }),
      })
      if (!response.ok) throw new Error(await apiError(response, '创建分组失败'))
      setNewName('')
      await onGroupsChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const saveRename = async (event) => {
    event.preventDefault()
    if (!editingGroup) return
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/stock-groups/${editingGroup.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editingName }),
      })
      if (!response.ok) throw new Error(await apiError(response, '重命名失败'))
      setEditingGroup(null)
      await onGroupsChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const deleteGroup = async (groupId) => {
    setBusy(true)
    setError('')
    try {
      const response = await fetch(`${API_BASE}/stock-groups/${groupId}`, { method: 'DELETE' })
      if (!response.ok) throw new Error(await apiError(response, '删除分组失败'))
      setDeletingGroupId(null)
      await onGroupsChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="group-manager-title">
      <div className="absolute inset-0 bg-black/60" onClick={busy ? undefined : onClose} />
      <div className="relative w-full max-w-md mx-4 bg-sent-card border border-sent-border rounded-xl p-6 max-h-[80vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <h3 id="group-manager-title" className="text-lg font-semibold">管理分组</h3>
            <p className="text-xs text-sent-dim mt-1">删除分组不会删除其中的监控股票。</p>
          </div>
          <button type="button" onClick={onClose} disabled={busy} className="text-sent-dim hover:text-white disabled:opacity-50" aria-label="关闭分组管理">✕</button>
        </div>

        <form onSubmit={createGroup} className="flex gap-2 mb-4">
          <input
            value={newName}
            onChange={(event) => setNewName(event.target.value)}
            placeholder="新分组名称，例如：长期持有"
            className="min-w-0 flex-1 bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
          />
          <button type="submit" disabled={busy} className="px-3 py-2 text-sm bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 disabled:opacity-50">新建</button>
        </form>

        {error && <p className="mb-3 text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{error}</p>}
        {groups.length === 0 ? (
          <p className="py-6 text-sm text-center text-sent-dim">还没有分组。先创建一个来整理你的自选股票。</p>
        ) : (
          <div className="space-y-2">
            {groups.map((group) => (
              <div key={group.id} className="rounded-lg bg-sent-bg border border-sent-border px-3 py-2.5">
                {editingGroup?.id === group.id ? (
                  <form onSubmit={saveRename} className="flex gap-2">
                    <input value={editingName} onChange={(event) => setEditingName(event.target.value)} className="min-w-0 flex-1 bg-sent-card border border-sent-border rounded px-2 py-1 text-sm text-white focus:outline-none focus:border-sent-blue" autoFocus />
                    <button type="submit" disabled={busy} className="text-xs text-sent-blue hover:text-white disabled:opacity-50">保存</button>
                    <button type="button" onClick={() => setEditingGroup(null)} disabled={busy} className="text-xs text-sent-dim hover:text-white">取消</button>
                  </form>
                ) : (
                  <div className="flex items-center gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-white truncate">{group.name}</p>
                      <p className="text-xs text-sent-dim mt-0.5">{group.stock_count} 只股票</p>
                    </div>
                    <button type="button" onClick={() => { setEditingGroup(group); setEditingName(group.name); setError('') }} disabled={busy} className="text-xs text-sent-dim hover:text-sent-yellow">改名</button>
                    <button type="button" onClick={() => setDeletingGroupId(group.id)} disabled={busy} className="text-xs text-sent-dim hover:text-sent-red">删除</button>
                  </div>
                )}
                {deletingGroupId === group.id && (
                  <div className="mt-3 pt-3 border-t border-sent-border">
                    <p className="text-xs text-sent-dim mb-2">删除“{group.name}”后，组内股票会保留在监控列表中。确认删除吗？</p>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => deleteGroup(group.id)} disabled={busy} className="px-2.5 py-1 text-xs bg-sent-red text-white rounded hover:bg-sent-red/80 disabled:opacity-50">确认删除</button>
                      <button type="button" onClick={() => setDeletingGroupId(null)} disabled={busy} className="px-2.5 py-1 text-xs text-sent-dim hover:text-white">取消</button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
