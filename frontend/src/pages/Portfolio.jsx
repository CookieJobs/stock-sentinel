/**
 * Portfolio - 组合管理（M5 充实）
 */
import { useEffect, useState } from 'react'
import { portfolios as portfolioApi } from '../lib/api'

export default function Portfolio() {
  const [list, setList] = useState([])
  const [name, setName] = useState('')
  const [benchmark, setBenchmark] = useState('000300.SH')
  const [error, setError] = useState('')

  function load() {
    portfolioApi.list().then(d => setList(d.portfolios || [])).catch(e => setError(e.message))
  }
  useEffect(() => { load() }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    try {
      await portfolioApi.create({ name, benchmark, rebalance_freq: 'monthly' })
      setName('')
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleDelete(id) {
    if (!confirm('确认删除该组合？')) return
    await portfolioApi.delete(id)
    load()
  }

  return (
    <div className="space-y-4">
      <div className="bg-sent-card border border-sent-border rounded-lg p-6">
        <h2 className="text-lg font-bold text-white mb-4">💼 组合管理</h2>

        {/* 创建组合 */}
        <form onSubmit={handleCreate} className="flex gap-2 mb-6">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="组合名（如：核心持仓、成长组合）"
            className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm flex-1 focus:outline-none focus:border-sent-blue"
          />
          <select
            value={benchmark}
            onChange={e => setBenchmark(e.target.value)}
            className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
          >
            <option value="000300.SH">沪深 300</option>
            <option value="000905.SH">中证 500</option>
            <option value="399006.SZ">创业板指</option>
            <option value="HSI">恒生指数</option>
            <option value="SPX">标普 500</option>
          </select>
          <button type="submit" className="bg-sent-blue text-sent-bg px-4 py-1.5 rounded text-sm font-bold hover:opacity-80">
            创 建
          </button>
        </form>

        {error && <div className="text-sent-red text-sm mb-4">{error}</div>}

        {/* 列表 */}
        <div className="space-y-2">
          {list.length === 0 && <div className="text-sent-dim text-sm text-center py-8">还没有组合，创建第一个吧 👆</div>}
          {list.map(p => (
            <div key={p.id} className="bg-sent-bg border border-sent-border rounded p-3 flex items-center justify-between">
              <div>
                <div className="text-white font-bold">{p.name}</div>
                <div className="text-xs text-sent-dim mt-1">
                  基准：{p.benchmark} · 调仓：{p.rebalance_freq} · 创建于 {p.created_at}
                </div>
              </div>
              <button
                onClick={() => handleDelete(p.id)}
                className="text-sent-red hover:opacity-80 text-sm"
              >
                删除
              </button>
            </div>
          ))}
        </div>

        <div className="mt-6 text-xs text-sent-dim">
          ✅ 后端组合 CRUD + 再平衡检测 ready<br />
          🚧 前端持仓编辑 + 可视化：M5 实现
        </div>
      </div>
    </div>
  )
}
