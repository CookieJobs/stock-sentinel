/**
 * Risk - 风险分析页（M5 完整版）
 * 复用回测结果 → 净值曲线 + 回撤曲线 + 关键指标
 * 支持：
 *   1. 输入 equity_curve JSON
 *   2. 从回测历史选择已完成的回测
 *   3. 显示完整风险分析
 */
import { useEffect, useState } from 'react'
import { risk as riskApi, backtest as backtestApi } from '../lib/api'

const DEFAULT_EQUITY = JSON.stringify([
  { date: '2024-01-02', value: 1000000, benchmark_value: 1000000 },
  { date: '2024-02-01', value: 980000,  benchmark_value: 970000 },
  { date: '2024-03-01', value: 1050000, benchmark_value: 1020000 },
  { date: '2024-04-01', value: 1080000, benchmark_value: 1060000 },
  { date: '2024-05-01', value: 1020000, benchmark_value: 1080000 },
  { date: '2024-06-01', value: 1100000, benchmark_value: 1100000 },
  { date: '2024-07-01', value: 1150000, benchmark_value: 1130000 },
  { date: '2024-08-01', value: 1080000, benchmark_value: 1100000 },
  { date: '2024-09-01', value: 1120000, benchmark_value: 1150000 },
  { date: '2024-10-01', value: 1180000, benchmark_value: 1180000 },
  { date: '2024-11-01', value: 1220000, benchmark_value: 1160000 },
  { date: '2024-12-31', value: 1200000, benchmark_value: 1190000 },
], null, 2)

export default function Risk() {
  const [equityInput, setEquityInput] = useState(DEFAULT_EQUITY)
  const [metrics, setMetrics] = useState(null)
  const [equityData, setEquityData] = useState(null)
  const [drawdownSeries, setDrawdownSeries] = useState(null)
  const [error, setError] = useState('')
  const [history, setHistory] = useState([])
  const [loadingId, setLoadingId] = useState(null)
  const [view, setView] = useState('curve')  // 'curve' | 'drawdown' | 'metrics'

  useEffect(() => {
    backtestApi.listRecent(20).then(d => setHistory(d.backtests || [])).catch(() => {})
  }, [])

  async function handleCompute() {
    setError('')
    setMetrics(null)
    setDrawdownSeries(null)
    try {
      const equity = JSON.parse(equityInput)
      if (!Array.isArray(equity) || equity.length < 2) {
        throw new Error('equity_curve 至少需要 2 个数据点')
      }
      const result = await riskApi.compute(equity, equity[0].value)
      setMetrics(result)
      setEquityData(equity)

      // 算回撤曲线
      const dd = []
      let peak = equity[0].value
      for (const pt of equity) {
        if (pt.value > peak) peak = pt.value
        const ddPct = peak > 0 ? (pt.value - peak) / peak : 0
        dd.push({ date: pt.date, value: ddPct * 100 })
      }
      setDrawdownSeries(dd)
    } catch (e) {
      setError(e.message)
    }
  }

  async function loadFromBacktest(id) {
    setLoadingId(id)
    setError('')
    try {
      const d = await backtestApi.get(id)
      if (d.status !== 'done') {
        setError(`回测 #${id} 状态: ${d.status}，请等待完成`)
        return
      }
      const eq = d.equity_curve || []
      if (eq.length < 2) {
        setError('回测无净值数据')
        return
      }
      // 写入 input
      setEquityInput(JSON.stringify(eq, null, 2))
      // 自动 compute
      const result = await riskApi.compute(eq, eq[0].value)
      setMetrics(result)
      setEquityData(eq)
      const dd = []
      let peak = eq[0].value
      for (const pt of eq) {
        if (pt.value > peak) peak = pt.value
        dd.push({ date: pt.date, value: peak > 0 ? (pt.value - peak) / peak * 100 : 0 })
      }
      setDrawdownSeries(dd)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingId(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-sent-card border border-sent-border rounded-lg p-4">
        <h2 className="text-lg font-bold text-white mb-2">⚖️ 风险分析</h2>
        <p className="text-sent-dim text-sm mb-4">输入净值曲线或从回测历史加载，自动算全套风险指标 + 净值曲线 + 回撤曲线。</p>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* 左侧：输入 + 历史 */}
          <div className="lg:col-span-1 space-y-3">
            <div>
              <h3 className="text-xs text-sent-dim font-bold mb-2">📝 equity_curve JSON</h3>
              <textarea
                value={equityInput}
                onChange={e => setEquityInput(e.target.value)}
                className="w-full h-40 bg-sent-bg border border-sent-border rounded p-2 text-xs font-mono text-white"
              />
              <button
                onClick={handleCompute}
                className="mt-2 w-full bg-sent-blue text-sent-bg px-4 py-1.5 rounded text-sm font-bold hover:opacity-80"
              >
                计 算
              </button>
            </div>
            <div>
              <h3 className="text-xs text-sent-dim font-bold mb-2">📚 从回测历史加载</h3>
              <div className="space-y-1 max-h-64 overflow-auto">
                {history.filter(h => h.status === 'done').slice(0, 10).map(h => (
                  <button
                    key={h.id}
                    onClick={() => loadFromBacktest(h.id)}
                    disabled={loadingId === h.id}
                    className="w-full text-left bg-sent-bg border border-sent-border rounded px-2 py-1.5 text-xs hover:border-sent-blue/40 disabled:opacity-50"
                  >
                    <div className="font-mono text-white">#{h.id} {h.name}</div>
                    <div className="text-sent-dim">
                      {loadingId === h.id ? '加载中...' : `${h.strategy} · ${h.start_date} ~ ${h.end_date}`}
                    </div>
                  </button>
                ))}
                {history.filter(h => h.status === 'done').length === 0 && (
                  <div className="text-sent-dim text-xs text-center py-3">还没有完成的回测</div>
                )}
              </div>
            </div>
          </div>

          {/* 右侧：图表 + 指标 */}
          <div className="lg:col-span-2 space-y-3">
            {error && <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded p-2 text-sm">⚠️ {error}</div>}

            {!metrics && !error && (
              <div className="bg-sent-bg border border-sent-border rounded p-8 text-sent-dim text-sm text-center">
                输入 JSON 或选择回测，点击"计算"开始分析
              </div>
            )}

            {metrics && (
              <>
                {/* 视图切换 */}
                <div className="flex gap-1">
                  {[
                    { value: 'curve', label: '📈 净值曲线' },
                    { value: 'drawdown', label: '📉 回撤曲线' },
                    { value: 'metrics', label: '📊 风险指标' },
                  ].map(v => (
                    <button
                      key={v.value}
                      onClick={() => setView(v.value)}
                      className={`px-3 py-1 rounded text-xs font-mono ${
                        view === v.value
                          ? 'bg-sent-blue text-sent-bg'
                          : 'bg-sent-bg border border-sent-border text-sent-dim hover:text-white'
                      }`}
                    >
                      {v.label}
                    </button>
                  ))}
                </div>

                {/* 净值曲线 / 回撤曲线 / 指标 */}
                {view === 'curve' && equityData && <EquityChartView equity={equityData} />}
                {view === 'drawdown' && drawdownSeries && <DrawdownChartView drawdown={drawdownSeries} />}
                {view === 'metrics' && <MetricsView metrics={metrics} />}

                {/* 概览数字（始终显示在底部） */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  <Stat label="总收益" value={fmt(metrics.total_return, true)} />
                  <Stat label="年化" value={fmt(metrics.annual_return, true)} />
                  <Stat label="夏普" value={fmt(metrics.sharpe, false)} />
                  <Stat label="最大回撤" value={fmt(metrics.max_drawdown, true)} highlight="red" />
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function EquityChartView({ equity }) {
  if (!equity || equity.length < 2) return null
  const w = 600, h = 220, pad = 10
  const values = equity.map(d => d.value)
  const benchValues = equity.map(d => d.benchmark_value).filter(v => v != null)
  const allValues = [...values, ...benchValues]
  const min = Math.min(...allValues), max = Math.max(...allValues)
  const range = max - min || 1

  const linePoints = (data) => data.map((d, i) => {
    const x = pad + (w - 2 * pad) * (i / (data.length - 1))
    const y = pad + (h - 2 * pad) * (1 - (d - min) / range)
    return `${x},${y}`
  }).join(' ')

  return (
    <div className="bg-sent-bg border border-sent-border rounded p-3">
      <div className="text-xs text-sent-dim mb-2 flex items-center gap-3">
        <span className="inline-flex items-center gap-1">
          <span className="inline-block w-2 h-2 bg-sent-blue rounded-full" />策略净值
        </span>
        {benchValues.length > 0 && (
          <span className="inline-flex items-center gap-1">
            <span className="inline-block w-2 h-2 bg-sent-yellow rounded-full" />基准
          </span>
        )}
      </div>
      <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        {benchValues.length === equity.length && (
          <polyline points={linePoints(benchValues)} fill="none" stroke="#fbbf24" strokeWidth="1" strokeDasharray="3,3" />
        )}
        <polyline points={linePoints(values)} fill="none" stroke="#60a5fa" strokeWidth="2" />
        {/* 起止点 */}
        <circle cx={pad} cy={pad + (h - 2 * pad) * (1 - (values[0] - min) / range)} r="3" fill="#60a5fa" />
        <circle cx={w - pad} cy={pad + (h - 2 * pad) * (1 - (values[values.length - 1] - min) / range)} r="3" fill="#60a5fa" />
      </svg>
      <div className="flex justify-between text-xs text-sent-dim mt-1">
        <span>起始 ¥{values[0].toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        <span>末值 ¥{values[values.length - 1].toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
      </div>
    </div>
  )
}

function DrawdownChartView({ drawdown }) {
  if (!drawdown || drawdown.length < 2) return null
  const w = 600, h = 180, pad = 10
  const min = Math.min(...drawdown.map(d => d.value), 0)

  const points = drawdown.map((d, i) => {
    const x = pad + (w - 2 * pad) * (i / (drawdown.length - 1))
    const y = pad + (h - 2 * pad) * (1 - d.value / min)  // min 为负，d.value 越负 y 越大
    return `${x},${y}`
  }).join(' ')

  const maxDD = Math.min(...drawdown.map(d => d.value))

  return (
    <div className="bg-sent-bg border border-sent-border rounded p-3">
      <div className="text-xs text-sent-dim mb-2 flex items-center gap-3">
        <span><span className="inline-block w-2 h-2 bg-sent-red rounded-full mr-1"/>回撤幅度</span>
      </div>
      <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        {/* 0 线 */}
        <line x1={pad} y1={pad} x2={w - pad} y2={pad} stroke="#1e2130" strokeWidth="1" />
        <polyline points={points} fill="none" stroke="#f87171" strokeWidth="2" />
      </svg>
      <div className="text-xs text-sent-dim mt-1 text-center">
        最大回撤 <span className="text-sent-red font-mono font-bold">{(maxDD).toFixed(2)}%</span>
      </div>
    </div>
  )
}

function MetricsView({ metrics }) {
  const groups = [
    { title: '收益类', keys: ['total_return', 'annual_return', 'years'] },
    { title: '风险类', keys: ['volatility', 'max_drawdown', 'var_95', 'cvar_95'] },
    { title: '风险调整', keys: ['sharpe', 'sortino', 'calmar'] },
    { title: '相对基准', keys: ['alpha', 'beta', 'tracking_error', 'information_ratio'] },
    { title: '交易', keys: ['win_rate', 'trade_count', 'sell_count', 'profit_loss_ratio'] },
  ]
  return (
    <div className="bg-sent-bg border border-sent-border rounded p-3 space-y-3">
      {groups.map(g => {
        const items = g.keys.filter(k => metrics[k] != null)
        if (!items.length) return null
        return (
          <div key={g.title}>
            <div className="text-xs text-sent-blue font-bold mb-2">{g.title}</div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {items.map(k => <Stat key={k} label={labelOf(k)} value={fmt(metrics[k], k.includes('return') || k.includes('drawdown') || k.includes('win') || k.includes('ratio'))} />)}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Stat({ label, value, highlight }) {
  const color = highlight === 'red' ? 'text-sent-red' :
                highlight === 'green' ? 'text-sent-green' : 'text-white'
  return (
    <div className="bg-sent-card border border-sent-border rounded p-2">
      <div className="text-xs text-sent-dim">{label}</div>
      <div className={`text-sm font-mono mt-0.5 ${color}`}>{value}</div>
    </div>
  )
}

function labelOf(k) {
  const map = {
    total_return: '总收益', annual_return: '年化', years: '年数',
    volatility: '波动率', max_drawdown: '最大回撤', var_95: 'VaR(95%)', cvar_95: 'CVaR(95%)',
    sharpe: '夏普', sortino: '索提诺', calmar: '卡玛',
    alpha: 'Alpha', beta: 'Beta', tracking_error: '跟踪误差', information_ratio: '信息比率',
    win_rate: '胜率', trade_count: '总交易', sell_count: '卖出数', profit_loss_ratio: '盈亏比',
  }
  return map[k] || k
}

function fmt(v, asPct = false) {
  if (v == null || isNaN(v)) return '—'
  let s = Number(v).toFixed(4)
  if (asPct) s = (Number(v) * 100).toFixed(2) + '%'
  return s
}
