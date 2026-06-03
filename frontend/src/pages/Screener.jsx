/**
 * Screener - 选股器（M3 完整版）
 * 流程：刷新因子库 → 多条件筛选 → 排名 → Top N 结果
 */
import { useEffect, useState } from 'react'
import { factors as factorsApi, backtest as backtestApi } from '../lib/api'

const FILTER_PRESETS = [
  { name: 'pe_ttm',       label: 'PE-TTM',         unit: '倍',  defaultMin: 0,  defaultMax: 30 },
  { name: 'pb',           label: 'PB',             unit: '倍',  defaultMin: 0,  defaultMax: 5 },
  { name: 'ps_ttm',       label: 'PS-TTM',         unit: '倍',  defaultMin: 0,  defaultMax: 10 },
  { name: 'roe',          label: 'ROE',            unit: '%',   defaultMin: 15, defaultMax: 100, isPct: true },
  { name: 'gross_margin', label: '毛利率',         unit: '%',   defaultMin: 30, defaultMax: 100, isPct: true },
  { name: 'market_cap',   label: '总市值',         unit: '亿',  defaultMin: 50, defaultMax: 5000 },
  { name: 'turnover_rate',label: '换手率',         unit: '%',   defaultMin: 0,  defaultMax: 20 },
]

const RANK_PRESETS = [
  { value: 'roe',           label: 'ROE（越大越好）' },
  { value: 'pe_ttm',        label: 'PE（越小越好）' },
  { value: 'pb',            label: 'PB（越小越好）' },
  { value: 'gross_margin',  label: '毛利率（越大越好）' },
  { value: 'market_cap',    label: '总市值（越大越好）' },
  { value: 'turnover_rate', label: '换手率（越大越好）' },
]

export default function Screener() {
  const [factors, setFactors] = useState([])
  const [stats, setStats] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [results, setResults] = useState([])
  const [resultMeta, setResultMeta] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [activeFilters, setActiveFilters] = useState({})  // {factor_name: {min, max}}
  const [rankBy, setRankBy] = useState('roe')
  const [topN, setTopN] = useState(20)
  const [runBacktestTicker, setRunBacktestTicker] = useState(null)
  const [btLoading, setBtLoading] = useState(false)

  const loadMeta = async () => {
    try {
      const [f, s] = await Promise.all([
        factorsApi.list(),
        factorsApi.universeStats(),
      ])
      setFactors(f.factors || [])
      setStats(s)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    loadMeta()
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    setError('')
    try {
      const r = await factorsApi.refresh()
      await loadMeta()
      setResultMeta({ message: r.message, inserted: r.inserted })
    } catch (e) {
      setError(e.message)
    } finally {
      setRefreshing(false)
    }
  }

  function toggleFilter(factorName) {
    setActiveFilters(prev => {
      const next = { ...prev }
      if (next[factorName]) delete next[factorName]
      else {
        const preset = FILTER_PRESETS.find(p => p.name === factorName)
        next[factorName] = { min: preset?.defaultMin, max: preset?.defaultMax }
      }
      return next
    })
  }

  function updateFilter(factorName, key, value) {
    setActiveFilters(prev => ({
      ...prev,
      [factorName]: { ...prev[factorName], [key]: value === '' ? null : Number(value) },
    }))
  }

  async function handleScreen() {
    setLoading(true)
    setError('')
    setResults([])
    setRunBacktestTicker(null)
    const filters = Object.entries(activeFilters).map(([factor, range]) => ({
      factor,
      min: range.min,
      max: range.max,
    })).filter(f => f.min !== null || f.max !== null)
    try {
      const r = await factorsApi.screen(filters, rankBy, topN)
      setResults(r.results || [])
      setResultMeta({
        trade_date: r.trade_date,
        total_candidates: r.total_candidates,
        error: r.error,
      })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function runBacktestForOne(ticker) {
    setBtLoading(true)
    setRunBacktestTicker(ticker)
    try {
      const r = await backtestApi.run({
        name: `${ticker} 选股器回测`,
        strategy: 'ma_cross',
        params: { fast: 5, slow: 20 },
        tickers: [ticker],
        start_date: '2024-01-01',
        end_date: '2024-12-31',
        initial_capital: 1000000,
      })
      alert(`回测已提交！ID: ${r.backtest_id}\n\n前往"回测"页面查看结果。`)
    } catch (e) {
      alert('提交失败: ' + e.message)
    } finally {
      setBtLoading(false)
      setRunBacktestTicker(null)
    }
  }

  return (
    <div className="space-y-4">
      {/* 顶部状态条 */}
      <div className="bg-sent-card border border-sent-border rounded-lg p-4 flex flex-wrap items-center gap-4">
        <div>
          <h2 className="text-lg font-bold text-white">🔍 选股器</h2>
          <p className="text-xs text-sent-dim mt-1">
            {stats ? (
              <>
                Universe = <span className="text-white font-mono">{stats.universe_size}</span> 只 ·
                因子 = <span className="text-white font-mono">{stats.factor_count}</span> 个 ·
                数据源 = <span className="text-sent-yellow font-mono">{stats.source}</span> ·
                最近更新 = <span className="text-white font-mono">{stats.latest_date || '—'}</span>
              </>
            ) : '加载中...'}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="ml-auto bg-sent-blue text-sent-bg px-4 py-2 rounded text-sm font-bold hover:opacity-80 disabled:opacity-50"
        >
          {refreshing ? '刷新中...' : '🔄 刷新因子库'}
        </button>
      </div>

      {error && <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-3 text-sm">⚠️ {error}</div>}

      {/* 条件筛选 */}
      <div className="bg-sent-card border border-sent-border rounded-lg p-4">
        <h3 className="text-sm font-bold text-sent-blue mb-3">📋 筛选条件（点击添加）</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {FILTER_PRESETS.map(p => {
            const active = !!activeFilters[p.name]
            return (
              <button
                key={p.name}
                onClick={() => toggleFilter(p.name)}
                className={`px-3 py-1 rounded text-xs font-mono ${
                  active ? 'bg-sent-yellow/20 text-sent-yellow border border-sent-yellow/40' : 'bg-sent-bg border border-sent-border text-sent-dim hover:text-white'
                }`}
              >
                {p.label}
              </button>
            )
          })}
        </div>

        {/* 选中的条件范围编辑 */}
        {Object.keys(activeFilters).length > 0 && (
          <div className="space-y-2 mb-4 p-3 bg-sent-bg border border-sent-border rounded">
            {Object.entries(activeFilters).map(([factor, range]) => {
              const preset = FILTER_PRESETS.find(p => p.name === factor)
              return (
                <div key={factor} className="flex items-center gap-2 text-sm">
                  <span className="font-mono text-white w-32">{preset?.label || factor}</span>
                  <input
                    type="number"
                    placeholder="最小"
                    value={range.min ?? ''}
                    onChange={e => updateFilter(factor, 'min', e.target.value)}
                    className="w-24 bg-sent-card border border-sent-border rounded px-2 py-1 text-sm font-mono"
                  />
                  <span className="text-sent-dim">~</span>
                  <input
                    type="number"
                    placeholder="最大"
                    value={range.max ?? ''}
                    onChange={e => updateFilter(factor, 'max', e.target.value)}
                    className="w-24 bg-sent-card border border-sent-border rounded px-2 py-1 text-sm font-mono"
                  />
                  <span className="text-sent-dim text-xs">{preset?.unit || ''}</span>
                  <button
                    onClick={() => toggleFilter(factor)}
                    className="ml-auto text-sent-red text-xs hover:opacity-80"
                  >
                    移除
                  </button>
                </div>
              )
            })}
          </div>
        )}

        {/* 排名 + Top N */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="text-sm text-sent-dim">排名方式：</span>
          <select
            value={rankBy}
            onChange={e => setRankBy(e.target.value)}
            className="bg-sent-bg border border-sent-border rounded px-3 py-1 text-sm"
          >
            {RANK_PRESETS.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <span className="text-sm text-sent-dim ml-4">返回 Top</span>
          <input
            type="number"
            value={topN}
            onChange={e => setTopN(Number(e.target.value) || 20)}
            min={1}
            max={500}
            className="w-20 bg-sent-bg border border-sent-border rounded px-3 py-1 text-sm font-mono"
          />
          <button
            onClick={handleScreen}
            disabled={loading}
            className="ml-auto bg-sent-green text-sent-bg px-6 py-2 rounded text-sm font-bold hover:opacity-80 disabled:opacity-50"
          >
            {loading ? '选股中...' : '▶ 执 行 选 股'}
          </button>
        </div>
      </div>

      {/* 结果 */}
      {resultMeta && (
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-sm text-sent-dim mb-3">
            {resultMeta.error ? (
              <span className="text-sent-red">⚠️ {resultMeta.error}</span>
            ) : (
              <>
                交易日 <span className="text-white font-mono">{resultMeta.trade_date}</span> ·
                命中 <span className="text-white font-mono">{resultMeta.total_candidates}</span> 只 ·
                显示 <span className="text-white font-mono">{results.length}</span> 只
                {resultMeta.message && <span className="ml-3 text-sent-yellow">· {resultMeta.message}</span>}
              </>
            )}
          </div>

          {results.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-sent-dim">
                  <tr className="border-b border-sent-border">
                    <th className="text-left p-2">#</th>
                    <th className="text-left p-2">代码</th>
                    <th className="text-right p-2">PE</th>
                    <th className="text-right p-2">PB</th>
                    <th className="text-right p-2">PS</th>
                    <th className="text-right p-2">ROE</th>
                    <th className="text-right p-2">毛利率</th>
                    <th className="text-right p-2">市值(亿)</th>
                    <th className="text-right p-2">换手率</th>
                    <th className="text-left p-2">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map(r => (
                    <tr key={r.ticker} className="border-b border-sent-border/30 hover:bg-sent-bg/50">
                      <td className="p-2 text-sent-yellow font-bold">{r.rank}</td>
                      <td className="p-2 font-mono text-white">{r.ticker}</td>
                      <td className="p-2 text-right font-mono">{fmt(r.pe_ttm, 2)}</td>
                      <td className="p-2 text-right font-mono">{fmt(r.pb, 2)}</td>
                      <td className="p-2 text-right font-mono">{fmt(r.ps_ttm, 2)}</td>
                      <td className={`p-2 text-right font-mono ${r.roe >= 0.15 ? 'text-sent-green' : 'text-sent-dim'}`}>
                        {fmt(r.roe * 100, 2)}%
                      </td>
                      <td className="p-2 text-right font-mono">{fmt(r.gross_margin * 100, 1)}%</td>
                      <td className="p-2 text-right font-mono">{fmt(r.market_cap, 0)}</td>
                      <td className="p-2 text-right font-mono">{fmt(r.turnover_rate, 2)}%</td>
                      <td className="p-2">
                        <button
                          onClick={() => runBacktestForOne(r.ticker)}
                          disabled={btLoading}
                          className="text-xs text-sent-blue hover:opacity-80"
                        >
                          {btLoading && runBacktestTicker === r.ticker ? '提交中...' : '⚡ 回测'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 因子说明 */}
      <details className="bg-sent-card border border-sent-border rounded-lg p-4 text-sm">
        <summary className="cursor-pointer text-sent-blue font-bold">📚 因子说明（{factors.length} 个）</summary>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {factors.map(f => (
            <div key={f.name} className="bg-sent-bg border border-sent-border rounded p-2 text-xs">
              <div className="font-mono text-white">{f.name}</div>
              <div className="text-sent-dim mt-0.5">
                {f.category} · {f.direction === 'asc' ? '↑ 越大越好' : '↓ 越小越好'}
              </div>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

function fmt(v, decimals = 2) {
  if (v == null || isNaN(v)) return '—'
  return Number(v).toFixed(decimals)
}
