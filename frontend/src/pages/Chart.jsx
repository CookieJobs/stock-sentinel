/**
 * Chart - 单股深度图表页
 * K 线 + 成交量 + 多技术指标
 */
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import StockChart from '../components/StockChart'
import { kline } from '../lib/api'

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
  const [chartData, setChartData] = useState({ kline: [], indicators: {}, meta: null })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [inputTicker, setInputTicker] = useState(ticker)

  // 加载 K 线 + 指标
  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    kline.withIndicators(ticker, { market, period, adj }, activeIndicators)
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
  }, [ticker, market, period, adj, activeIndicators])

  function handleTickerSubmit(e) {
    e.preventDefault()
    const t = inputTicker.trim().toUpperCase()
    if (!t) return
    const m = detectMarket(t)
    setMarket(m)
    setSearchParams({ ticker: t, period })
  }

  return (
    <div className="space-y-4">
      {/* 控制栏 */}
      <div className="bg-sent-card border border-sent-border rounded-lg p-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Ticker 输入 */}
          <form onSubmit={handleTickerSubmit} className="flex gap-2">
            <input
              value={inputTicker}
              onChange={e => setInputTicker(e.target.value)}
              placeholder="代码（600519 / AAPL / 00700）"
              className="bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm w-56 focus:outline-none focus:border-sent-blue"
            />
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

          {/* 市场标识 */}
          <div className="ml-auto text-sm text-sent-dim">
            {MARKETS.find(m => m.value === market)?.label || market}
          </div>
        </div>

        {/* 指标预设 */}
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

      {/* 图表 */}
      <div className="bg-sent-card border border-sent-border rounded-lg overflow-hidden">
        <StockChart
          kline={chartData.kline}
          indicators={chartData.indicators}
          loading={loading}
          height={520}
        />
      </div>
    </div>
  )
}
