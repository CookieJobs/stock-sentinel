/**
 * Backtest - 回测工作流（M4 完整版）
 * 流程：选策略 → 配参数 → 输标的 → 提交 → 轮询进度 → 看结果
 */
import { useEffect, useState } from 'react'
import { backtest as backtestApi } from '../lib/api'

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

export default function Backtest() {
  const [strategies, setStrategies] = useState([])
  const [history, setHistory] = useState([])
  const [form, setForm] = useState({
    name: '我的回测',
    strategy: 'ma_cross',
    params: { fast: 5, slow: 20 },
    tickers: '600519',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
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
    loadHistory()
  }, [])

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
    setForm(prev => ({
      ...prev,
      strategy: s,
      params: { ...STRATEGY_DEFAULTS[s] },
    }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    setResultData(null)
    setRunningData(null)
    const tickers = form.tickers.split(/[,\s]+/).map(t => t.trim().toUpperCase()).filter(Boolean)
    if (!tickers.length) {
      setError('请输入至少一个股票代码')
      setSubmitting(false)
      return
    }
    try {
      const r = await backtestApi.run({
        ...form,
        tickers,
        // 把 params 转成数字
        params: Object.fromEntries(Object.entries(form.params).map(([k, v]) => [k, Number(v) || v])),
      })
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

  return (
    <div className="space-y-4">
      {/* 提交表单 */}
      <form onSubmit={handleSubmit} className="bg-sent-card border border-sent-border rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-bold text-white">📈 回测中心</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="block">
            <span className="text-xs text-sent-dim">回测名称</span>
            <input
              value={form.name}
              onChange={e => updateForm('name', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-sent-blue"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">策略</span>
            <select
              value={form.strategy}
              onChange={e => handleStrategyChange(e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            >
              {strategies.map(s => (
                <option key={s.name} value={s.name}>{s.name}</option>
              ))}
            </select>
            <span className="text-xs text-sent-dim mt-1 block">
              {STRATEGY_DESCRIPTIONS[form.strategy]}
            </span>
          </label>
        </div>

        {/* 策略参数 */}
        {Object.keys(form.params).length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(form.params).map(([k, v]) => (
              <label key={k} className="block">
                <span className="text-xs text-sent-dim">{k}</span>
                <input
                  value={v}
                  onChange={e => updateParam(k, e.target.value)}
                  className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
                />
              </label>
            ))}
          </div>
        )}

        <label className="block">
          <span className="text-xs text-sent-dim">股票代码（逗号或空格分隔）</span>
          <input
            value={form.tickers}
            onChange={e => updateForm('tickers', e.target.value)}
            placeholder="600519, 000858, 000001"
            className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
          />
        </label>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <label className="block">
            <span className="text-xs text-sent-dim">开始日期</span>
            <input
              type="date"
              value={form.start_date}
              onChange={e => updateForm('start_date', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">结束日期</span>
            <input
              type="date"
              value={form.end_date}
              onChange={e => updateForm('end_date', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">初始资金</span>
            <input
              type="number"
              value={form.initial_capital}
              onChange={e => updateForm('initial_capital', Number(e.target.value))}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">基准</span>
            <select
              value={form.benchmark}
              onChange={e => updateForm('benchmark', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            >
              {BENCHMARK_OPTIONS.map(b => (
                <option key={b.value} value={b.value}>{b.label}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <label className="block">
            <span className="text-xs text-sent-dim">调仓频率</span>
            <select
              value={form.rebalance_freq}
              onChange={e => updateForm('rebalance_freq', e.target.value)}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm"
            >
              {REBALANCE_OPTIONS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">手续费率</span>
            <input
              type="number"
              step="0.0001"
              value={form.commission}
              onChange={e => updateForm('commission', Number(e.target.value))}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
            />
          </label>
          <label className="block">
            <span className="text-xs text-sent-dim">滑点率</span>
            <input
              type="number"
              step="0.0001"
              value={form.slippage}
              onChange={e => updateForm('slippage', Number(e.target.value))}
              className="mt-1 w-full bg-sent-bg border border-sent-border rounded px-3 py-1.5 text-sm font-mono"
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={submitting || !!runningId}
          className="bg-sent-blue text-sent-bg px-6 py-2 rounded text-sm font-bold hover:opacity-80 disabled:opacity-50"
        >
          {submitting ? '提交中...' : runningId ? '回测运行中...' : '▶ 运 行 回 测'}
        </button>
      </form>

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
