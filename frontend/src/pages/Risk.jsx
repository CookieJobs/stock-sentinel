/**
 * Risk - 风险指标展示页（M5 充实）
 */
import { useState } from 'react'
import { risk as riskApi } from '../lib/api'

export default function Risk() {
  const [equityInput, setEquityInput] = useState(JSON.stringify([
    { date: '2024-01-01', value: 1000000 },
    { date: '2024-04-01', value: 1050000 },
    { date: '2024-07-01', value: 980000 },
    { date: '2024-10-01', value: 1120000 },
    { date: '2024-12-31', value: 1080000 },
  ], null, 2))
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState('')

  async function handleCompute() {
    setError('')
    try {
      const equity = JSON.parse(equityInput)
      const result = await riskApi.compute(equity, 1_000_000)
      setMetrics(result)
    } catch (e) {
      setError(e.message)
      setMetrics(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="bg-sent-card border border-sent-border rounded-lg p-6">
        <h2 className="text-lg font-bold text-white mb-2">⚖️ 风险指标</h2>
        <p className="text-sent-dim text-sm mb-4">输入净值曲线（即 equity_curve），计算完整风险指标。</p>

        <textarea
          value={equityInput}
          onChange={e => setEquityInput(e.target.value)}
          className="w-full h-48 bg-sent-bg border border-sent-border rounded p-3 text-xs font-mono text-white"
        />

        <button
          onClick={handleCompute}
          className="mt-3 bg-sent-blue text-sent-bg px-4 py-1.5 rounded text-sm font-bold hover:opacity-80"
        >
          计 算
        </button>

        {error && <div className="text-sent-red text-sm mt-3">{error}</div>}

        {metrics && (
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(metrics).map(([k, v]) => (
              <div key={k} className="bg-sent-bg border border-sent-border rounded p-3">
                <div className="text-xs text-sent-dim">{k}</div>
                <div className="text-lg font-mono text-white mt-1">
                  {typeof v === 'number' ? v.toFixed(4) : String(v)}
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 text-xs text-sent-dim">
          ✅ 后端 13 个风险指标 ready（夏普/Sortino/Calmar/最大回撤/波动率/VaR/CVaR/Alpha/Beta/信息比率/胜率/盈亏比）<br />
          🚧 前端可视化（收益曲线 + 回撤图）：M5 实现
        </div>
      </div>
    </div>
  )
}
