import { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api/quant/paper'

export default function PaperTrading() {
  const [portfolios, setPortfolios] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [newName, setNewName] = useState('')
  const [newCapital, setNewCapital] = useState('100000')
  const [tradeForm, setTradeForm] = useState({ ticker: '', side: 'buy', qty: '' })
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const loadList = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}`)
      if (res.ok) setPortfolios((await res.json()).portfolios || [])
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(`${API_BASE}/${selected.id}`)
        if (res.ok && !cancelled) setDetail(await res.json())
      } catch {
        /* ignore */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [selected])

  const flash = (msg) => {
    setMessage(msg)
    setTimeout(() => setMessage(''), 4000)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await fetch(`${API_BASE}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, initial_capital: parseFloat(newCapital) }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '创建失败')
      flash(`已创建模拟组合「${data.name}」`)
      setNewName('')
      await loadList()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleTrade = async (e) => {
    e.preventDefault()
    if (!selected) return
    setError('')
    setBusy(true)
    try {
      const res = await fetch(`${API_BASE}/${selected.id}/trade`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: tradeForm.ticker.trim().toUpperCase(),
          side: tradeForm.side,
          qty: parseFloat(tradeForm.qty),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '下单失败')
      flash(`成交：${data.side === 'buy' ? '买入' : '卖出'} ${data.ticker} ${data.qty} 股 @ ${data.price}`)
      setTradeForm((prev) => ({ ...prev, ticker: '', qty: '' }))
      // 刷新详情
      const res2 = await fetch(`${API_BASE}/${selected.id}`)
      if (res2.ok) setDetail(await res2.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const handleMark = async () => {
    if (!selected) return
    setBusy(true)
    try {
      const res = await fetch(`${API_BASE}/${selected.id}/mark`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '重估失败')
      flash(`已重估净值：${data.equity.toLocaleString('zh-CN')} 元`)
      const res2 = await fetch(`${API_BASE}/${selected.id}`)
      if (res2.ok) setDetail(await res2.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const fmt = (v, digits = 2) => (v == null ? '--' : Number(v).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }))

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold">📒 模拟交易（Paper Trading）</h2>
      <p className="text-xs text-sent-dim">以真实行情成交，不涉及真实资金；无真实行情时会拒绝成交。</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 左侧：组合列表 + 创建 */}
        <div className="space-y-4">
          <div className="bg-sent-card border border-sent-border rounded-lg p-4">
            <div className="text-sm font-bold text-white mb-3">我的组合</div>
            <div className="space-y-2">
              {portfolios.length === 0 && <div className="text-xs text-sent-dim">还没有组合，先创建一个</div>}
              {portfolios.map((p) => (
                <button
                  key={p.id}
                  onClick={() => setSelected(p)}
                  className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
                    selected && selected.id === p.id
                      ? 'border-sent-blue bg-sent-blue/10'
                      : 'border-sent-border/60 hover:border-sent-blue/50'
                  }`}
                >
                  <div className="text-sm font-bold text-white">{p.name}</div>
                  <div className="text-xs text-sent-dim">
                    {p.status === 'active' ? '🟢 运行中' : '🔴 已关闭'} · 初始 {fmt(p.initial_capital, 0)} · 现金 {fmt(p.cash, 0)}
                  </div>
                </button>
              ))}
            </div>
          </div>

          <form onSubmit={handleCreate} className="bg-sent-card border border-sent-border rounded-lg p-4 space-y-3">
            <div className="text-sm font-bold text-white">新建模拟组合</div>
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="组合名称"
              className="w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
            <input
              value={newCapital}
              onChange={(e) => setNewCapital(e.target.value)}
              placeholder="初始资金"
              className="w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
            <button
              disabled={busy || !newName.trim()}
              className="w-full px-3 py-1.5 bg-sent-blue text-white rounded hover:bg-sent-blue/80 disabled:opacity-50 text-sm"
            >
              创建
            </button>
          </form>
        </div>

        {/* 右侧：详情 */}
        <div className="lg:col-span-2 space-y-4">
          {!detail ? (
            <div className="py-16 text-center text-sent-dim bg-sent-card border border-sent-border rounded-lg">
              选择一个组合查看详情
            </div>
          ) : (
            <>
              {message && <div className="text-xs text-sent-green bg-sent-green/10 px-3 py-2 rounded">{message}</div>}
              {error && <div className="text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded">{error}</div>}

              {/* 概览 */}
              <div className="bg-sent-card border border-sent-border rounded-lg p-4 flex flex-wrap items-center gap-6">
                <div>
                  <div className="text-xs text-sent-dim">总资产</div>
                  <div className="text-xl font-bold text-white">{fmt(detail.total_value)}</div>
                </div>
                <div>
                  <div className="text-xs text-sent-dim">总盈亏</div>
                  <div className={`text-xl font-bold ${detail.total_pnl >= 0 ? 'text-sent-green' : 'text-sent-red'}`}>
                    {detail.total_pnl >= 0 ? '+' : ''}{fmt(detail.total_pnl)}
                  </div>
                </div>
                <div>
                  <div className="text-xs text-sent-dim">现金</div>
                  <div className="text-lg text-white">{fmt(detail.portfolio.cash)}</div>
                </div>
                <div className="ml-auto flex gap-2">
                  <button onClick={handleMark} disabled={busy} className="px-3 py-1.5 bg-sent-yellow/20 text-sent-yellow rounded text-sm hover:bg-sent-yellow/30 disabled:opacity-50">
                    重估净值
                  </button>
                </div>
              </div>

              {/* 下单 */}
              <form onSubmit={handleTrade} className="bg-sent-card border border-sent-border rounded-lg p-4 flex flex-wrap items-end gap-3">
                <label className="block">
                  <span className="text-xs text-sent-dim">代码</span>
                  <input
                    value={tradeForm.ticker}
                    onChange={(e) => setTradeForm((p) => ({ ...p, ticker: e.target.value }))}
                    placeholder="600519"
                    className="mt-1 w-32 bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
                  />
                </label>
                <label className="block">
                  <span className="text-xs text-sent-dim">方向</span>
                  <select
                    value={tradeForm.side}
                    onChange={(e) => setTradeForm((p) => ({ ...p, side: e.target.value }))}
                    className="mt-1 w-24 bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
                  >
                    <option value="buy">买入</option>
                    <option value="sell">卖出</option>
                  </select>
                </label>
                <label className="block">
                  <span className="text-xs text-sent-dim">数量</span>
                  <input
                    value={tradeForm.qty}
                    onChange={(e) => setTradeForm((p) => ({ ...p, qty: e.target.value }))}
                    placeholder="100"
                    className="mt-1 w-28 bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
                  />
                </label>
                <button disabled={busy} className="px-4 py-1.5 bg-sent-blue text-white rounded text-sm hover:bg-sent-blue/80 disabled:opacity-50">
                  下单
                </button>
              </form>

              {/* 持仓 */}
              <div className="bg-sent-card border border-sent-border rounded-lg p-4">
                <div className="text-sm font-bold text-white mb-3">持仓（{detail.positions.length}）</div>
                {detail.positions.length === 0 ? (
                  <div className="text-xs text-sent-dim">暂无持仓</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-sent-dim border-b border-sent-border/50">
                          <th className="text-left py-2">代码</th>
                          <th className="text-right py-2">数量</th>
                          <th className="text-right py-2">成本</th>
                          <th className="text-right py-2">现价</th>
                          <th className="text-right py-2">市值</th>
                          <th className="text-right py-2">浮盈亏</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.positions.map((p) => (
                          <tr key={p.id} className="border-b border-sent-border/30">
                            <td className="py-2 font-mono text-white">{p.ticker}</td>
                            <td className="py-2 text-right">{fmt(p.qty, 0)}</td>
                            <td className="py-2 text-right">{fmt(p.avg_cost)}</td>
                            <td className="py-2 text-right">{fmt(p.price)}</td>
                            <td className="py-2 text-right">{fmt(p.market_value)}</td>
                            <td className={`py-2 text-right ${p.pnl == null ? '' : p.pnl >= 0 ? 'text-sent-green' : 'text-sent-red'}`}>
                              {p.pnl == null ? '--' : `${p.pnl >= 0 ? '+' : ''}${fmt(p.pnl)}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* 成交记录 */}
              <div className="bg-sent-card border border-sent-border rounded-lg p-4">
                <div className="text-sm font-bold text-white mb-3">成交记录</div>
                {detail.trades.length === 0 ? (
                  <div className="text-xs text-sent-dim">暂无成交</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-xs text-sent-dim border-b border-sent-border/50">
                          <th className="text-left py-2">时间</th>
                          <th className="text-left py-2">代码</th>
                          <th className="text-left py-2">方向</th>
                          <th className="text-right py-2">价格</th>
                          <th className="text-right py-2">数量</th>
                          <th className="text-right py-2">金额</th>
                          <th className="text-right py-2">实现盈亏</th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.trades.map((t) => (
                          <tr key={t.id} className="border-b border-sent-border/30">
                            <td className="py-2 text-xs text-sent-dim">{t.trade_date}</td>
                            <td className="py-2 font-mono text-white">{t.ticker}</td>
                            <td className={`py-2 ${t.side === 'buy' ? 'text-sent-green' : 'text-sent-red'}`}>
                              {t.side === 'buy' ? '买入' : '卖出'}
                            </td>
                            <td className="py-2 text-right">{fmt(t.price)}</td>
                            <td className="py-2 text-right">{fmt(t.qty, 0)}</td>
                            <td className="py-2 text-right">{fmt(t.amount)}</td>
                            <td className={`py-2 text-right ${t.realized_pnl == null ? 'text-sent-dim' : t.realized_pnl >= 0 ? 'text-sent-green' : 'text-sent-red'}`}>
                              {t.realized_pnl == null ? '--' : `${t.realized_pnl >= 0 ? '+' : ''}${fmt(t.realized_pnl)}`}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
