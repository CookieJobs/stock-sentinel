/**
 * Portfolio - 组合管理（M5 完整版）
 * 流程：创建组合 → 加持仓 → 设权重 → 估值 → 再平衡 → 跑回测
 */
import { useEffect, useState } from 'react'
import { portfolios as portfolioApi } from '../lib/api'

const BENCHMARKS = [
  { value: '000300.SH', label: '沪深 300' },
  { value: '000905.SH', label: '中证 500' },
  { value: '000016.SH', label: '上证 50' },
  { value: '399006.SZ', label: '创业板指' },
  { value: 'HSI',       label: '恒生指数' },
  { value: 'SPX',       label: '标普 500' },
]

const REBALANCE_FREQS = [
  { value: 'monthly',   label: '每月' },
  { value: 'quarterly', label: '每季' },
  { value: 'none',      label: '不调仓' },
]

export default function Portfolio() {
  const [list, setList] = useState([])
  const [expanded, setExpanded] = useState(null)
  const [name, setName] = useState('')
  const [benchmark, setBenchmark] = useState('000300.SH')
  const [rebalanceFreq, setRebalanceFreq] = useState('monthly')
  const [error, setError] = useState('')
  const [valuationCache, setValuationCache] = useState({})  // {pid: {data, ts}}

  function load() {
    portfolioApi.list().then(d => setList(d.portfolios || [])).catch(e => setError(e.message))
  }
  useEffect(() => { load() }, [])

  async function handleCreate(e) {
    e.preventDefault()
    if (!name.trim()) return
    try {
      await portfolioApi.create({ name, benchmark, rebalance_freq: rebalanceFreq })
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

  async function loadValuation(id) {
    try {
      const data = await portfolioApi.valuation(id)
      setValuationCache(prev => ({ ...prev, [id]: { data, ts: Date.now() } }))
    } catch (e) {
      setError(e.message)
    }
  }

  function toggleExpand(id) {
    setExpanded(prev => prev === id ? null : id)
    if (expanded !== id && !valuationCache[id]) {
      loadValuation(id)
    }
  }

  return (
    <div className="space-y-4">
      {/* 创建组合 */}
      <form onSubmit={handleCreate} className="bg-sent-card border border-sent-border rounded-lg p-4">
        <h2 className="text-lg font-bold text-white mb-3">💼 组合管理</h2>
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="组合名（如：核心持仓）"
            className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm flex-1 min-w-[200px] focus:outline-none focus:border-sent-blue"
          />
          <select
            value={benchmark}
            onChange={e => setBenchmark(e.target.value)}
            className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
          >
            {BENCHMARKS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
          </select>
          <select
            value={rebalanceFreq}
            onChange={e => setRebalanceFreq(e.target.value)}
            className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
          >
            {REBALANCE_FREQS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
          <button type="submit" className="bg-sent-blue text-sent-bg px-4 py-1.5 rounded text-sm font-bold hover:opacity-80">
            创 建
          </button>
        </div>
      </form>

      {error && <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-3 text-sm">⚠️ {error}</div>}

      {/* 列表 */}
      <div className="space-y-2">
        {list.length === 0 && (
          <div className="bg-sent-card border border-sent-border rounded-lg text-sent-dim text-sm text-center py-12">
            还没有组合，创建第一个吧 👆
          </div>
        )}
        {list.map(p => (
          <PortfolioCard
            key={p.id}
            portfolio={p}
            expanded={expanded === p.id}
            onToggle={() => toggleExpand(p.id)}
            onDelete={() => handleDelete(p.id)}
            onRefresh={() => loadValuation(p.id)}
            valuation={valuationCache[p.id]?.data}
            onError={setError}
          />
        ))}
      </div>
    </div>
  )
}

function PortfolioCard({ portfolio, expanded, onToggle, onDelete, onRefresh, valuation, onError }) {
  const [holdings, setHoldings] = useState(portfolio.holdings || [])
  const [newTicker, setNewTicker] = useState('')
  const [newWeight, setNewWeight] = useState('0.1')
  const [rebalanceData, setRebalanceData] = useState(null)
  const [rebalanceThreshold, setRebalanceThreshold] = useState(0.05)
  const [rebalanceCapital, setRebalanceCapital] = useState(1000000)
  const [btStart, setBtStart] = useState('2024-01-01')
  const [btEnd, setBtEnd] = useState('2024-12-31')

  useEffect(() => {
    setHoldings(portfolio.holdings || [])
  }, [portfolio])

  // 总权重
  const totalWeight = holdings.reduce((s, h) => s + (h.weight || 0), 0)
  const weightOk = Math.abs(totalWeight - 1) < 0.001

  async function handleAddHolding() {
    if (!newTicker.trim()) return
    try {
      await portfolioApi.addHolding(portfolio.id, {
        ticker: newTicker.trim().toUpperCase(),
        market: 'CN',
        weight: parseFloat(newWeight) || 0,
      })
      setNewTicker('')
      setNewWeight('0.1')
      onRefresh()
    } catch (e) {
      onError(e.message)
    }
  }

  async function handleUpdateWeight(ticker, newW) {
    try {
      await portfolioApi.updateHolding(portfolio.id, ticker, { weight: parseFloat(newW) || 0 })
      onRefresh()
    } catch (e) {
      onError(e.message)
    }
  }

  async function handleRemove(ticker) {
    try {
      await portfolioApi.removeHolding(portfolio.id, ticker)
      onRefresh()
    } catch (e) {
      onError(e.message)
    }
  }

  async function loadRebalance() {
    try {
      const d = await portfolioApi.rebalance(portfolio.id, rebalanceThreshold, rebalanceCapital)
      setRebalanceData(d)
    } catch (e) {
      onError(e.message)
    }
  }

  async function runBacktest() {
    try {
      const r = await portfolioApi.runBacktest(portfolio.id, {
        start_date: btStart,
        end_date: btEnd,
        initial_capital: rebalanceCapital,
      })
      alert(`组合回测已提交！\n回测 ID: ${r.backtest_id}\n\n前往"回测"页面查看结果。`)
    } catch (e) {
      onError(e.message)
    }
  }

  return (
    <div className="bg-sent-card border border-sent-border rounded-lg">
      {/* 头部 */}
      <div className="p-4 flex items-center gap-3">
        <button onClick={onToggle} className="text-sent-blue font-mono w-4">
          {expanded ? '▼' : '▶'}
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-white font-bold">#{portfolio.id} {portfolio.name}</span>
            {holdings.length > 0 && (
              <span className="text-xs text-sent-dim">
                {holdings.length} 只持仓 ·
                <span className={weightOk ? 'text-sent-green' : 'text-sent-yellow'}>
                  {' '}总权重 {(totalWeight * 100).toFixed(1)}%
                </span>
              </span>
            )}
          </div>
          <div className="text-xs text-sent-dim mt-1">
            基准：{portfolio.benchmark} · 调仓：{portfolio.rebalance_freq} · 创建于 {portfolio.created_at}
          </div>
        </div>
        <button
          onClick={onDelete}
          className="text-sent-red text-sm hover:opacity-80"
        >
          删除
        </button>
      </div>

      {expanded && (
        <div className="border-t border-sent-border p-4 space-y-4">
          {/* 持仓编辑 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold text-sent-blue">📋 持仓</h4>
              {!weightOk && (
                <span className="text-xs text-sent-yellow">⚠️ 权重总和应为 100%</span>
              )}
            </div>

            <div className="space-y-1 mb-3">
              {holdings.length === 0 && (
                <div className="text-sent-dim text-sm text-center py-4">还没有持仓，添加第一个 ↓</div>
              )}
              {holdings.map(h => (
                <div key={h.ticker} className="flex items-center gap-2 bg-sent-bg border border-sent-border rounded px-3 py-2 text-sm">
                  <span className="font-mono text-white w-24">{h.ticker}</span>
                  <span className="text-sent-dim text-xs">{h.market}</span>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={h.weight}
                    onChange={e => handleUpdateWeight(h.ticker, e.target.value)}
                    className="ml-auto w-20 bg-sent-card border border-sent-border rounded px-2 py-0.5 text-sm font-mono text-right"
                  />
                  <span className="text-sent-dim text-xs w-4">%</span>
                  <button
                    onClick={() => handleRemove(h.ticker)}
                    className="text-sent-red text-xs hover:opacity-80"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>

            <div className="flex gap-2">
              <input
                value={newTicker}
                onChange={e => setNewTicker(e.target.value)}
                placeholder="代码"
                className="bg-sent-bg border border-sent-border rounded px-2 py-1 text-sm w-24 font-mono"
              />
              <input
                type="number"
                step="0.01"
                value={newWeight}
                onChange={e => setNewWeight(e.target.value)}
                placeholder="权重"
                className="bg-sent-bg border border-sent-border rounded px-2 py-1 text-sm w-20 font-mono"
              />
              <button
                onClick={handleAddHolding}
                className="bg-sent-blue text-sent-bg px-3 py-1 rounded text-sm font-bold hover:opacity-80"
              >
                + 添加
              </button>
              <button
                onClick={() => { if (newWeight) { /* TODO: normalize */ } }}
                className="text-xs text-sent-dim hover:text-white"
                title="等分剩余权重到所有持仓"
              >
                ⚖️ 等分
              </button>
            </div>
          </div>

          {/* 估值 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold text-sent-blue">💰 估值（实时价 × 目标权重）</h4>
              <button
                onClick={onRefresh}
                className="text-xs text-sent-dim hover:text-white"
              >
                🔄 刷新
              </button>
            </div>
            {!valuation ? (
              <div className="text-sent-dim text-sm">加载中...</div>
            ) : valuation.error ? (
              <div className="text-sent-red text-sm">{valuation.error}</div>
            ) : (
              <div className="bg-sent-bg border border-sent-border rounded p-3">
                <div className="text-2xl font-mono text-white mb-2">
                  ¥{valuation.total_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </div>
                <div className="text-xs text-sent-dim mb-2">模拟总市值（基于当前价）</div>
                <div className="space-y-1">
                  {valuation.holdings.map(h => (
                    <div key={h.ticker} className="flex items-center text-xs">
                      <span className="font-mono text-white w-20">{h.ticker}</span>
                      <span className="text-sent-dim w-16">价 {h.price?.toFixed(2) || '—'}</span>
                      <span className="text-sent-dim w-20">值 {h.value?.toFixed(0)}</span>
                      <div className="flex-1 bg-sent-card rounded-full h-2 ml-2 overflow-hidden">
                        <div
                          className="h-full bg-sent-blue"
                          style={{ width: `${(h.pct_of_total || 0) * 100}%` }}
                        />
                      </div>
                      <span className="text-white font-mono w-14 text-right">
                        {(h.pct_of_total * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 再平衡 */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-bold text-sent-blue">⚖️ 再平衡建议</h4>
              <button
                onClick={loadRebalance}
                className="text-xs text-sent-dim hover:text-white"
              >
                计算
              </button>
            </div>
            <div className="flex items-center gap-2 text-xs mb-2">
              <label>阈值 <input type="number" step="0.01" value={rebalanceThreshold} onChange={e => setRebalanceThreshold(parseFloat(e.target.value) || 0.05)} className="w-16 bg-sent-bg border border-sent-border rounded px-2 py-0.5 text-xs font-mono" /></label>
              <label>资金 <input type="number" value={rebalanceCapital} onChange={e => setRebalanceCapital(parseFloat(e.target.value) || 0)} className="w-24 bg-sent-bg border border-sent-border rounded px-2 py-0.5 text-xs font-mono" /></label>
            </div>
            {rebalanceData && (
              <div className="space-y-1">
                {rebalanceData.actions.length === 0 ? (
                  <div className="text-sent-dim text-sm">✅ 无需再平衡（所有偏差 &lt; 阈值）</div>
                ) : (
                  rebalanceData.actions.map((a, i) => (
                    <div key={i} className={`flex items-center gap-2 text-xs px-2 py-1 rounded ${
                      a.action === 'buy' ? 'bg-sent-green/10 border border-sent-green/30' : 'bg-sent-red/10 border border-sent-red/30'
                    }`}>
                      <span className={a.action === 'buy' ? 'text-sent-green' : 'text-sent-red'}>
                        {a.action === 'buy' ? '买' : '卖'}
                      </span>
                      <span className="font-mono text-white w-20">{a.ticker}</span>
                      <span className="font-mono">¥{Math.abs(a.delta_value).toLocaleString()}</span>
                      <span className="text-sent-dim text-xs ml-auto">{a.reason}</span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* 组合回测 */}
          <div>
            <h4 className="text-sm font-bold text-sent-blue mb-2">📈 组合回测</h4>
            <div className="flex items-center gap-2 text-xs">
              <label>起 <input type="date" value={btStart} onChange={e => setBtStart(e.target.value)} className="bg-sent-bg border border-sent-border rounded px-2 py-0.5 text-xs" /></label>
              <label>止 <input type="date" value={btEnd} onChange={e => setBtEnd(e.target.value)} className="bg-sent-bg border border-sent-border rounded px-2 py-0.5 text-xs" /></label>
              <button
                onClick={runBacktest}
                className="ml-auto bg-sent-green text-sent-bg px-3 py-1 rounded text-sm font-bold hover:opacity-80"
              >
                ▶ 跑回测（按持仓权重）
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
