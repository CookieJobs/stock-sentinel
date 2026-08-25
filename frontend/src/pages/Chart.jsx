/**
 * Chart - 单股深度图表页
 * K 线 + 成交量 + 多技术指标
 */
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import StockChart from '../components/StockChart'
import { kline, search } from '../lib/api'

const PERIODS = [
  { value: '1d',  label: '日 K' },
  { value: '1w',  label: '周 K' },
  { value: '1mo', label: '月 K' },
  { value: '60m', label: '60分' },
  { value: '30m', label: '30分' },
  { value: '15m', label: '15分' },
  { value: '5m',  label: '5分' },
  { value: '1m',  label: '1分' },
]

const MARKETS = [
  { value: 'CN', label: '🇨🇳 A股', detect: t => /^\d{6}$/.test(t) },
  { value: 'HK', label: '🇭🇰 港股', detect: t => /^\d{1,5}$/.test(t) || t.toUpperCase().endsWith('.HK') },
  { value: 'US', label: '🇺🇸 美股', detect: t => /^[A-Z]+$/.test(t) },
]

const INDICATOR_PRESETS = [
  { name: 'MA',  label: 'MA(5,10,20,60)',  specs: [
    { name: 'MA', params: { period: 5 }},
    { name: 'MA', params: { period: 10 }},
    { name: 'MA', params: { period: 20 }},
    { name: 'MA', params: { period: 60 }},
  ]},
  { name: 'BOLL', label: 'BOLL(20,2)', specs: [{ name: 'BOLL', params: { period: 20, stddev: 2.0 }}]},
  { name: 'EMA',  label: 'EMA(12,26)', specs: [
    { name: 'EMA', params: { period: 12 }},
    { name: 'EMA', params: { period: 26 }},
  ]},
  { name: 'SAR',  label: 'SAR(0.02,0.2)', specs: [
    { name: 'SAR', params: { step: 0.02, max_step: 0.2 }},
  ]},
]

const OSCILLATOR_OPTIONS = [
  { value: null,  label: '无' },
  { value: 'MACD', label: 'MACD (12,26,9)' },
  { value: 'RSI',  label: 'RSI (14)' },
  { value: 'KDJ',  label: 'KDJ (9,3,3)' },
  { value: 'WR',   label: 'WR (14)' },
  { value: 'CCI',  label: 'CCI (14)' },
  { value: 'ATR',  label: 'ATR (14)' },
]

function detectMarket(ticker) {
  const t = ticker.trim().toUpperCase().replace('.HK', '')
  for (const m of MARKETS) if (m.detect(t)) return m.value
  return 'US'
}

export default function Chart() {
  const [searchParams, setSearchParams] = useSearchParams()
  const ticker = searchParams.get('ticker') || '600519'
  const [period, setPeriod] = useState(searchParams.get('period') || '1d')
  const [market, setMarket] = useState(detectMarket(ticker))
  const [adj] = useState('qfq')
  const [activeIndicators, setActiveIndicators] = useState(INDICATOR_PRESETS[0].specs)
  const [oscillator, setOscillator] = useState('MACD')
  const [chartData, setChartData] = useState({ kline: [], indicators: {}, meta: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [inputTicker, setInputTicker] = useState(ticker)
  const [stockName, setStockName] = useState('')      // 当前股票名称（搜索/反查解析）
  const [suggestions, setSuggestions] = useState([])  // 搜索下拉候选
  const [showDropdown, setShowDropdown] = useState(false)
  const [searching, setSearching] = useState(false)

  // 加载 K 线 + 指标（含当前 oscillator）
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    // 把 oscillator 也加入请求（如果选了）
    const specs = [...activeIndicators]
    if (oscillator) {
      const oscSpecs = oscillatorToSpecs(oscillator)
      specs.push(...oscSpecs)
    }
    kline.withIndicators(ticker, { market, period, adj }, specs)
      .then(data => {
        if (cancelled) return
        setChartData(data)
      })
      .catch(err => {
        if (cancelled) return
        setError(err.message)
        setChartData({ kline: [], indicators: {}, meta: null })
      })
      .finally(() => {
        if (cancelled) return
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [ticker, market, period, adj, activeIndicators, oscillator])

  // 输入联想搜索（300ms 防抖；输入等于当前代码时不再弹下拉）
  useEffect(() => {
    const q = inputTicker.trim()
    if (!q || q.toUpperCase() === ticker.toUpperCase()) {
      setSuggestions([])
      setShowDropdown(false)
      return
    }
    const timer = setTimeout(() => {
      setSearching(true)
      search.stocks(q, { limit: 8 })
        .then(data => {
          setSuggestions(data.results || [])
          setShowDropdown(true)
        })
        .catch(() => { setSuggestions([]); setShowDropdown(false) })
        .finally(() => setSearching(false))
    }, 300)
    return () => clearTimeout(timer)
  }, [inputTicker, ticker])

  // 深链/刷新时按 (ticker, market) 反查名称，页头显示「名称 + 代码」
  useEffect(() => {
    let cancelled = false
    setStockName('')
    search.stocks(ticker, { limit: 5, market })
      .then(data => {
        if (cancelled) return
        const hit = (data.results || []).find(r => r.ticker.toUpperCase() === ticker.toUpperCase())
        if (hit) setStockName(hit.name)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [ticker, market])

  // 选中下拉结果：跳转 + 记名称
  function selectStock(item) {
    setInputTicker(item.ticker)
    setStockName(item.name)
    setMarket(item.market)
    setShowDropdown(false)
    setSearchParams({ ticker: item.ticker, period })
  }

  function handleTickerSubmit(e) {
    e.preventDefault()
    const t = inputTicker.trim().toUpperCase()
    if (!t) return
    if (suggestions.length > 0) {
      // 有候选：精确代码匹配优先，否则选第一条（东财按相关性排序）
      const exact = suggestions.find(s => s.ticker.toUpperCase() === t)
      selectStock(exact || suggestions[0])
      return
    }
    // 无候选：当作代码直接查询（保持原行为）
    const m = detectMarket(t)
    setMarket(m)
    setSearchParams({ ticker: t, period })
  }

  return (
    <div className="space-y-4">
      {/* 控制栏 */}
      <div className="bg-sent-card border border-sent-border rounded-lg p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Ticker/名称 输入（联想下拉） */}
          <form onSubmit={handleTickerSubmit} className="flex gap-2">
            <div className="relative">
              <input
                value={inputTicker}
                onChange={e => setInputTicker(e.target.value)}
                onKeyDown={e => { if (e.key === 'Escape') setShowDropdown(false) }}
                onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
                placeholder="代码 / 名称（600519、茅台、AAPL）"
                className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm w-64 focus:outline-none focus:border-sent-blue"
              />
              {showDropdown && (
                <div className="absolute z-20 mt-1 w-72 max-h-72 overflow-auto bg-sent-card border border-sent-border rounded shadow-lg">
                  {searching && suggestions.length === 0 && (
                    <div className="px-3 py-2 text-xs text-sent-dim">搜索中…</div>
                  )}
                  {!searching && suggestions.length === 0 && (
                    <div className="px-3 py-2 text-xs text-sent-dim">未找到匹配的股票</div>
                  )}
                  {suggestions.map(s => (
                    <button
                      key={`${s.market}:${s.ticker}`}
                      type="button"
                      onMouseDown={e => { e.preventDefault(); selectStock(s) }}
                      className="w-full text-left px-3 py-2 flex items-center gap-2 hover:bg-sent-blue/10"
                    >
                      <span className="text-sm text-white flex-1 truncate">{s.name}</span>
                      <span className="text-xs font-mono text-sent-dim">{s.ticker}</span>
                      <span className="text-xs">{MARKETS.find(m => m.value === s.market)?.label.split(' ')[0] || s.market}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button type="submit" className="bg-sent-blue text-sent-bg px-4 py-1.5 rounded text-sm font-bold hover:opacity-80">
              查 询
            </button>
          </form>

          {/* 周期 */}
          <div className="flex gap-1 ml-4">
            {PERIODS.map(p => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-1.5 rounded text-xs font-mono transition ${
                  period === p.value
                    ? 'bg-sent-blue text-sent-bg'
                    : 'bg-sent-bg border border-sent-border text-sent-dim hover:text-white'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* 当前股票：名称 + 代码 + 市场 */}
          <div className="ml-auto text-sm flex items-center gap-2">
            {stockName && <span className="text-white font-semibold">{stockName}</span>}
            <span className="font-mono text-sent-dim">{ticker}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-sent-bg border border-sent-border text-sent-dim">
              {MARKETS.find(m => m.value === market)?.label || market}
            </span>
          </div>
        </div>

        {/* 指标预设 + 振荡器选择 */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-sent-dim">叠加指标：</span>
          {INDICATOR_PRESETS.map(p => {
            const active = p.specs.every(s => activeIndicators.some(a => a.name === s.name && JSON.stringify(a.params) === JSON.stringify(s.params)))
            return (
              <button
                key={p.name}
                onClick={() => active ? setActiveIndicators([]) : setActiveIndicators(p.specs)}
                className={`px-2 py-1 rounded text-xs ${
                  active ? 'bg-sent-yellow/20 text-sent-yellow border border-sent-yellow/40' : 'bg-sent-bg border border-sent-border text-sent-dim hover:text-white'
                }`}
              >
                {p.label}
              </button>
            )
          })}
          <span className="text-xs text-sent-dim ml-2">
            已选 {activeIndicators.length} 个
          </span>
        </div>

        {/* 振荡器（独立 pane） */}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs text-sent-dim">下方振荡器：</span>
          {OSCILLATOR_OPTIONS.map(o => (
            <button
              key={o.value ?? 'none'}
              onClick={() => setOscillator(o.value)}
              className={`px-2 py-1 rounded text-xs ${
                oscillator === o.value
                  ? 'bg-sent-blue/20 text-sent-blue border border-sent-blue/40'
                  : 'bg-sent-bg border border-sent-border text-sent-dim hover:text-white'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>

      {/* 错误 */}
      {error && (
        <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-3 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* 元信息 */}
      {chartData.meta && chartData.meta.row_count > 0 && (
        <div className="flex gap-4 text-xs text-sent-dim">
          <span>共 <span className="text-white font-mono">{chartData.meta.row_count}</span> 根 K 线</span>
          <span>范围 <span className="text-white font-mono">{chartData.meta.first_date}</span> ~ <span className="text-white font-mono">{chartData.meta.last_date}</span></span>
          <span>状态 <span className={chartData.meta.is_stale ? 'text-sent-yellow' : 'text-sent-green'}>{chartData.meta.is_stale ? '数据过期' : '数据新鲜'}</span></span>
        </div>
      )}

      {/* 空数据提示（如分钟周期数据源不可用） */}
      {!loading && !error && chartData.meta && chartData.meta.row_count === 0 && (
        <div className="bg-sent-yellow/10 border border-sent-yellow/40 text-sent-yellow rounded p-3 text-sm">
          ⚠️ 暂无数据：该代码/周期没有可用 K 线（数据源不可用或当前周期不支持）
        </div>
      )}

      {/* 图表 */}
      <div className="bg-sent-card border border-sent-border rounded-lg overflow-hidden">
        <StockChart
          kline={chartData.kline}
          indicators={chartData.indicators}
          oscillator={oscillator}
          loading={loading}
          height={520}
        />
      </div>
    </div>
  )
}

// 把 oscillator 名转成 indicators specs（用于 API 请求）
function oscillatorToSpecs(osc) {
  if (osc === 'MACD') return [{ name: 'MACD', params: {} }]
  if (osc === 'RSI') return [{ name: 'RSI', params: { period: 14 } }]
  if (osc === 'KDJ') return [{ name: 'KDJ', params: { n: 9, m1: 3, m2: 3 } }]
  if (osc === 'WR') return [{ name: 'WR', params: { period: 14 } }]
  if (osc === 'CCI') return [{ name: 'CCI', params: { period: 14 } }]
  if (osc === 'ATR') return [{ name: 'ATR', params: { period: 14 } }]
  return []
}
