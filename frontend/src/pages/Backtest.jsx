/**
 * Backtest - 回测工作流（M4 完整版）
 * 流程：选策略 → 配参数 → 输标的 → 提交 → 轮询进度 → 看结果
 */
import { useEffect, useState } from 'react'
import { backtest as backtestApi, search } from '../lib/api'
import { MODE_DEFAULTS, addStock, buildRunPayload, validateSelection } from '../lib/backtest-flow'

const STRATEGY_DEFAULTS = {
  ma_cross:     { fast: 5, slow: 20 },
  equal_weight: {},
  factor_rank:  { factor: 'momentum_20d', top_n: 10 },
}

const STRATEGY_DESCRIPTIONS = {
  ma_cross:     '单标的：close > MA_fast > MA_slow 时满仓买入，否则空仓',
  equal_weight: '所有标的等权持有，按 rebalance_freq 调仓',
  factor_rank:  '取因子（momentum_20d/volatility_20d）排名 Top N 等权',
}

const REBALANCE_OPTIONS = [
  { value: 'monthly', label: '每月' },
  { value: 'weekly',  label: '每周' },
  { value: 'daily',   label: '每日' },
  { value: 'none',    label: '不调仓' },
]

const BENCHMARK_OPTIONS = [
  { value: '000300.SH', label: '沪深 300' },
  { value: '000905.SH', label: '中证 500' },
  { value: '000016.SH', label: '上证 50' },
  { value: '399006.SZ', label: '创业板指' },
  { value: 'HSI',       label: '恒生指数' },
  { value: 'SPX',       label: '标普 500' },
]

const MODE_OPTIONS = [
  {
    value: 'single',
    title: '跟随趋势',
    description: '回测一只股票，在短期趋势强于长期趋势时持有。',
  },
  {
    value: 'portfolio',
    title: '等权持有',
    description: '把多只股票平均分配，每月恢复相同仓位。',
  },
]

const MARKET_LABELS = { CN: 'A股', HK: '港股', US: '美股' }
const MODE_LABELS = { single: '趋势方式', portfolio: '等权持有', custom: '自定义策略' }

function formatDate(date) {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

function defaultDateRange() {
  const end = new Date()
  const start = new Date(end)
  start.setFullYear(start.getFullYear() - 1)
  return { start_date: formatDate(start), end_date: formatDate(end) }
}

function detectMarket(ticker) {
  const normalized = ticker.trim().toUpperCase()
  if (/^\d{6}$/.test(normalized)) return 'CN'
  if (/^\d{1,5}$/.test(normalized) || normalized.endsWith('.HK')) return 'HK'
  return 'US'
}

function displayStock(stock) {
  return stock.name || stock.ticker
}

export default function Backtest() {
  const [strategies, setStrategies] = useState([])
  const [templates, setTemplates] = useState([])
  const [history, setHistory] = useState([])
  const [mode, setMode] = useState('single')
  const [selectedStocks, setSelectedStocks] = useState([])
  const [stockQuery, setStockQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [searching, setSearching] = useState(false)
  const dates = defaultDateRange()
  const [form, setForm] = useState({
    name: '我的回测',
    strategy: 'ma_cross',
    params: { fast: 5, slow: 20 },
    ...dates,
    initial_capital: 1000000,
    commission: 0.0003,
    slippage: 0.001,
    benchmark: '000300.SH',
    rebalance_freq: 'monthly',
  })
  const [submitting, setSubmitting] = useState(false)
  const [runningId, setRunningId] = useState(null)
  const [runningData, setRunningData] = useState(null)
  const [resultData, setResultData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    backtestApi.strategies().then(d => setStrategies(d.strategies || []))
    backtestApi.templates().then(d => setTemplates(d.templates || [])).catch(() => {})
    loadHistory()
  }, [])

  useEffect(() => {
    const query = stockQuery.trim()
    if (!query) {
      setSuggestions([])
      setShowSuggestions(false)
      return
    }
    const timer = setTimeout(() => {
      setSearching(true)
      search.stocks(query, { limit: 8 })
        .then(data => {
          setSuggestions(data.results || [])
          setShowSuggestions(true)
        })
        .catch(() => {
          setSuggestions([])
          setShowSuggestions(false)
        })
        .finally(() => setSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [stockQuery])

  function handleTemplate(t) {
    setForm(prev => ({
      ...prev,
      name: `模板：${t.name}`,
      strategy: t.strategy,
      params: { ...t.params },
      rebalance_freq: t.rebalance_freq || prev.rebalance_freq,
    }))
    setSelectedStocks((t.tickers || []).map(ticker => ({ ticker, name: '', market: 'CN' })))
    setMode(t.strategy === 'ma_cross' ? 'single' : 'custom')
    setError('')
  }

  function loadHistory() {
    backtestApi.listRecent(10).then(d => setHistory(d.backtests || [])).catch(() => {})
  }

  function updateForm(key, value) {
    setForm(prev => ({ ...prev, [key]: value }))
  }

  function updateParam(key, value) {
    setForm(prev => ({ ...prev, params: { ...prev.params, [key]: value } }))
  }

  function handleStrategyChange(s) {
    setMode('custom')
    setForm(prev => ({
      ...prev,
      strategy: s,
      params: { ...STRATEGY_DEFAULTS[s] },
    }))
  }

  function chooseMode(nextMode) {
    const defaults = MODE_DEFAULTS[nextMode]
    setMode(nextMode)
    setForm(prev => ({ ...prev, ...defaults, params: { ...defaults.params } }))
    setError('')
  }

  function selectStock(stock) {
    const normalized = {
      ticker: stock.ticker.trim().toUpperCase(),
      name: stock.name || '',
      market: stock.market || detectMarket(stock.ticker),
    }
    if (selectedStocks[0] && selectedStocks[0].market !== normalized.market) {
      setError('同一次回测请选择同一市场的股票，如需比较不同市场请分别运行回测')
      return
    }
    setSelectedStocks(prev => addStock(prev, normalized))
    setStockQuery('')
    setSuggestions([])
    setShowSuggestions(false)
    setError('')
  }

  function handleSearchKeyDown(e) {
    if (e.key === 'Escape') setShowSuggestions(false)
    if (e.key !== 'Enter') return
    e.preventDefault()
    const query = stockQuery.trim()
    if (!query) return
    const exact = suggestions.find(stock => stock.ticker.toUpperCase() === query.toUpperCase())
    if (exact || suggestions.length > 0) {
      selectStock(exact || suggestions[0])
      return
    }
    if (!/^[A-Za-z0-9.]+$/.test(query)) {
      setError('请选择候选股票，或输入有效的股票代码')
      return
    }
    selectStock({ ticker: query, name: '', market: detectMarket(query) })
  }

  function removeStock(stock) {
    setSelectedStocks(prev => prev.filter(item => !(item.ticker === stock.ticker && item.market === stock.market)))
    setError('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setResultData(null)
    setRunningData(null)
    const selection = validateSelection(mode, selectedStocks)
    if (selection.error) {
      setError(selection.error)
      return
    }
    setSubmitting(true)
    try {
      const r = await backtestApi.run(buildRunPayload(form, selectedStocks))
      setRunningId(r.backtest_id)
      setRunningData({ status: 'pending', name: form.name, strategy: form.strategy, progress: '提交成功，等待执行...' })
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  // 轮询
  useEffect(() => {
    if (!runningId) return
    const timer = setInterval(async () => {
      try {
        const d = await backtestApi.get(runningId)
        setRunningData(d)
        if (d.status === 'done') {
          setResultData(d)
          setRunningId(null)
          loadHistory()
        } else if (d.status === 'error') {
          setError(d.error_msg || '回测失败')
          setRunningId(null)
          loadHistory()
        }
      } catch {
        // 网络问题继续轮询
      }
    }, 2000)
    return () => clearInterval(timer)
  }, [runningId])

  async function viewResult(id) {
    const d = await backtestApi.get(id)
    if (d.status === 'done') setResultData(d)
    else setRunningData(d)
  }

  const selectedSummary = selectedStocks.length
    ? selectedStocks.map(displayStock).join('、')
    : '尚未选择股票'
  const benchmarkLabel = BENCHMARK_OPTIONS.find(item => item.value === form.benchmark)?.label || form.benchmark

  return (
    <div className="space-y-4">
      <form onSubmit={handleSubmit} className="bg-sent-card border border-sent-border rounded-lg p-6 space-y-4">
        <div>
          <h2 className="text-xl font-bold text-white">📈 开始一次回测</h2>
          <p className="mt-1 text-sm text-sent-dim">先选投资方式和股票，其他参数可以稍后调整。</p>
        </div>

        <fieldset>
          <legend className="text-sm font-bold text-white">1. 你想怎么回测？</legend>
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-3">
            {MODE_OPTIONS.map(option => (
              <button
                key={option.value}
                type="button"
                aria-pressed={mode === option.value}
                onClick={() => chooseMode(option.value)}
                className={`rounded-lg border p-4 text-left transition-colors focus:outline-none focus:ring-2 focus:ring-sent-blue ${
                  mode === option.value
                    ? 'border-sent-blue bg-sent-blue/10'
                    : 'border-sent-border bg-sent-bg/50 hover:border-sent-blue/60'
                }`}
              >
                <div className="text-sm font-bold text-white">{option.title}</div>
                <div className="mt-1 text-xs leading-5 text-sent-dim">{option.description}</div>
              </button>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-sm font-bold text-white">2. 选择股票</legend>
          <p className="mt-1 text-xs text-sent-dim">输入名称、拼音或代码，例如：茅台、MAOTAI、600519。{mode === 'portfolio' ? '组合回测至少选择两只股票。' : '趋势回测只选择一只股票。'}</p>
          <div className="relative mt-2">
            <input
              aria-label="搜索股票"
              value={stockQuery}
              onChange={e => setStockQuery(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
              placeholder="输入股票名称、拼音或代码"
              className="w-full bg-sent-bg border border-sent-border rounded px-3 py-2 text-sm focus:outline-none focus:border-sent-blue focus:ring-2 focus:ring-sent-blue/30"
            />
            {showSuggestions && (
              <div className="absolute z-20 mt-1 w-full max-h-72 overflow-auto rounded border border-sent-border bg-sent-card shadow-lg">
                {searching && suggestions.length === 0 && <div className="px-3 py-2 text-xs text-sent-dim">正在搜索股票…</div>}
                {!searching && suggestions.length === 0 && <div className="px-3 py-2 text-xs text-sent-dim">没有找到候选，若输入的是代码可直接按 Enter 添加。</div>}
                {suggestions.map(stock => (
                  <button
                    key={`${stock.market}:${stock.ticker}`}
                    type="button"
                    onMouseDown={e => { e.preventDefault(); selectStock(stock) }}
                    className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-sent-blue/10 focus:bg-sent-blue/10 focus:outline-none"
                  >
                    <span className="flex-1 truncate text-sm text-white">{stock.name}</span>
                    <span className="font-mono text-xs text-sent-dim">{stock.ticker}</span>
                    <span className="text-xs text-sent-blue">{MARKET_LABELS[stock.market] || stock.market}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedStocks.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2" aria-label="已选股票">
              {selectedStocks.map(stock => (
                <span key={`${stock.market}:${stock.ticker}`} className="inline-flex items-center gap-2 rounded bg-sent-blue/10 px-3 py-1.5 text-sm text-white">
                  <span>{displayStock(stock)}</span>
                  {stock.name && <span className="font-mono text-xs text-sent-dim">{stock.ticker}</span>}
                  <span className="text-xs text-sent-blue">{MARKET_LABELS[stock.market] || stock.market}</span>
                  <button type="button" onClick={() => removeStock(stock)} aria-label={`移除 ${displayStock(stock)}`} className="text-sent-dim hover:text-white focus:outline-none focus:ring-2 focus:ring-sent-blue">×</button>
                </span>
              ))}
            </div>
          )}
        </fieldset>

        <fieldset>
          <legend className="text-sm font-bold text-white">3. 选择回测区间</legend>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-sent-dim">从哪天开始</span>
            <input
              type="date"
              value={form.start_date}
              onChange={e => updateForm('start_date', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">到哪天结束</span>
            <input
              type="date"
              value={form.end_date}
              onChange={e => updateForm('end_date', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
          </label>
        </div>
        </fieldset>

        <div className="rounded border border-sent-border bg-sent-bg/60 p-3 text-sm text-sent-dim">
          将用<span className="mx-1 font-medium text-white">{MODE_LABELS[mode]}</span>回测<span className="mx-1 font-medium text-white">{selectedSummary}</span>，时间为 {form.start_date} 至 {form.end_date}，对比 {benchmarkLabel}。
        </div>

        <details className="rounded border border-sent-border bg-sent-bg/30 p-4">
          <summary className="cursor-pointer text-sm font-bold text-sent-blue focus:outline-none">高级设置（策略、资金与交易成本）</summary>
          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block">
                <span className="text-xs text-sent-dim">回测名称</span>
                <input value={form.name} onChange={e => updateForm('name', e.target.value)} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-sent-blue" />
              </label>
              <label className="block">
                <span className="text-xs text-sent-dim">策略引擎</span>
                <select value={form.strategy} onChange={e => handleStrategyChange(e.target.value)} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm">
                  {strategies.map(strategy => <option key={strategy.name} value={strategy.name}>{strategy.name}</option>)}
                </select>
                <span className="mt-1 block text-xs text-sent-dim">{STRATEGY_DESCRIPTIONS[form.strategy] || '自定义策略参数由回测引擎解释'}</span>
              </label>
            </div>

            {Object.keys(form.params).length > 0 && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(form.params).map(([key, value]) => (
                  <label key={key} className="block">
                    <span className="text-xs text-sent-dim">参数 {key}</span>
                    <input value={value} onChange={e => updateParam(key, e.target.value)} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono" />
                  </label>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              <label className="block">
                <span className="text-xs text-sent-dim">初始资金</span>
                <input type="number" value={form.initial_capital} onChange={e => updateForm('initial_capital', Number(e.target.value))} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono" />
              </label>
              <label className="block">
                <span className="text-xs text-sent-dim">基准</span>
                <select value={form.benchmark} onChange={e => updateForm('benchmark', e.target.value)} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm">
                  {BENCHMARK_OPTIONS.map(benchmark => <option key={benchmark.value} value={benchmark.value}>{benchmark.label}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-sent-dim">调仓频率</span>
                <select value={form.rebalance_freq} onChange={e => updateForm('rebalance_freq', e.target.value)} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm">
                  {REBALANCE_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              <label className="block">
                <span className="text-xs text-sent-dim">手续费率</span>
                <input type="number" step="0.0001" value={form.commission} onChange={e => updateForm('commission', Number(e.target.value))} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono" />
              </label>
            </div>
            <label className="block max-w-xs">
              <span className="text-xs text-sent-dim">滑点率</span>
              <input type="number" step="0.0001" value={form.slippage} onChange={e => updateForm('slippage', Number(e.target.value))} className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono" />
            </label>
          </div>
        </details>

        <button
          type="submit"
          disabled={submitting || !!runningId}
          className="bg-sent-blue text-sent-bg px-6 py-2 rounded text-sm font-bold hover:opacity-80 disabled:opacity-50"
        >
          {submitting ? '正在提交…' : runningId ? '回测运行中…' : '运行回测'}
        </button>
      </form>

      {templates.length > 0 && (
        <details className="bg-sent-card border border-sent-border rounded-lg p-4">
          <summary className="cursor-pointer text-sm font-bold text-sent-blue">尝试现成方案</summary>
          <p className="mt-1 text-xs text-sent-dim">套用后仍可在高级设置中查看和调整。</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {templates.map(template => (
              <button key={template.id} type="button" onClick={() => handleTemplate(template)} className="text-left px-3 py-2 rounded-lg border border-sent-border/60 bg-sent-bg/50 hover:border-sent-blue hover:bg-sent-blue/10 transition-colors" title={template.description}>
                <div className="text-sm font-bold text-white">{template.name}</div>
                <div className="text-xs text-sent-dim max-w-[220px] truncate">{template.description}</div>
              </button>
            ))}
          </div>
        </details>
      )}

      {error && <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-3 text-sm">⚠️ {error}</div>}

      {/* 进度 */}
      {runningData && !resultData && (
        <div className="bg-sent-card border border-sent-border rounded-lg p-6">
          <h3 className="text-sm font-bold text-sent-blue mb-2">⏳ 回测运行中</h3>
          <div className="text-sm text-sent-dim">
            <div>状态：<span className="text-white font-mono">{runningData.status}</span></div>
            <div>进度：<span className="text-white font-mono">{runningData.error_msg || '准备中...'}</span></div>
          </div>
        </div>
      )}

      {/* 结果展示 */}
      {resultData && (
        <BacktestResult data={resultData} />
      )}

      {/* 历史 */}
      <div className="bg-sent-card border border-sent-border rounded-lg p-6">
        <h3 className="text-sm font-bold text-sent-blue mb-3">📚 最近回测</h3>
        <div className="space-y-1">
          {history.length === 0 && <div className="text-sent-dim text-sm text-center py-4">还没有回测记录</div>}
          {history.map(b => (
            <div
              key={b.id}
              className="flex items-center justify-between bg-sent-bg border border-sent-border rounded px-3 py-2 cursor-pointer hover:border-sent-blue/40"
              onClick={() => viewResult(b.id)}
            >
              <div>
                <span className="text-white">#{b.id} {b.name}</span>
                <span className="text-xs text-sent-dim ml-3">
                  {b.strategy} · {b.start_date} ~ {b.end_date}
                </span>
              </div>
              <span className={`text-xs font-bold ${
                b.status === 'done' ? 'text-sent-green' :
                b.status === 'error' ? 'text-sent-red' : 'text-sent-yellow'
              }`}>
                {b.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function BacktestResult({ data }) {
  const m = data.metrics || {}
  return (
    <div className="bg-sent-card border border-sent-border rounded-lg p-6 space-y-4">
      <h3 className="text-lg font-bold text-sent-green">✅ 回测完成 - {data.name}</h3>

      {/* 关键指标卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Metric label="总收益" value={fmt(m.total_return, 4)} highlight={m.total_return >= 0 ? 'green' : 'red'} />
        <Metric label="年化收益" value={fmt(m.annual_return, 4)} highlight={m.annual_return >= 0 ? 'green' : 'red'} />
        <Metric label="夏普比率" value={fmt(m.sharpe, 2)} />
        <Metric label="最大回撤" value={fmt(m.max_drawdown, 4)} highlight="red" />
        <Metric label="波动率" value={fmt(m.volatility, 4)} />
        <Metric label="胜率" value={fmt(m.win_rate, 2)} />
        <Metric label="Alpha" value={fmt(m.alpha, 4)} highlight={m.alpha >= 0 ? 'green' : 'red'} />
        <Metric label="Beta" value={fmt(m.beta, 2)} />
      </div>

      {/* 收益曲线（简化） */}
      {data.equity_curve && data.equity_curve.length > 0 && (
        <EquityCurveMini data={data.equity_curve} />
      )}

      {/* 交易记录 */}
      {data.trades && data.trades.length > 0 && (
        <details>
          <summary className="cursor-pointer text-sm text-sent-blue">
            📋 查看交易记录（{data.trades.length} 笔）
          </summary>
          <div className="mt-2 max-h-64 overflow-auto">
            <table className="w-full text-xs font-mono">
              <thead className="text-sent-dim sticky top-0 bg-sent-card">
                <tr>
                  <th className="text-left p-1">日期</th>
                  <th className="text-left p-1">代码</th>
                  <th className="text-left p-1">方向</th>
                  <th className="text-right p-1">价格</th>
                  <th className="text-right p-1">数量</th>
                  <th className="text-right p-1">金额</th>
                </tr>
              </thead>
              <tbody>
                {data.trades.map((t, i) => (
                  <tr key={i} className="border-t border-sent-border/30">
                    <td className="p-1">{t.trade_date}</td>
                    <td className="p-1">{t.ticker}</td>
                    <td className={`p-1 ${t.side === 'buy' ? 'text-sent-green' : 'text-sent-red'}`}>{t.side === 'buy' ? '买' : '卖'}</td>
                    <td className="p-1 text-right">{fmt(t.price, 2)}</td>
                    <td className="p-1 text-right">{t.qty}</td>
                    <td className="p-1 text-right">{fmt(t.amount, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}

      <button
        onClick={() => navigator.clipboard?.writeText(JSON.stringify(data, null, 2))}
        className="text-xs text-sent-dim hover:text-white"
      >
        📋 复制完整结果 JSON
      </button>
    </div>
  )
}

function Metric({ label, value, highlight }) {
  const color = highlight === 'green' ? 'text-sent-green' :
                highlight === 'red'   ? 'text-sent-red'   : 'text-white'
  return (
    <div className="bg-sent-bg border border-sent-border rounded p-3">
      <div className="text-xs text-sent-dim">{label}</div>
      <div className={`text-lg font-mono mt-1 ${color}`}>{value}</div>
    </div>
  )
}

function EquityCurveMini({ data }) {
  // 简化：把净值曲线化成 SVG
  if (!data || data.length < 2) return null
  const w = 600, h = 120, pad = 8
  const values = data.map(d => d.value)
  const min = Math.min(...values), max = Math.max(...values)
  const range = max - min || 1
  const points = data.map((d, i) => {
    const x = pad + (w - 2 * pad) * (i / (data.length - 1))
    const y = pad + (h - 2 * pad) * (1 - (d.value - min) / range)
    return `${x},${y}`
  }).join(' ')
  return (
    <div className="bg-sent-bg border border-sent-border rounded p-3">
      <div className="text-xs text-sent-dim mb-2">净值曲线</div>
      <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <polyline points={points} fill="none" stroke="#60a5fa" strokeWidth="1.5" />
      </svg>
      <div className="flex justify-between text-xs text-sent-dim mt-1">
        <span>起始 {fmt(values[0], 0)}</span>
        <span>最高 {fmt(max, 0)}</span>
        <span>最低 {fmt(min, 0)}</span>
        <span>末值 {fmt(values[values.length - 1], 0)}</span>
      </div>
    </div>
  )
}

function fmt(v, decimals = 2) {
  if (v == null || isNaN(v)) return '—'
  return Number(v).toFixed(decimals)
}
