/**
 * Screener - 选股器（v1.1 AI 策略版）
 * 双模式：
 *  - ✨ AI 策略选股（默认，新手友好）：内置策略卡一键选股 + 自然语言 AI 生成策略
 *  - ⚙️ 手动高级模式：保留 M3 原始多条件筛选
 */
import { useEffect, useState } from 'react'
import { factors as factorsApi, screener as screenerApi, backtest as backtestApi } from '../lib/api'

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

// 策略卡条件 chip 的中文名（含 daily_metrics 附加字段）
const FACTOR_LABELS = {
  pe_ttm: 'PE', pb: 'PB', ps_ttm: 'PS', peg: 'PEG',
  roe: 'ROE', roa: 'ROA',
  revenue_yoy: '营收增速', profit_yoy: '利润增速',
  gross_margin: '毛利率', net_margin: '净利率', debt_ratio: '负债率',
  turnover_rate: '换手率', market_cap: '市值',
  momentum_20d: '20日动量', momentum_60d: '60日动量',
  hist_vol_20d: '波动率', atr_pct: '波幅', free_cash_flow: '现金流',
}

// 百分比存储的因子（chip 显示 %）
const PCT_FACTORS = new Set(['roe', 'roa', 'gross_margin', 'net_margin', 'debt_ratio',
  'turnover_rate', 'revenue_yoy', 'profit_yoy'])

function chipFor(f) {
  const label = FACTOR_LABELS[f.factor] || f.factor
  const unit = PCT_FACTORS.has(f.factor) ? '%' : (f.factor === 'market_cap' ? '亿' : '')
  const parts = []
  if (f.min != null) parts.push(`≥ ${f.min}${unit}`)
  if (f.max != null) parts.push(`≤ ${f.max}${unit}`)
  return `${label} ${parts.join(' ')}`
}

// ROE/毛利率等百分比因子：兼容小数（0.15）与百分比原值（15）两种存储
function normPct(v) {
  if (v == null || isNaN(v)) return null
  return Number(v) > 1 ? Number(v) : Number(v) * 100
}

export default function Screener() {
  const [factors, setFactors] = useState([])
  const [stats, setStats] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [mode, setMode] = useState('ai')          // 'ai' | 'manual'
  const [strategies, setStrategies] = useState([])
  const [llmConfigured, setLlmConfigured] = useState(false)
  const [aiPrompt, setAiPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [expanded, setExpanded] = useState(null)   // 展开详情策略 id
  const [runningStrategy, setRunningStrategy] = useState(null)
  const [results, setResults] = useState([])
  const [resultMeta, setResultMeta] = useState(null)
  const [skippedFactors, setSkippedFactors] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // 手动高级模式
  const [activeFilters, setActiveFilters] = useState({})
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
    screenerApi.strategies()
      .then(r => {
        setStrategies(r.strategies || [])
        setLlmConfigured(!!r.llm_configured)
      })
      .catch(e => setError(e.message))
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

  // ── AI 策略 ─────────────────────────────────────
  async function handleGenerate() {
    if (!aiPrompt.trim()) return
    setGenerating(true)
    setError('')
    try {
      const r = await screenerApi.generate(aiPrompt.trim())
      const s = r.strategy
      setStrategies(prev => [s, ...prev])
      setExpanded(s.id)
      setAiPrompt('')
    } catch (e) {
      setError(e.message)
    } finally {
      setGenerating(false)
    }
  }

  async function runStrategy(strategy) {
    setLoading(true)
    setError('')
    setResults([])
    setRunBacktestTicker(null)
    setRunningStrategy(strategy.id)
    try {
      const r = await screenerApi.screen(
        strategy.llm_generated ? undefined : strategy.id,
        strategy.llm_generated ? strategy : undefined,
      )
      setResults(r.results || [])
      setSkippedFactors(r.skipped_factors || [])
      setResultMeta({ trade_date: r.trade_date, total_candidates: r.total_candidates, error: r.error })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setRunningStrategy(null)
    }
  }

  // ── 手动模式（M3 原始功能） ─────────────────────
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
    setSkippedFactors([])
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

      {/* 模式切换 */}
      <div className="flex gap-2">
        <button
          onClick={() => setMode('ai')}
          className={`px-4 py-2 rounded text-sm font-bold border transition-colors ${
            mode === 'ai'
              ? 'bg-sent-blue text-sent-bg border-sent-blue'
              : 'bg-sent-card border-sent-border text-sent-dim hover:text-white'
          }`}
        >
          ✨ AI 策略选股（推荐新手）
        </button>
        <button
          onClick={() => setMode('manual')}
          className={`px-4 py-2 rounded text-sm font-bold border transition-colors ${
            mode === 'manual'
              ? 'bg-sent-blue text-sent-bg border-sent-blue'
              : 'bg-sent-card border-sent-border text-sent-dim hover:text-white'
          }`}
        >
          ⚙️ 手动高级模式
        </button>
      </div>

      {error && <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-3 text-sm">⚠️ {error}</div>}

      {/* ── AI 策略模式 ─────────────────────────── */}
      {mode === 'ai' && (
        <>
          {/* 自然语言生成 */}
          <div className="bg-sent-card border border-sent-border rounded-lg p-4">
            <h3 className="text-sm font-bold text-sent-blue mb-1">🤖 用一句话描述你想要的股票</h3>
            <p className="text-xs text-sent-dim mb-3">
              比如「低估值的高分红股」「稳定赚钱的大公司」。AI 会把它翻译成一条选股策略，不懂指标也能用。
            </p>
            <div className="flex gap-2">
              <input
                value={aiPrompt}
                onChange={e => setAiPrompt(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                placeholder={llmConfigured ? '例如：我想找估值便宜、分红高的股票' : 'AI 生成需要配置 LLM_API_KEY，可直接用下面的内置策略'}
                className="flex-1 bg-sent-bg border border-sent-border rounded px-3 py-2 text-sm placeholder:text-sent-dim/60"
              />
              <button
                onClick={handleGenerate}
                disabled={generating || !aiPrompt.trim()}
                className="bg-sent-purple text-white px-4 py-2 rounded text-sm font-bold hover:opacity-80 disabled:opacity-50"
              >
                {generating ? '生成中...' : '🤖 AI 生成策略'}
              </button>
            </div>
          </div>

          {/* 策略卡 */}
          <div className="bg-sent-card border border-sent-border rounded-lg p-4">
            <h3 className="text-sm font-bold text-sent-blue mb-1">🎯 选择一个策略，一键选股</h3>
            <p className="text-xs text-sent-dim mb-3">
              每个策略都帮你把「该看什么指标」翻译成了人话，点一下直接出结果。
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {strategies.map(s => (
                <div key={s.id} className="bg-sent-bg border border-sent-border rounded-lg p-4 flex flex-col gap-2 hover:border-sent-blue/50 transition-colors">
                  <div className="flex items-start justify-between">
                    <span className="text-2xl leading-none">{s.emoji || '📊'}</span>
                    {s.llm_generated && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-400/30">✨ AI 生成</span>
                    )}
                  </div>
                  <div className="font-bold text-white">{s.name}</div>
                  <div className="text-xs text-sent-dim leading-relaxed">{s.tagline}</div>
                  <div className="flex flex-wrap gap-1.5">
                    {s.filters.map(f => (
                      <span key={f.factor} className="px-2 py-0.5 rounded bg-sent-card border border-sent-border text-[11px] font-mono text-sent-yellow">
                        {chipFor(f)}
                      </span>
                    ))}
                  </div>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-sent-dim">
                    <span>👤 {s.audience}</span>
                    <span>⚠️ 风险：{s.risk_level}</span>
                  </div>
                  <div className="mt-auto pt-2 flex gap-2">
                    <button
                      onClick={() => runStrategy(s)}
                      disabled={loading}
                      className="flex-1 bg-sent-green text-sent-bg px-3 py-2 rounded text-xs font-bold hover:opacity-80 disabled:opacity-50"
                    >
                      {loading && runningStrategy === s.id ? '选股中...' : '▶ 用这个策略选股'}
                    </button>
                    <button
                      onClick={() => setExpanded(expanded === s.id ? null : s.id)}
                      className="bg-sent-card border border-sent-border text-sent-dim hover:text-white px-3 py-2 rounded text-xs"
                    >
                      {expanded === s.id ? '收起' : '📖 说明'}
                    </button>
                  </div>
                  {expanded === s.id && (
                    <div className="mt-1 pt-3 border-t border-sent-border text-xs space-y-2">
                      <div className="text-sent-dim leading-relaxed">💡 <span className="text-white">{s.name}</span> 为什么这样选：{s.why}</div>
                      {s.filters.map(f => (
                        <div key={f.factor} className="bg-sent-card/60 rounded p-2">
                          <div className="font-mono text-sent-yellow">{chipFor(f)}</div>
                          <div className="text-sent-dim mt-0.5 leading-relaxed">{s.explains?.[f.factor]}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* ── 手动高级模式（M3 原始） ───────────────── */}
      {mode === 'manual' && (
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
      )}

      {/* 结果 */}
      {resultMeta && (
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-sm text-sent-dim mb-3 space-y-1">
            <div>
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
            {skippedFactors.length > 0 && (
              <div className="text-sent-yellow text-xs">
                ⚠️ 以下条件暂无数据，已自动跳过（刷新因子库后自动生效）：
                <span className="font-mono">{skippedFactors.join('、')}</span>
              </div>
            )}
          </div>

          {results.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-sent-dim">
                  <tr className="border-b border-sent-border">
                    <th className="text-left p-2">#</th>
                    <th className="text-left p-2">代码</th>
                    <th className="text-left p-2">名称</th>
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
                  {results.map(r => {
                    const roePct = normPct(r.roe)
                    return (
                      <tr key={r.ticker} className="border-b border-sent-border/30 hover:bg-sent-bg/50">
                        <td className="p-2 text-sent-yellow font-bold">{r.rank}</td>
                        <td className="p-2 font-mono text-white">{r.ticker}</td>
                        <td className="p-2 text-sent-dim">{r.name || '—'}</td>
                        <td className="p-2 text-right font-mono">{fmt(r.pe_ttm, 2)}</td>
                        <td className="p-2 text-right font-mono">{fmt(r.pb, 2)}</td>
                        <td className="p-2 text-right font-mono">{fmt(r.ps_ttm, 2)}</td>
                        <td className={`p-2 text-right font-mono ${roePct != null && roePct >= 12 ? 'text-sent-green' : 'text-sent-dim'}`}>
                          {roePct != null ? `${roePct.toFixed(2)}%` : '—'}
                        </td>
                        <td className="p-2 text-right font-mono">
                          {normPct(r.gross_margin) != null ? `${normPct(r.gross_margin).toFixed(1)}%` : '—'}
                        </td>
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
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 因子说明（白话版） */}
      <details className="bg-sent-card border border-sent-border rounded-lg p-4 text-sm">
        <summary className="cursor-pointer text-sent-blue font-bold">
          📚 指标小词典（{factors.length} 个，给小白看的大白话）
        </summary>
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {factors.map(f => (
            <div key={f.name} className="bg-sent-bg border border-sent-border rounded p-2 text-xs">
              <div className="font-mono text-white">{f.name}
                {f.unit && <span className="text-sent-dim ml-1">（单位：{f.unit}）</span>}
              </div>
              <div className="text-sent-dim mt-0.5">
                {f.category} · {f.direction === 'asc' ? '↑ 越大越好' : '↓ 越小越好'}
              </div>
              <div className="text-sent-dim mt-1 leading-relaxed">{f.description_zh}</div>
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
